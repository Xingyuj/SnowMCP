import httpx
import pytest

from servicenow_mcp.auth import IntegrationTokenAuthenticator
from servicenow_mcp.clients import ServiceNowKnowledgeApiClient
from servicenow_mcp.config import ServiceNowKnowledgeConfig
from servicenow_mcp.errors import ErrorCode, KnowledgeMcpError


def config(**overrides: object) -> ServiceNowKnowledgeConfig:
    values = {
        "servicenow_base_url": "https://instance.example",
        "transient_retry_attempts": 0,
        "retry_backoff_seconds": 0,
        **overrides,
    }
    return ServiceNowKnowledgeConfig(**values)


def client(handler, **overrides: object) -> ServiceNowKnowledgeApiClient:
    settings = config(**overrides)
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url=settings.servicenow_base_url
    )
    return ServiceNowKnowledgeApiClient(
        settings, IntegrationTokenAuthenticator("test-token"), http_client
    )


@pytest.mark.asyncio
async def test_search_maps_ranked_candidates_and_scopes_request():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.url.params["query"] == "remote access"
        assert request.url.params["knowledge_base"] == "workplace"
        assert request.url.params["language"] == "en"
        assert "text" not in request.url.params["fields"]
        return httpx.Response(
            200,
            json={
                "result": {
                    "articles": [
                        {
                            "sys_id": "a1",
                            "number": "KB001",
                            "short_description": "Remote access",
                            "description": "Connection guidance",
                            "score": "0.9",
                            "kb_knowledge_base": {"display_value": "Workplace"},
                        },
                        {"sys_id": "a2", "title": "Troubleshooting", "score": 0.7},
                    ]
                }
            },
        )

    results = await client(handler).search("remote access", 2, "workplace", "en")
    assert [item.rank for item in results] == [1, 2]
    assert results[0].knowledge_base == "Workplace"
    assert results[0].score == 0.9


@pytest.mark.asyncio
async def test_search_empty_result():
    results = await client(lambda _: httpx.Response(200, json={"result": []})).search(
        "missing", 5, None, None
    )
    assert results == []


@pytest.mark.asyncio
async def test_get_categories_maps_hierarchy_and_pagination():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/now/table/kb_category"
        assert request.url.params["sysparm_limit"] == "2"
        assert request.url.params["sysparm_offset"] == "4"
        assert request.url.params["sysparm_query"] == "ORDERBYfull_category"
        assert "label" in request.url.params["sysparm_fields"]
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "sys_id": "category-1",
                        "label": "VPN",
                        "value": "vpn",
                        "parent_id": {"value": "category-parent", "display_value": "Network"},
                        "full_category": "IT > Network > VPN",
                        "active": "true",
                    }
                ]
            },
        )

    categories = await client(handler).get_categories(2, 4)
    assert categories[0].label == "VPN"
    assert categories[0].parent_id == "category-parent"
    assert categories[0].active is True


@pytest.mark.asyncio
async def test_categories_reject_malformed_response():
    with pytest.raises(KnowledgeMcpError) as exc:
        await client(lambda _: httpx.Response(200, json={"result": {}})).get_categories(10, 0)
    assert exc.value.code == ErrorCode.UPSTREAM_ERROR


@pytest.mark.asyncio
async def test_get_article_maps_content_and_status_metadata():
    raw = {
        "sys_id": "article-1",
        "number": "KB002",
        "short_description": "Policy",
        "article_body": "Canonical content",
        "workflow_state": "draft",
        "published": "2026-01-01",
        "valid_to": "2026-12-31",
        "sys_updated_on": "2026-06-01",
    }
    article = await client(
        lambda _: httpx.Response(200, json={"result": {"article": raw}})
    ).get_article("article-1")
    assert article.content == "Canonical content"
    assert article.workflow_state == "draft"
    assert article.valid_to == "2026-12-31"


@pytest.mark.asyncio
async def test_get_article_accepts_missing_optional_fields():
    article = await client(
        lambda _: httpx.Response(200, json={"result": {"sys_id": "article-1", "title": "Minimal"}})
    ).get_article("article-1")
    assert article.content == ""
    assert article.category is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, ErrorCode.UNAUTHENTICATED),
        (403, ErrorCode.FORBIDDEN),
        (404, ErrorCode.NOT_FOUND),
        (429, ErrorCode.RATE_LIMITED),
        (503, ErrorCode.UPSTREAM_UNAVAILABLE),
    ],
)
async def test_status_mapping(status: int, code: ErrorCode):
    with pytest.raises(KnowledgeMcpError) as exc:
        await client(lambda _: httpx.Response(status)).get_article("article-1")
    assert exc.value.code == code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, ErrorCode.UNAUTHENTICATED),
        (403, ErrorCode.FORBIDDEN),
        (429, ErrorCode.RATE_LIMITED),
        (500, ErrorCode.UPSTREAM_UNAVAILABLE),
    ],
)
async def test_search_status_mapping(status: int, code: ErrorCode):
    with pytest.raises(KnowledgeMcpError) as exc:
        await client(lambda _: httpx.Response(status)).search("query", 1, None, None)
    assert exc.value.code == code


@pytest.mark.asyncio
async def test_article_malformed_response():
    with pytest.raises(KnowledgeMcpError) as exc:
        await client(lambda _: httpx.Response(200, json={"result": []})).get_article("article-1")
    assert exc.value.code == ErrorCode.UPSTREAM_ERROR


@pytest.mark.asyncio
async def test_timeout_mapping():
    async def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    with pytest.raises(KnowledgeMcpError) as exc:
        await client(handler).search("query", 1, None, None)
    assert exc.value.code == ErrorCode.UPSTREAM_TIMEOUT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [httpx.Response(200, content=b"not-json"), httpx.Response(200, json={"unexpected": []})],
)
async def test_malformed_json(response: httpx.Response):
    with pytest.raises(KnowledgeMcpError) as exc:
        await client(lambda _: response).search("query", 1, None, None)
    assert exc.value.code == ErrorCode.UPSTREAM_ERROR
