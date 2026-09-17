import logging
from collections.abc import Callable

from fastmcp import FastMCP
from fastmcp.server.auth import TokenVerifier

from .config import ServiceNowKnowledgeConfig, get_config
from .health_routes import register_health_routes
from .knowledge.service import KnowledgeService
from .runtime import ServiceRuntime, build_service
from .security.apim import ApimClaimsTokenVerifier
from .telemetry import set_up_telemetry
from .tools import register_knowledge_tools

__all__ = [
    "SERVER_INSTRUCTIONS",
    "SERVER_NAME",
    "build_apim_auth",
    "build_service",
    "create_mcp",
    "main",
    "mcp",
    "mcp_app",
]

SERVER_NAME = "ServiceNow Automation MCP"
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
    runtime = ServiceRuntime(
        config,
        service,
        telemetry_setup=set_up_telemetry,
        service_builder=build_service,
    )
    server = FastMCP(
        SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        auth=build_apim_auth(config),
        lifespan=runtime.lifespan,
    )
    register_knowledge_tools(server, runtime, config)
    register_health_routes(server, runtime)
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
