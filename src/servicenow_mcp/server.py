import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from threading import Lock
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AuthCheck, TokenVerifier, require_scopes
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from servicenowautomation_mcp.app_telemetry import set_up_telemetry

from .auth import (
    ApimClaimsTokenVerifier,
    ClientCredentialsAuthenticator,
    IntegrationTokenAuthenticator,
    ServiceNowAuthenticator,
)
from .clients import ServiceNowKnowledgeApiClient
from .config import ServiceNowKnowledgeConfig, get_config
from .errors import KnowledgeMcpError
from .models import (
    KnowledgeArticle,
    KnowledgeAttachment,
    KnowledgeCategoriesResponse,
    KnowledgeSearchResponse,
)
from .scopes import (
    ARTICLE_READ_SCOPE,
    ATTACHMENT_READ_SCOPE,
    CATEGORY_READ_SCOPE,
    SEARCH_KNOWLEDGE_SCOPE,
)
from .service import KnowledgeService

log = logging.getLogger("servicenowautomation_mcp")

SERVER_NAME = "ServiceNow MCP"
SERVER_INSTRUCTIONS = (
    "Provides read-only access to authoritative enterprise knowledge stored in ServiceNow. "
    "For a general natural-language knowledge question, use search_knowledge first unless a "
    "specific article identifier is already known. Use get_kb_article only with an article_id "
    "returned by search_knowledge or otherwise explicitly supplied. "
    "Treat search results as candidates rather than complete article content. When a caller "
    "provides a specific article identifier, prefer direct retrieval over an unnecessary search. "
    "Use list_kb_categories only for category discovery or filtering. Retrieve attachments only "
    "when they are relevant to a selected article and explicitly needed. "
    "Base responses only on records returned by ServiceNow, preserve article identifiers and "
    "relevant source metadata for traceability, and clearly report missing, inaccessible, or "
    "incomplete information instead of inventing content."
)
_READ_ONLY_EXTERNAL_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
_IDENTIFIER_PATTERN = r"^[^\s/\\?#]{1,255}$"


def build_service(
    config: ServiceNowKnowledgeConfig,
) -> tuple[KnowledgeService, ServiceNowKnowledgeApiClient]:
    config.validate_runtime()
    authenticator: ServiceNowAuthenticator
    if config.servicenow_access_token:
        authenticator = IntegrationTokenAuthenticator(
            config.servicenow_access_token.get_secret_value()
        )
    else:
        assert config.servicenow_client_id is not None
        assert config.servicenow_client_secret is not None
        authenticator = ClientCredentialsAuthenticator(
            base_url=config.servicenow_base_url,
            client_id=config.servicenow_client_id,
            client_secret=config.servicenow_client_secret.get_secret_value(),
            token_path=config.servicenow_oauth_token_path,
            scope=config.servicenow_oauth_scope,
            timeout=config.request_timeout_seconds,
        )
    client = ServiceNowKnowledgeApiClient(config, authenticator)
    return KnowledgeService(client, config), client


def build_apim_auth(config: ServiceNowKnowledgeConfig) -> TokenVerifier | None:
    """Trust user-token claims only after APIM has validated and forwarded the token."""
    config.validate_apim_auth()
    if not config.apim_auth_enabled:
        return None
    return ApimClaimsTokenVerifier(
        scope_claim_names=config.apim_scope_claims,
        subject_claim_names=config.apim_subject_claims,
    )


class _ServiceRuntime:
    """Own the lazily initialized service and its client lifecycle."""

    def __init__(
        self,
        config: ServiceNowKnowledgeConfig,
        service: KnowledgeService | None,
    ) -> None:
        self._config = config
        self._state: dict[str, object] = {"service": service}
        self._lock = Lock()
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    @asynccontextmanager
    async def lifespan(self, _: FastMCP) -> AsyncIterator[dict[str, object]]:
        set_up_telemetry(
            connection_string=self._config.applicationinsights_connection_string,
            service_name="servicenowautomation-mcp",
            environment=self._config.environment,
        )
        self._ready = True
        try:
            yield self._state
        finally:
            self._ready = False
            owned_client = self._state.get("owned_client")
            if isinstance(owned_client, ServiceNowKnowledgeApiClient):
                await owned_client.aclose()

    def resolve_service(self) -> KnowledgeService:
        current = self._state.get("service")
        if isinstance(current, KnowledgeService):
            return current
        with self._lock:
            current = self._state.get("service")
            if isinstance(current, KnowledgeService):
                return current
            current, client = build_service(self._config)
            self._state["service"] = current
            self._state["owned_client"] = client
            return current


def _scope_check(config: ServiceNowKnowledgeConfig, scope: str) -> AuthCheck | None:
    return require_scopes(scope) if config.apim_auth_enabled else None


def create_mcp(
    service: KnowledgeService | None = None,
    config_provider: Callable[[], ServiceNowKnowledgeConfig] = get_config,
) -> FastMCP:
    config = config_provider()
    runtime = _ServiceRuntime(config, service)

    server = FastMCP(
        SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        auth=build_apim_auth(config),
        lifespan=runtime.lifespan,
    )

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

    @server.custom_route("/mcp/live", methods=["GET"])
    async def health_live(_: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "servicenowautomation-mcp"})

    @server.custom_route("/mcp/health", methods=["GET"])
    @server.custom_route("/mcp/ready", methods=["GET"])
    async def health_ready(_: Request) -> JSONResponse:
        is_ready = runtime.ready
        return JSONResponse(
            {
                "status": "ready" if is_ready else "not_ready",
                "service": "servicenowautomation-mcp",
            },
            status_code=200 if is_ready else 503,
        )

    return server


mcp = create_mcp()
mcp_app = mcp.http_app(path="/mcp", stateless_http=True)


def main() -> None:
    config = get_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    mcp.run(
        transport="streamable-http",
        host=config.host,
        port=config.port,
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
