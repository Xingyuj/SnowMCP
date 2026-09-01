import base64
import json

import httpx
import pytest

from servicenow_mcp.auth import (
    ApimClaimsTokenVerifier,
    AuthorizationContext,
    ClientCredentialsAuthenticator,
)
from servicenow_mcp.config import ServiceNowKnowledgeConfig
from servicenow_mcp.errors import ErrorCode, KnowledgeMcpError
from servicenow_mcp.server import build_apim_auth


@pytest.mark.asyncio
async def test_client_credentials_fetches_and_caches_token():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/oauth_token.do"
        assert request.headers["content-type"].startswith("application/x-www-form-urlencoded")
        assert request.content.decode() == (
            "grant_type=client_credentials&client_id=client-id&"
            "client_secret=client-secret&scope=knowledge.read"
        )
        return httpx.Response(200, json={"access_token": "oauth-token", "expires_in": 1800})

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://instance.example"
    )
    authenticator = ClientCredentialsAuthenticator(
        base_url="https://instance.example",
        client_id="client-id",
        client_secret="client-secret",
        scope="knowledge.read",
        http_client=http_client,
    )

    assert await authenticator.headers() == {"Authorization": "Bearer oauth-token"}
    assert await authenticator.headers() == {"Authorization": "Bearer oauth-token"}
    assert len(requests) == 1
    await http_client.aclose()


@pytest.mark.asyncio
async def test_delegated_token_does_not_request_client_credentials_token():
    async def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("OAuth endpoint should not be called")

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://instance.example"
    )
    authenticator = ClientCredentialsAuthenticator(
        base_url="https://instance.example",
        client_id="client-id",
        client_secret="client-secret",
        http_client=http_client,
    )

    headers = await authenticator.headers(AuthorizationContext(delegated_token="user-token"))
    assert headers == {"Authorization": "Bearer user-token"}
    await http_client.aclose()


def test_apim_auth_builds_claims_adapter_without_jwt_key_configuration():
    config = ServiceNowKnowledgeConfig(apim_auth_enabled=True)
    assert isinstance(build_apim_auth(config), ApimClaimsTokenVerifier)


@pytest.mark.asyncio
async def test_apim_verifier_extracts_validated_claims_without_signature_verification():
    verifier = ApimClaimsTokenVerifier()
    token = _unsigned_test_jwt(
        {
            "oid": "user-object-id",
            "azp": "client-id",
            "scp": "knowledge.search knowledge.article.read",
            "roles": ["knowledge.category.read"],
            "exp": 2_000_000_000,
        }
    )

    access_token = await verifier.verify_token(token)

    assert access_token is not None
    assert access_token.subject == "user-object-id"
    assert access_token.client_id == "client-id"
    assert access_token.scopes == [
        "knowledge.search",
        "knowledge.article.read",
        "knowledge.category.read",
    ]
    assert access_token.expires_at == 2_000_000_000


@pytest.mark.asyncio
async def test_apim_verifier_rejects_malformed_token_or_missing_subject():
    verifier = ApimClaimsTokenVerifier()

    assert await verifier.verify_token("not-a-jwt") is None
    assert await verifier.verify_token(_unsigned_test_jwt({"scp": "knowledge.search"})) is None
    assert await verifier.verify_token(_unsigned_test_jwt({"sub": "user"})) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(401), ErrorCode.UNAUTHENTICATED),
        (httpx.Response(429), ErrorCode.RATE_LIMITED),
        (httpx.Response(503), ErrorCode.UPSTREAM_UNAVAILABLE),
        (httpx.Response(200, json={}), ErrorCode.UPSTREAM_ERROR),
    ],
)
async def test_client_credentials_error_mapping(response: httpx.Response, code: ErrorCode):
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: response),
        base_url="https://instance.example",
    )
    authenticator = ClientCredentialsAuthenticator(
        base_url="https://instance.example",
        client_id="client-id",
        client_secret="client-secret",
        http_client=http_client,
    )

    with pytest.raises(KnowledgeMcpError) as exc:
        await authenticator.headers()
    assert exc.value.code == code
    await http_client.aclose()


def _unsigned_test_jwt(claims: dict[str, object]) -> str:
    def encode(value: dict[str, object]) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{encode({'alg': 'RS256', 'typ': 'JWT'})}.{encode(claims)}.signature"
