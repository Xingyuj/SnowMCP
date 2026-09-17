from typing import Any

import pytest

from servicenowautomation_mcp.config import ServiceNowKnowledgeConfig
from servicenowautomation_mcp.errors import ErrorCode, KnowledgeMcpError
from servicenowautomation_mcp.knowledge.client import KnowledgeBackend
from servicenowautomation_mcp.knowledge.models import (
    KnowledgeArticle,
    KnowledgeAttachment,
    KnowledgeCategory,
    KnowledgeSearchCandidate,
)
from servicenowautomation_mcp.knowledge.service import KnowledgeService
from servicenowautomation_mcp.security.servicenow_auth import AuthorizationContext


class RecordingClient(KnowledgeBackend):
    def __init__(self) -> None:
        self.search_args: tuple[Any, ...] | None = None
        self.category_calls: list[tuple[int, int, AuthorizationContext | None]] = []
        self.article_calls: list[str] = []

    async def search(
        self,
        query: str,
        limit: int,
        knowledge_base: str | None,
        language: str | None,
        authorization: AuthorizationContext | None = None,
    ) -> list[KnowledgeSearchCandidate]:
        self.search_args = (query, limit, knowledge_base, language, authorization)
        return [
            KnowledgeSearchCandidate(
                id="9b4f5c1adb1230106a3e1b1f299619d2", title="Candidate", rank=1
            )
        ]

    async def get_categories(
        self,
        limit: int,
        offset: int,
        authorization: AuthorizationContext | None = None,
    ) -> list[KnowledgeCategory]:
        self.category_calls.append((limit, offset, authorization))
        if offset == 0:
            return [
                KnowledgeCategory(id=str(index), label=f"Category {index}")
                for index in range(limit)
            ]
        if offset == limit:
            return [KnowledgeCategory(id="last", label="Last category")]
        return []

    async def get_article(
        self, article_id: str, authorization: AuthorizationContext | None = None
    ) -> KnowledgeArticle:
        self.article_calls.append(article_id)
        return KnowledgeArticle(id=article_id, title="Article", content="Body")

    async def get_attachment(
        self,
        article_id: str,
        attachment_id: str,
        authorization: AuthorizationContext | None = None,
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
        _env_file=None,
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
async def test_natural_language_question_is_valid_search_input():
    target, client = service()

    result = await target.search_knowledge("what can i do to reset password")

    assert result.query == "what can i do to reset password"
    assert client.search_args is not None
    assert client.search_args[0] == "what can i do to reset password"


@pytest.mark.asyncio
@pytest.mark.parametrize(("query", "limit"), [(" ", None), ("valid", 0), ("valid", 6)])
async def test_search_validation(query: str, limit: int | None):
    target, _ = service()
    with pytest.raises(KnowledgeMcpError) as exc:
        await target.search_knowledge(query, limit)
    assert exc.value.code == ErrorCode.INVALID_REQUEST


@pytest.mark.asyncio
async def test_categories_are_automatically_paginated():
    target, client = service()
    target.config.category_page_size = 2
    result = await target.list_knowledge_categories()
    assert result.total == 3
    assert [item.label for item in result.results] == [
        "Category 0",
        "Category 1",
        "Last category",
    ]
    assert [call[:2] for call in client.category_calls] == [(2, 0), (2, 2)]


@pytest.mark.asyncio
async def test_article_and_attachment_identifier_validation():
    target, _ = service()
    assert (await target.get_knowledge_article("KB0012345")).id == "KB0012345"
    assert (
        await target.get_knowledge_attachment("article-1", "attachment-1")
    ).attachment_id == "attachment-1"
    for invalid in ("", "has space", "path/segment"):
        with pytest.raises(KnowledgeMcpError):
            await target.get_knowledge_article(invalid)
        with pytest.raises(KnowledgeMcpError):
            await target.get_knowledge_attachment("article-1", invalid)

    for invalid_article_number in ("KB123456", "KB12345678", "kb1234567", "KB123456A"):
        with pytest.raises(KnowledgeMcpError):
            await target.get_knowledge_article(invalid_article_number)


@pytest.mark.asyncio
async def test_article_rejects_natural_language_with_search_guidance():
    target, client = service()

    for invalid in ("reset password", "password"):
        with pytest.raises(KnowledgeMcpError) as exc:
            await target.get_knowledge_article(invalid)
        assert exc.value.code == ErrorCode.INVALID_REQUEST
        assert exc.value.message == (
            "Invalid article identifier. Use a 32-character sys_id or KB followed by exactly "
            "7 digits. Use search_knowledge first to obtain a valid article_id."
        )

    assert client.article_calls == []
