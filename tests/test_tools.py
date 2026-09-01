from fastmcp import Client
from fastmcp.server.auth import AccessToken, AuthContext, run_auth_checks

from servicenow_mcp.auth import AuthorizationContext
from servicenow_mcp.clients import KnowledgeBackend
from servicenow_mcp.config import ServiceNowKnowledgeConfig
from servicenow_mcp.models import (
    KnowledgeArticle,
    KnowledgeCategory,
    KnowledgeSearchCandidate,
)
from servicenow_mcp.server import create_mcp
from servicenow_mcp.service import KnowledgeService


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


def server_client() -> Client:
    config = ServiceNowKnowledgeConfig(servicenow_base_url="https://instance.example")
    return Client(create_mcp(KnowledgeService(ToolClient(), config)))


async def test_fastmcp_lists_all_retrieval_tools():
    async with server_client() as client:
        tools = await client.list_tools()
    assert [tool.name for tool in tools] == [
        "search_knowledge",
        "list_knowledge_categories",
        "get_knowledge_article",
    ]
    assert "ranked candidates" in tools[0].description
    assert "hierarchy" in tools[1].description
    assert "after search_knowledge" in tools[2].description


async def test_all_fastmcp_tool_contracts_in_process():
    async with server_client() as client:
        search = await client.call_tool("search_knowledge", {"query": "access"})
        categories = await client.call_tool("list_knowledge_categories", {})
        article = await client.call_tool("get_knowledge_article", {"article_id": "article-1"})
    assert search.structured_content is not None and search.structured_content["total"] == 1
    assert (
        categories.structured_content is not None
        and categories.structured_content["results"][0]["label"] == "Workplace"
    )
    assert (
        article.structured_content is not None
        and article.structured_content["content"] == "Canonical content"
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
        "search_knowledge": config.mcp_search_scope,
        "list_knowledge_categories": config.mcp_category_read_scope,
        "get_knowledge_article": config.mcp_article_read_scope,
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
