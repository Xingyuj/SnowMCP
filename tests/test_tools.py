from fastmcp import Client
from fastmcp.server.auth import AccessToken, AuthContext, run_auth_checks

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
        "list_knowledge_categories",
        "get_knowledge_article",
        "get_knowledge_attachment",
    ]
    assert "ranked candidates" in tools[0].description
    assert "hierarchy" in tools[1].description
    assert "after search_knowledge" in tools[2].description
    assert "only when" in tools[3].description


async def test_all_fastmcp_tool_contracts_in_process():
    async with server_client() as client:
        search = await client.call_tool("search_knowledge", {"query": "access"})
        categories = await client.call_tool("list_knowledge_categories", {})
        article = await client.call_tool("get_knowledge_article", {"article_id": "article-1"})
        attachment = await client.call_tool(
            "get_knowledge_attachment",
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
        "list_knowledge_categories": CATEGORY_READ_SCOPE,
        "get_knowledge_article": ARTICLE_READ_SCOPE,
        "get_knowledge_attachment": ATTACHMENT_READ_SCOPE,
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
