from typing import Any

import pytest

from servicenow_mcp.auth import AuthorizationContext
from servicenow_mcp.clients import KnowledgeClient
from servicenow_mcp.config import ServiceNowKnowledgeConfig
from servicenow_mcp.errors import ErrorCode, KnowledgeMcpError
from servicenow_mcp.models import KnowledgeArticle, KnowledgeAttachment, KnowledgeSearchCandidate
from servicenow_mcp.service import KnowledgeService


class RecordingClient(KnowledgeClient):
    def __init__(self) -> None:
        self.search_args: tuple[Any, ...] | None = None

    async def search(
        self,
        query: str,
        limit: int,
        knowledge_base: str | None,
        language: str | None,
        authorization: AuthorizationContext | None = None,
    ) -> list[KnowledgeSearchCandidate]:
        self.search_args = (query, limit, knowledge_base, language, authorization)
        return [KnowledgeSearchCandidate(id="1", title="Candidate", rank=1)]

    async def get_article(
        self, article_id: str, authorization: AuthorizationContext | None = None
    ) -> KnowledgeArticle:
        return KnowledgeArticle(id=article_id, title="Article", content="Body")

    async def get_attachment(
        self, article_id: str, attachment_id: str, authorization: AuthorizationContext | None = None
    ) -> KnowledgeAttachment:
        return KnowledgeAttachment(
            article_id=article_id,
            attachment_id=attachment_id,
            content_type="application/octet-stream",
            size_bytes=0,
            content_base64="",
        )


def service() -> tuple[KnowledgeService, RecordingClient]:
    client = RecordingClient()
    config = ServiceNowKnowledgeConfig(
        servicenow_base_url="https://instance.example",
        default_search_limit=3,
        max_search_limit=5,
        servicenow_knowledge_base="default-base",
        servicenow_language="en",
    )
    return KnowledgeService(client, config), client


@pytest.mark.asyncio
async def test_search_defaults_and_explicit_scope():
    target, client = service()
    result = await target.search_knowledge("  access  ")
    assert result.total == 1
    assert client.search_args is not None and client.search_args[:4] == (
        "access",
        3,
        "default-base",
        "en",
    )
    await target.search_knowledge("access", 2, "another-base", "fr")
    assert client.search_args is not None and client.search_args[:4] == (
        "access",
        2,
        "another-base",
        "fr",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("query", "limit"), [(" ", None), ("valid", 0), ("valid", 6)])
async def test_search_validation(query: str, limit: int | None):
    target, _ = service()
    with pytest.raises(KnowledgeMcpError) as exc:
        await target.search_knowledge(query, limit)
    assert exc.value.code == ErrorCode.INVALID_REQUEST


@pytest.mark.asyncio
async def test_article_and_attachment_identifier_validation():
    target, _ = service()
    assert (await target.get_knowledge_article("KB001")).id == "KB001"
    assert (
        await target.get_knowledge_attachment("article-1", "attachment-1")
    ).attachment_id == "attachment-1"
    for invalid in ("", "has space", "path/segment"):
        with pytest.raises(KnowledgeMcpError):
            await target.get_knowledge_article(invalid)
