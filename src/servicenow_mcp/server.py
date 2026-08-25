import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from .auth import IntegrationTokenAuthenticator
from .clients import ServiceNowKnowledgeClient
from .config import ServiceNowKnowledgeConfig, get_config
from .errors import KnowledgeMcpError
from .models import KnowledgeArticle, KnowledgeAttachment, KnowledgeSearchResponse
from .service import KnowledgeService

log = logging.getLogger("servicenow_knowledge_mcp")


def build_service(
    config: ServiceNowKnowledgeConfig,
) -> tuple[KnowledgeService, ServiceNowKnowledgeClient]:
    config.validate_runtime()
    token = (
        config.servicenow_access_token.get_secret_value()
        if config.servicenow_access_token
        else None
    )
    client = ServiceNowKnowledgeClient(config, IntegrationTokenAuthenticator(token))
    return KnowledgeService(client, config), client


def create_mcp(
    service: KnowledgeService | None = None,
    config_provider: Callable[[], ServiceNowKnowledgeConfig] = get_config,
) -> FastMCP:
    state: dict[str, object] = {"service": service}

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[dict[str, object]]:
        try:
            yield state
        finally:
            owned_client = state.get("owned_client")
            if isinstance(owned_client, ServiceNowKnowledgeClient):
                await owned_client.aclose()

    server = FastMCP(
        "ServiceNow Knowledge",
        instructions="Retrieve authoritative enterprise Knowledge Articles without generating answers.",
        lifespan=lifespan,
    )

    def resolve_service() -> KnowledgeService:
        current = state.get("service")
        if isinstance(current, KnowledgeService):
            return current
        current, client = build_service(config_provider())
        state["service"] = current
        state["owned_client"] = client
        return current

    @server.tool(
        description=(
            "Use this tool to find relevant enterprise Knowledge Articles from a natural-language "
            "question or keywords. It returns ranked candidates and snippets, not complete article bodies."
        )
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
            "Use this tool after search_knowledge identifies a relevant Knowledge Article and complete "
            "canonical content and publication metadata are needed for grounding."
        )
    )
    async def get_knowledge_article(article_id: str) -> KnowledgeArticle:
        try:
            return await resolve_service().get_knowledge_article(article_id)
        except KnowledgeMcpError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from None

    @server.tool(
        description=(
            "Use this supporting tool only when a selected Knowledge Article references an attachment "
            "whose contents are required. It returns bounded base64 binary data and does not parse it."
        )
    )
    async def get_knowledge_attachment(
        article_sys_id: str, attachment_sys_id: str
    ) -> KnowledgeAttachment:
        try:
            return await resolve_service().get_knowledge_attachment(
                article_sys_id, attachment_sys_id
            )
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
    mcp.run(transport=config.transport, host=config.host, port=config.port, stateless_http=True)


if __name__ == "__main__":
    main()
