from typing import Any

from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.utilities.auth import decode_jwt_payload, parse_scopes


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
