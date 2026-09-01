import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AuthCheck, TokenVerifier, require_scopes

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
    KnowledgeCategoriesResponse,
    KnowledgeSearchResponse,
)
from .service import KnowledgeService

log = logging.getLogger("servicenow_knowledge_mcp")


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


def create_mcp(
    service: KnowledgeService | None = None,
    config_provider: Callable[[], ServiceNowKnowledgeConfig] = get_config,
) -> FastMCP:
    config = config_provider()
    state: dict[str, object] = {"service": service}

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[dict[str, object]]:
        try:
            yield state
        finally:
            owned_client = state.get("owned_client")
            if isinstance(owned_client, ServiceNowKnowledgeApiClient):
                await owned_client.aclose()

    server = FastMCP(
        "ServiceNow Knowledge",
        instructions="Retrieve authoritative enterprise Knowledge Articles without generating answers.",
        auth=build_apim_auth(config),
        lifespan=lifespan,
    )

    def scope_check(scope: str) -> AuthCheck | None:
        return require_scopes(scope) if config.apim_auth_enabled else None

    def resolve_service() -> KnowledgeService:
        current = state.get("service")
        if isinstance(current, KnowledgeService):
            return current
        current, client = build_service(config)
        state["service"] = current
        state["owned_client"] = client
        return current

    @server.tool(
        description=(
            "Use this tool to find relevant enterprise Knowledge Articles from a natural-language "
            "question or keywords. It returns ranked candidates and snippets, not complete article bodies."
        ),
        auth=scope_check(config.mcp_search_scope),
    )
    async def search_knowledge(
        query: str,
        limit: int | None = None,
        knowledge_base: str | None = None,
        language: str | None = None,
    ) -> KnowledgeSearchResponse:
        try:
            return await resolve_service().search_knowledge(query, limit, knowledge_base, language)
        except KnowledgeMcpError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None

    @server.tool(
        description=(
            "Use this tool to list all accessible ServiceNow Knowledge categories and their hierarchy. "
            "Results include category identifiers, labels, parent identifiers, and full paths."
        ),
        auth=scope_check(config.mcp_category_read_scope),
    )
    async def list_knowledge_categories() -> KnowledgeCategoriesResponse:
        try:
            return await resolve_service().list_knowledge_categories()
        except KnowledgeMcpError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None

    @server.tool(
        description=(
            "Use this tool after search_knowledge identifies a relevant Knowledge Article and complete "
            "canonical content and publication metadata are needed for grounding."
        ),
        auth=scope_check(config.mcp_article_read_scope),
    )
    async def get_knowledge_article(article_id: str) -> KnowledgeArticle:
        try:
            return await resolve_service().get_knowledge_article(article_id)
        except KnowledgeMcpError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None

    return server


mcp = create_mcp()


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
