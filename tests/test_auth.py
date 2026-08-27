import httpx
import pytest

from servicenow_mcp.auth import AuthorizationContext, ClientCredentialsAuthenticator
from servicenow_mcp.config import ServiceNowKnowledgeConfig
from servicenow_mcp.errors import ErrorCode, KnowledgeMcpError
from servicenow_mcp.server import build_mcp_auth


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


def test_mcp_auth_requires_one_key_issuer_and_audience():
    config = ServiceNowKnowledgeConfig(mcp_auth_enabled=True)
    with pytest.raises(ValueError, match="exactly one"):
        build_mcp_auth(config)

    config = ServiceNowKnowledgeConfig(
        mcp_auth_enabled=True,
        mcp_jwt_public_key="local-test-secret-that-is-at-least-32-bytes",
        mcp_jwt_algorithm="HS256",
    )
    with pytest.raises(ValueError, match="ISSUER.*AUDIENCE"):
        build_mcp_auth(config)


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
