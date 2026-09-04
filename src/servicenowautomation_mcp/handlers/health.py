"""
Health Check Handlers
Kubernetes health probe implementations for liveness and readiness checks
"""

import logging
from typing import Any, Dict

from ..config import settings
from ..context import get_context

logger = logging.getLogger(__name__)


def health_check() -> Dict[str, Any]:
    """
    Liveness probe endpoint
    Returns simple status check indicating service is alive

    Returns:
        Dict containing health status
    """
    return {
        "status": "healthy",
        "service": settings.mcp_name,
    }


def readiness_check() -> Dict[str, Any]:
    """
    Readiness probe endpoint
    Checks if service is ready to handle requests

    Returns:
        Dict containing readiness status
    """
    return {
        "status": "ready",
        "service": settings.mcp_name,
        "environment": settings.environment,
    }


def liveness_check() -> Dict[str, Any]:
    """
    Liveness probe endpoint
    Returns detailed status check

    Returns:
        Dict containing liveness status
    """
    context = get_context()
    return {
        "status": "alive",
        "service": settings.mcp_name,
        "version": "1.0.0",
        "correlation_id": context.get_correlation_id(),
    }
