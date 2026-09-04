"""
FastMCP server entry point.

Transport: streamable-http (compatible with AKS MCP / Azure AI Foundry).
Port:      8000

Run locally:
    python main.py

Or via uvicorn (for dev hot-reload):
    uv run uvicorn main:mcp_app --host 0.0.0.0 --port 8000 --reload
"""

import logging
import sys

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from app_telemetry import set_up_telemetry
from authentication import close_async_azure_credential
from config import settings
from runtime_state import (
    mark_lifespan_started,
    mark_lifespan_stopped,
    snapshot_runtime_state,
)
from tools.example_tool import example_mcp
from tools.health import health_mcp

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)
set_up_telemetry()


@lifespan
async def app_lifespan(server):
    """Manage generic server lifecycle hooks for diagnostics and cleanup."""
    mark_lifespan_started(server)
    logger.info(
        "Lifespan startup complete",
        extra={
            "service": settings.mcp_name,
            "environment": settings.environment,
            **snapshot_runtime_state(),
        },
    )
    try:
        yield {}
    finally:
        mark_lifespan_stopped()
        logger.info(
            "Lifespan shutdown complete",
            extra={
                "service": settings.mcp_name,
                "environment": settings.environment,
                **snapshot_runtime_state(),
            },
        )
        await close_async_azure_credential()


# ---------------------------------------------------------------------------
# Root MCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name=settings.mcp_name,
    instructions=(
        "You are connected to the ServiceNowAutomation MCP server. "
        "Use available tools to check health status and perform example operations."
    ),
    lifespan=app_lifespan,
)

# Mount tool collections
mcp.mount(health_mcp, namespace="health")
mcp.mount(example_mcp, namespace="example")


# ---------------------------------------------------------------------------
# ASGI app — exposed for uvicorn / AKS streamable-http transport
# ---------------------------------------------------------------------------

mcp_app = mcp.http_app(path="/mcp")


# ---------------------------------------------------------------------------
# Direct run (stdio or streamable-http depending on settings)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info(
        "Starting %s on %s:%s [%s]",
        settings.mcp_name,
        settings.mcp_host,
        settings.mcp_port,
        settings.mcp_transport,
    )
    mcp.run(
        transport=settings.mcp_transport,
        host=settings.mcp_host,
        port=settings.mcp_port,
    )
