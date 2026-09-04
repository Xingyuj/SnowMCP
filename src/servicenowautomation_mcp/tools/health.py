"""
Health Check MCP Tools

Kubernetes health probe implementations for liveness and readiness checks.
"""

import logging
from typing import Any, Dict

from fastmcp import FastMCP

from config import settings
from context import get_context

logger = logging.getLogger(__name__)

health_mcp = FastMCP("health-tools")


@health_mcp.tool()
def health_check() -> Dict[str, Any]:
    """
    Liveness probe - returns health status
    Indicates if service is alive and running.
    """
    logger.info("Tool called: health_check")
    result = {
        "status": "healthy",
        "service": settings.mcp_name,
    }
    return result


@health_mcp.tool()
def readiness() -> Dict[str, Any]:
    """
    Readiness probe - checks if service is ready to handle requests
    """
    logger.info("Tool called: readiness")
    result = {
        "status": "ready",
        "service": settings.mcp_name,
        "environment": settings.environment,
    }
    return result


@health_mcp.tool()
def liveness() -> Dict[str, Any]:
    """
    Liveness probe - returns detailed status
    """
    logger.info("Tool called: liveness")
    context = get_context()
    result = {
        "status": "live",
        "service": settings.mcp_name,
        "environment": settings.environment,
        "request_id": context.get_request_id(),
        "correlation_id": context.get_correlation_id(),
    }
    return result
