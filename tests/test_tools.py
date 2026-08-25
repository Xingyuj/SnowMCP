from fastmcp import Client

from servicenow_mcp.auth import AuthorizationContext
from servicenow_mcp.clients import KnowledgeClient
from servicenow_mcp.config import ServiceNowKnowledgeConfig
from servicenow_mcp.models import (
    KnowledgeArticle,
    KnowledgeAttachment,
    KnowledgeSearchCandidate,
)
from servicenow_mcp.server import create_mcp
from servicenow_mcp.service import KnowledgeService


class ToolClient(KnowledgeClient):
    async def search(
        self,
        query: str,
        limit: int,
        knowledge_base: str | None,
        language: str | None,
        authorization: AuthorizationContext | None = None,
    ) -> list[KnowledgeSearchCandidate]:
        return [KnowledgeSearchCandidate(id="article-1", title="Candidate", rank=1)]

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


def server_client() -> Client:
    config = ServiceNowKnowledgeConfig(servicenow_base_url="https://instance.example")
    return Client(create_mcp(KnowledgeService(ToolClient(), config)))


async def test_fastmcp_lists_only_the_three_retrieval_tools():
    async with server_client() as client:
        tools = await client.list_tools()
    assert [tool.name for tool in tools] == [
        "search_knowledge",
        "get_knowledge_article",
        "get_knowledge_attachment",
    ]
    assert "ranked candidates" in tools[0].description
    assert "after search_knowledge" in tools[1].description
    assert "only when" in tools[2].description


async def test_all_fastmcp_tool_contracts_in_process():
    async with server_client() as client:
        search = await client.call_tool("search_knowledge", {"query": "access"})
        article = await client.call_tool("get_knowledge_article", {"article_id": "article-1"})
        attachment = await client.call_tool(
            "get_knowledge_attachment",
            {"article_sys_id": "article-1", "attachment_sys_id": "attachment-1"},
        )
    assert search.structured_content is not None and search.structured_content["total"] == 1
    assert (
        article.structured_content is not None
        and article.structured_content["content"] == "Canonical content"
    )
    assert (
        attachment.structured_content is not None
        and attachment.structured_content["content_type"] == "application/pdf"
    )
