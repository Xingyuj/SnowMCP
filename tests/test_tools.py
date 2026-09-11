import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from fastmcp import Client
from fastmcp.server.auth import AccessToken, AuthContext, run_auth_checks

import servicenow_mcp.server as server_module
from servicenow_mcp.auth import AuthorizationContext
from servicenow_mcp.clients import KnowledgeBackend
from servicenow_mcp.config import ServiceNowKnowledgeConfig
from servicenow_mcp.models import (
    KnowledgeArticle,
    KnowledgeAttachment,
    KnowledgeCategory,
    KnowledgeSearchCandidate,
)
from servicenow_mcp.scopes import (
    ARTICLE_READ_SCOPE,
    ATTACHMENT_READ_SCOPE,
    CATEGORY_READ_SCOPE,
    SEARCH_KNOWLEDGE_SCOPE,
)
from servicenow_mcp.server import create_mcp
from servicenow_mcp.service import KnowledgeService

TEST_SERVICENOW_BASE_URL = "https://instance.example"


class ToolClient(KnowledgeBackend):
    async def search(
        self,
        query: str,
        limit: int,
        knowledge_base: str | None,
        language: str | None,
        authorization: AuthorizationContext | None = None,
    ) -> list[KnowledgeSearchCandidate]:
        return [KnowledgeSearchCandidate(id="article-1", title="Candidate", rank=1)]

    async def get_categories(
        self,
        limit: int,
        offset: int,
        authorization: AuthorizationContext | None = None,
    ) -> list[KnowledgeCategory]:
        return (
            [KnowledgeCategory(id="category-1", label="Workplace", active=True)]
            if offset == 0
            else []
        )

    async def get_article(
        self, article_id: str, authorization: AuthorizationContext | None = None
    ) -> KnowledgeArticle:
        return KnowledgeArticle(id=article_id, title="Article", content="Canonical content")

    async def get_attachment(
        self,
        article_id: str,
        attachment_id: str,
        authorization: AuthorizationContext | None = None,
    ) -> KnowledgeAttachment:
        return KnowledgeAttachment(
            article_id=article_id,
            attachment_id=attachment_id,
            filename="guide.pdf",
            content_type="application/pdf",
            size_bytes=3,
            content_base64="YWJj",
        )


def server_client(config: ServiceNowKnowledgeConfig | None = None) -> Client:
    config = config or ServiceNowKnowledgeConfig(servicenow_base_url=TEST_SERVICENOW_BASE_URL)
    return Client(create_mcp(KnowledgeService(ToolClient(), config)))


async def test_fastmcp_lists_all_retrieval_tools():
    async with server_client() as client:
        tools = await client.list_tools()
    assert [tool.name for tool in tools] == [
        "search_knowledge",
        "list_kb_categories",
        "get_kb_article",
        "get_kb_article_attachment",
    ]
    assert [tool.title for tool in tools] == [
        "Search ServiceNow Knowledge",
        "List Knowledge Base Categories",
        "Get Knowledge Base Article",
        "Get Knowledge Base Article Attachment",
    ]
    assert "ranked article candidates" in tools[0].description
    assert "does not return Knowledge Articles" in tools[1].description
    assert "article sys_id or article number" in tools[2].description
    assert "does not parse or interpret" in tools[3].description


