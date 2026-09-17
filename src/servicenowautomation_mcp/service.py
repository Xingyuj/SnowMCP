import re

from .auth import AuthorizationContext
from .clients import KnowledgeBackend
from .config import ServiceNowKnowledgeConfig
from .errors import ErrorCode, KnowledgeMcpError
from .models import (
    KnowledgeArticle,
    KnowledgeAttachment,
    KnowledgeCategoriesResponse,
    KnowledgeSearchResponse,
)

# Attachment validation retains the existing compatibility-oriented identifier contract.
_IDENTIFIER = re.compile(r"^[^\s/\\?#]{1,255}$")
_ARTICLE_SYS_ID = re.compile(r"^[0-9a-fA-F]{32}$")
_ARTICLE_NUMBER = re.compile(r"^KB\d{1,20}$", re.ASCII)


class KnowledgeService:
    def __init__(self, client: KnowledgeBackend, config: ServiceNowKnowledgeConfig) -> None:
        self.client = client
        self.config = config

    async def search_knowledge(
        self,
        query: str,
        limit: int | None = None,
        knowledge_base: str | None = None,
        language: str | None = None,
        authorization: AuthorizationContext | None = None,
    ) -> KnowledgeSearchResponse:
        query = query.strip()
        if not query:
            raise KnowledgeMcpError(ErrorCode.INVALID_REQUEST, "query must not be blank")
        requested_limit = self.config.default_search_limit if limit is None else limit
        if requested_limit < 1 or requested_limit > self.config.max_search_limit:
            raise KnowledgeMcpError(
                ErrorCode.INVALID_REQUEST,
                f"limit must be between 1 and {self.config.max_search_limit}",
            )
        results = await self.client.search(
            query,
            requested_limit,
            _clean_optional(knowledge_base) or self.config.servicenow_knowledge_base,
            _clean_optional(language) or self.config.servicenow_language,
            authorization,
        )
        return KnowledgeSearchResponse(query=query, total=len(results), results=results)

    async def list_knowledge_categories(
        self,
        authorization: AuthorizationContext | None = None,
    ) -> KnowledgeCategoriesResponse:
        results = []
        offset = 0
        while True:
            page = await self.client.get_categories(
                self.config.category_page_size, offset, authorization
            )
            results.extend(page)
            if len(page) < self.config.category_page_size:
                break
            offset += len(page)
        return KnowledgeCategoriesResponse(total=len(results), results=results)

    async def get_knowledge_article(
        self, article_id: str, authorization: AuthorizationContext | None = None
    ) -> KnowledgeArticle:
        return await self.client.get_article(
            _validated_article_identifier(article_id), authorization
        )

    async def get_knowledge_attachment(
        self,
        article_sys_id: str,
        attachment_sys_id: str,
        authorization: AuthorizationContext | None = None,
    ) -> KnowledgeAttachment:
        return await self.client.get_attachment(
            _validated_identifier(article_sys_id, "article_sys_id"),
            _validated_identifier(attachment_sys_id, "attachment_sys_id"),
            authorization,
        )


def _clean_optional(value: str | None) -> str | None:
    cleaned = value.strip() if value else ""
    return cleaned or None


def _validated_identifier(value: str, name: str) -> str:
    cleaned = value.strip()
    if not _IDENTIFIER.fullmatch(cleaned):
        raise KnowledgeMcpError(ErrorCode.INVALID_REQUEST, f"{name} is invalid")
    return cleaned


def _validated_article_identifier(value: str) -> str:
    cleaned = value.strip()
    if not (_ARTICLE_SYS_ID.fullmatch(cleaned) or _ARTICLE_NUMBER.fullmatch(cleaned)):
        raise KnowledgeMcpError(
            ErrorCode.INVALID_REQUEST,
            "Invalid article identifier. Use search_knowledge first to obtain a valid article_id.",
        )
    return cleaned
