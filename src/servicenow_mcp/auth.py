import asyncio
from abc import ABC, abstractmethod
from time import monotonic
from typing import Any

import httpx
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.utilities.auth import decode_jwt_payload, parse_scopes
from pydantic import BaseModel, ConfigDict, Field

from .errors import ErrorCode, KnowledgeMcpError
from .tls import system_ssl_context


class AuthorizationContext(BaseModel):
    """Reserved context for a confirmed end-user authorization mechanism."""

    model_config = ConfigDict(extra="ignore")
    subject_id: str | None = None
    delegated_token: str | None = Field(default=None, repr=False, exclude=True)


class ApimClaimsTokenVerifier(TokenVerifier):
    """Trust claims from a bearer token that APIM has already validated.

    This class intentionally performs no signature, issuer, or audience validation. It must only
    be used when the backend cannot be reached except through APIM and APIM validates the token
    before forwarding the original Authorization header.
    """

    def __init__(
        self,
        *,
        scope_claim_names: tuple[str, ...] = ("scp", "scope", "roles"),
        subject_claim_names: tuple[str, ...] = ("oid", "sub"),
    ) -> None:
        super().__init__()
        self.scope_claim_names = scope_claim_names
        self.subject_claim_names = subject_claim_names

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or len(token) > 16_384:
            return None
        try:
            claims = decode_jwt_payload(token)
        except (TypeError, ValueError):
            return None
        if not isinstance(claims, dict):
            return None

        subject = _first_string_claim(claims, self.subject_claim_names)
        if subject is None:
            return None

        scopes: list[str] = []
        for claim_name in self.scope_claim_names:
            parsed = parse_scopes(claims.get(claim_name)) or []
            for scope in parsed:
                if scope not in scopes:
                    scopes.append(scope)

        if claims.get("exp") is None:
            return None
        try:
            expires_at = int(claims["exp"])
        except (TypeError, ValueError):
            return None

        client_id = _first_string_claim(claims, ("azp", "appid")) or subject
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=expires_at,
            subject=subject,
            claims=claims,
        )


def _first_string_claim(claims: dict[str, Any], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = claims.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class ServiceNowAuthenticator(ABC):
    @abstractmethod
    async def headers(self, context: AuthorizationContext | None = None) -> dict[str, str]: ...

    async def aclose(self) -> None:
        return None


class IntegrationTokenAuthenticator(ServiceNowAuthenticator):
    """Authenticate as the configured integration identity."""

    def __init__(self, token: str | None) -> None:
        self._token = token

    async def headers(self, context: AuthorizationContext | None = None) -> dict[str, str]:
        if context and context.delegated_token:
            return {"Authorization": f"Bearer {context.delegated_token}"}
        if not self._token:
            raise KnowledgeMcpError(
                ErrorCode.UNAUTHENTICATED, "ServiceNow authentication is not configured"
            )
        return {"Authorization": f"Bearer {self._token}"}


class ClientCredentialsAuthenticator(ServiceNowAuthenticator):
    """Obtain and cache a ServiceNow OAuth client-credentials access token."""

    def __init__(
        self,
        *,
        base_url: str,
        client_id: str,
        client_secret: str,
        token_path: str = "/oauth_token.do",
        scope: str | None = None,
        timeout: float = 10,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_path = token_path
        self._scope = scope
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            verify=system_ssl_context(),
        )
        self._access_token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()

    async def headers(self, context: AuthorizationContext | None = None) -> dict[str, str]:
        if context and context.delegated_token:
            return {"Authorization": f"Bearer {context.delegated_token}"}
        token = await self._get_access_token()
        return {"Authorization": f"Bearer {token}"}

    async def _get_access_token(self) -> str:
        if self._access_token and monotonic() < self._expires_at:
            return self._access_token
        async with self._lock:
            if self._access_token and monotonic() < self._expires_at:
                return self._access_token
            data = {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
            if self._scope:
                data["scope"] = self._scope
            try:
                response = await self._http_client.post(
                    self._token_path,
                    data=data,
                    headers={"Accept": "application/json"},
                )
            except httpx.TimeoutException as exc:
                raise KnowledgeMcpError(
                    ErrorCode.UPSTREAM_TIMEOUT, "ServiceNow OAuth token request timed out"
                ) from exc
            except httpx.RequestError as exc:
                raise KnowledgeMcpError(
                    ErrorCode.UPSTREAM_UNAVAILABLE, "ServiceNow OAuth endpoint is unavailable"
                ) from exc

            if response.status_code in (400, 401, 403):
                raise KnowledgeMcpError(
                    ErrorCode.UNAUTHENTICATED,
                    "ServiceNow rejected the OAuth client credentials",
                    status=response.status_code,
                )
            if response.status_code == 429:
                raise KnowledgeMcpError(
                    ErrorCode.RATE_LIMITED,
                    "ServiceNow OAuth rate limit was reached",
                    status=429,
                )
            if response.status_code >= 500:
                raise KnowledgeMcpError(
                    ErrorCode.UPSTREAM_UNAVAILABLE,
                    "ServiceNow OAuth endpoint is unavailable",
                    status=response.status_code,
                )
            if response.status_code >= 400:
                raise KnowledgeMcpError(
                    ErrorCode.UPSTREAM_ERROR,
                    "ServiceNow rejected the OAuth token request",
                    status=response.status_code,
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise KnowledgeMcpError(
                    ErrorCode.UPSTREAM_ERROR, "ServiceNow OAuth returned malformed JSON"
                ) from exc
            access_token = payload.get("access_token") if isinstance(payload, dict) else None
            if not isinstance(access_token, str):
                raise KnowledgeMcpError(
                    ErrorCode.UPSTREAM_ERROR,
                    "ServiceNow OAuth response omitted access_token",
                )
            token = access_token
            expires_in = payload.get("expires_in", 300)
            try:
                lifetime = max(float(expires_in), 1.0)
            except (TypeError, ValueError):
                lifetime = 300.0
            # Refresh shortly before expiry, while still caching very short-lived tokens.
            refresh_skew = min(30.0, lifetime * 0.1)
            self._access_token = token
            self._expires_at = monotonic() + lifetime - refresh_skew
            return token