async def test_fastmcp_tool_metadata_and_schemas_are_complete():
    async with server_client() as client:
        tools = await client.list_tools()

    expected_required_inputs = {
        "search_knowledge": {"query"},
        "list_kb_categories": set(),
        "get_kb_article": {"article_id"},
        "get_kb_article_attachment": {"article_sys_id", "attachment_sys_id"},
    }
    expected_required_outputs = {
        "search_knowledge": {"query", "total", "results"},
        "list_kb_categories": {"total", "results"},
        "get_kb_article": {"id", "title", "content"},
        "get_kb_article_attachment": {
            "article_id",
            "attachment_id",
            "content_type",
            "size_bytes",
            "content_base64",
        },
    }

    for tool in tools:
        assert tool.description
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.idempotentHint is True
        assert tool.annotations.openWorldHint is True

        assert tool.inputSchema["additionalProperties"] is False
        assert set(tool.inputSchema.get("required", [])) == expected_required_inputs[tool.name]
        _assert_schema_property_descriptions(tool.inputSchema)

        assert tool.outputSchema is not None
        assert tool.outputSchema["additionalProperties"] is False
        assert set(tool.outputSchema["required"]) == expected_required_outputs[tool.name]
        _assert_schema_property_descriptions(tool.outputSchema)

    search_schema = tools[0].inputSchema["properties"]
    assert search_schema["query"]["minLength"] == 1
    assert search_schema["limit"]["anyOf"][0]["minimum"] == 1
    article_id_schema = tools[2].inputSchema["properties"]["article_id"]
    assert article_id_schema["maxLength"] == 255
    assert article_id_schema["pattern"] == r"^[^\s/\\?#]{1,255}$"
    attachment_output = tools[3].outputSchema["properties"]
    assert attachment_output["content_base64"]["contentEncoding"] == "base64"


def _assert_schema_property_descriptions(schema: dict[str, object]) -> None:
    properties = schema.get("properties", {})
    assert isinstance(properties, dict)
    for property_schema in properties.values():
        assert isinstance(property_schema, dict)
        assert property_schema.get("description")
        items = property_schema.get("items")
        if isinstance(items, dict):
            _assert_schema_property_descriptions(items)


async def test_all_fastmcp_tool_contracts_in_process():
    async with server_client() as client:
        search = await client.call_tool("search_knowledge", {"query": "access"})
        categories = await client.call_tool("list_kb_categories", {})
        article = await client.call_tool("get_kb_article", {"article_id": "article-1"})
        attachment = await client.call_tool(
            "get_kb_article_attachment",
            {"article_sys_id": "article-1", "attachment_sys_id": "attachment-1"},
        )
    assert search.structured_content is not None and search.structured_content["total"] == 1
    assert (
        categories.structured_content is not None
        and categories.structured_content["results"][0]["label"] == "Workplace"
    )
    assert (
        article.structured_content is not None
        and article.structured_content["content"] == "Canonical content"
    )
    assert (
        attachment.structured_content is not None
        and attachment.structured_content["content_type"] == "application/pdf"
    )


async def test_every_tool_requires_its_own_scope_when_apim_auth_is_enabled():
    config = ServiceNowKnowledgeConfig(
        apim_auth_enabled=True,
    )
    server = create_mcp(
        KnowledgeService(ToolClient(), config),
        config_provider=lambda: config,
    )
    expected_scopes = {
        "search_knowledge": SEARCH_KNOWLEDGE_SCOPE,
        "list_kb_categories": CATEGORY_READ_SCOPE,
        "get_kb_article": ARTICLE_READ_SCOPE,
        "get_kb_article_attachment": ATTACHMENT_READ_SCOPE,
    }

    for tool_name, required_scope in expected_scopes.items():
        tool = await server._local_provider.get_tool(tool_name)
        assert tool is not None and tool.auth is not None
        allowed = AuthContext(
            token=AccessToken(token="allowed", client_id="test", scopes=[required_scope]),
            component=tool,
        )
        denied = AuthContext(
            token=AccessToken(token="denied", client_id="test", scopes=["some.other.scope"]),
            component=tool,
        )
        assert await run_auth_checks(tool.auth, allowed)
        assert not await run_auth_checks(tool.auth, denied)


def test_concurrent_first_calls_build_one_service(monkeypatch):
    config = ServiceNowKnowledgeConfig(servicenow_base_url=TEST_SERVICENOW_BASE_URL)
    service = KnowledgeService(ToolClient(), config)
    build_count = 0

    def slow_build_service(_config):
        nonlocal build_count
        time.sleep(0.05)
        build_count += 1
        return service, object()

    monkeypatch.setattr(server_module, "build_service", slow_build_service)
    server = create_mcp(config_provider=lambda: config)
    tool = asyncio.run(server._local_provider.get_tool("search_knowledge"))
    assert tool is not None

    def call_search():
        return asyncio.run(tool.run({"query": "access"}))

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: call_search(), range(8)))

    assert len(results) == 8
    assert build_count == 1
