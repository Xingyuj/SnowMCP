from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AuthCheck, require_scopes
from mcp.types import ToolAnnotations
from pydantic import Field

from ..config import ServiceNowKnowledgeConfig
from ..errors import KnowledgeMcpError
from ..knowledge.models import (
    KnowledgeArticle,
    KnowledgeAttachment,
    KnowledgeCategoriesResponse,
    KnowledgeSearchResponse,
)
from ..runtime import ServiceRuntime
from ..scopes import (
    ARTICLE_READ_SCOPE,
    ATTACHMENT_READ_SCOPE,
    CATEGORY_READ_SCOPE,
    SEARCH_KNOWLEDGE_SCOPE,
)

_READ_ONLY_EXTERNAL_TOOL = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
_IDENTIFIER_PATTERN = r"^[^\s/\\?#]{1,255}$"


def _scope_check(config: ServiceNowKnowledgeConfig, scope: str) -> AuthCheck | None:
    return require_scopes(scope) if config.apim_auth_enabled else None


def register_knowledge_tools(
    server: FastMCP,
    runtime: ServiceRuntime,
    config: ServiceNowKnowledgeConfig,
) -> None:
    @server.tool(
        title="Search ServiceNow Knowledge",
        description=(
            "Primary entry point for general natural-language knowledge questions. Use this tool "
            "when no specific article_id is already known. Searches accessible ServiceNow "
            "Knowledge Articles and returns ranked candidates with article_id values and snippets, "
            "not canonical article content; retrieve a selected result with get_kb_article."
        ),
        annotations=_READ_ONLY_EXTERNAL_TOOL,
        auth=_scope_check(config, SEARCH_KNOWLEDGE_SCOPE),
    )
    async def search_knowledge(
        query: Annotated[
            str,
            Field(
                min_length=1,
                description="Natural-language question or keywords used to find Knowledge Articles.",
            ),
        ],
        limit: Annotated[
            int | None,
            Field(
                ge=1,
                description=(
                    "Maximum number of candidates to return. Uses the configured default when omitted "
                    "and cannot exceed the server-configured maximum."
                ),
            ),
        ] = None,
        knowledge_base: Annotated[
            str | None,
            Field(
                min_length=1,
                description=(
                    "Optional ServiceNow Knowledge Base identifier used to restrict the search."
                ),
            ),
        ] = None,
        language: Annotated[
            str | None,
            Field(
                min_length=1,
                description="Optional ServiceNow article language used to restrict the search.",
            ),
        ] = None,
    ) -> KnowledgeSearchResponse:
        try:
            return await runtime.resolve_service().search_knowledge(
                query, limit, knowledge_base, language
            )
        except KnowledgeMcpError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None

    @server.tool(
        title="List Knowledge Base Categories",
        description=(
            "Use only for category discovery, browsing, or choosing a search filter. Lists accessible "
            "ServiceNow Knowledge Base categories and their hierarchy; it does not return Knowledge "
            "Articles and is not the default entry point for a general knowledge question."
        ),
        annotations=_READ_ONLY_EXTERNAL_TOOL,
        auth=_scope_check(config, CATEGORY_READ_SCOPE),
    )
    async def list_kb_categories() -> KnowledgeCategoriesResponse:
        try:
            return await runtime.resolve_service().list_knowledge_categories()
        except KnowledgeMcpError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None

    @server.tool(
        title="Get Knowledge Base Article",
        description=(
            "Retrieve one specific ServiceNow Knowledge Article and its canonical content. Only call "
            "this tool when a valid article_id is already known, normally from search_knowledge. "
            "Do not use this tool for general natural-language search."
        ),
        annotations=_READ_ONLY_EXTERNAL_TOOL,
        auth=_scope_check(config, ARTICLE_READ_SCOPE),
    )
    async def get_kb_article(
        article_id: Annotated[
            str,
            Field(
                min_length=1,
                max_length=255,
                description=(
                    "Specific ServiceNow article sys_id (32 hexadecimal characters) or KB article "
                    "number, such as KB0012345. Pass results[].article_id from search_knowledge; "
                    "do not pass a natural-language question."
                ),
                examples=["9b4f5c1adb1230106a3e1b1f299619d2", "KB0012345"],
            ),
        ],
    ) -> KnowledgeArticle:
        try:
            return await runtime.resolve_service().get_knowledge_article(article_id)
        except KnowledgeMcpError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None

    @server.tool(
        title="Get Knowledge Base Article Attachment",
        description=(
            "Retrieve one specific attachment only when its article_sys_id and attachment_sys_id are "
            "already known and the attachment content is required. This is not a search or discovery "
            "tool. Returns size-limited base64 binary data and does not parse or interpret it."
        ),
        annotations=_READ_ONLY_EXTERNAL_TOOL,
        auth=_scope_check(config, ATTACHMENT_READ_SCOPE),
    )
    async def get_kb_article_attachment(
        article_sys_id: Annotated[
            str,
            Field(
                min_length=1,
                max_length=255,
                pattern=_IDENTIFIER_PATTERN,
                description="ServiceNow sys_id of the Knowledge Article that owns the attachment.",
            ),
        ],
        attachment_sys_id: Annotated[
            str,
            Field(
                min_length=1,
                max_length=255,
                pattern=_IDENTIFIER_PATTERN,
                description="ServiceNow sys_id of the attachment to retrieve.",
            ),
        ],
    ) -> KnowledgeAttachment:
        try:
            return await runtime.resolve_service().get_knowledge_attachment(
                article_sys_id, attachment_sys_id
            )
        except KnowledgeMcpError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None
