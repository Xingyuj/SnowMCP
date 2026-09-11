import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from threading import Lock

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AuthCheck, TokenVerifier, require_scopes
from starlette.requests import Request
from starlette.responses import JSONResponse

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
        "ServiceNowAutomation",
        instructions="Retrieve authoritative enterprise Knowledge Articles without generating answers.",
        auth=build_apim_auth(config),
        lifespan=runtime.lifespan,
    )

    @server.tool(
        description=(
            "Use this tool to find relevant enterprise Knowledge Articles from a natural-language "
            "question or keywords. It returns ranked candidates and snippets, not complete article bodies."
        ),
        auth=_scope_check(config, SEARCH_KNOWLEDGE_SCOPE),
    )
    async def search_knowledge(
        query: str,
        limit: int | None = None,
        knowledge_base: str | None = None,
        language: str | None = None,
    ) -> KnowledgeSearchResponse:
        try:
            return await runtime.resolve_service().search_knowledge(
                query, limit, knowledge_base, language
            )
        except KnowledgeMcpError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None

    @server.tool(
        description=(
            "Use this tool to list all accessible ServiceNow Knowledge categories and their hierarchy. "
            "Results include category identifiers, labels, parent identifiers, and full paths."
        ),
        auth=_scope_check(config, CATEGORY_READ_SCOPE),
    )
    async def list_kb_categories() -> KnowledgeCategoriesResponse:
        try:
            return await runtime.resolve_service().list_knowledge_categories()
        except KnowledgeMcpError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None

    @server.tool(
        description=(
            "Retrieve complete canonical content and publication metadata for a Knowledge Article. "
            "Provide the ServiceNow article identifier as article_id."
        ),
        auth=_scope_check(config, ARTICLE_READ_SCOPE),
    )
    async def get_kb_article(article_id: str) -> KnowledgeArticle:
        try:
            return await runtime.resolve_service().get_knowledge_article(article_id)
        except KnowledgeMcpError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None

    @server.tool(
        description=(
            "Use this supporting tool only when a selected Knowledge Article references an attachment "
            "whose contents are required. It returns bounded base64 binary data and does not parse it."
        ),
        auth=_scope_check(config, ATTACHMENT_READ_SCOPE),
    )
    async def get_kb_article_attachment(
        article_sys_id: str, attachment_sys_id: str
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
