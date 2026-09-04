"""
MCP Context Management
Manages request context, correlation IDs, and application state
"""

import logging
import uuid
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger(__name__)

# Context variables for request tracking
_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class MCPContext:
    """
    MCP Server Context Manager
    Handles request context, correlation IDs, and shared state
    """

    def __init__(self):
        """Initialize MCP context"""
        self.request_id: Optional[str] = None
        self.correlation_id: Optional[str] = None

    def set_request_id(self, request_id: Optional[str] = None) -> str:
        """
        Set request ID for correlation tracking

        Args:
            request_id: Request ID (generated if not provided)

        Returns:
            str: The set request ID
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        self.request_id = request_id
        _request_id_var.set(request_id)
        return request_id

    def get_request_id(self) -> Optional[str]:
        """Get current request ID"""
        return _request_id_var.get() or self.request_id

    def set_correlation_id(self, correlation_id: Optional[str] = None) -> str:
        """
        Set correlation ID for request tracking

        Args:
            correlation_id: Correlation ID (generated if not provided)

        Returns:
            str: The set correlation ID
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        self.correlation_id = correlation_id
        _correlation_id_var.set(correlation_id)
        return correlation_id

    def get_correlation_id(self) -> Optional[str]:
        """Get current correlation ID"""
        return _correlation_id_var.get() or self.correlation_id


# Global context instance
_context = MCPContext()


def get_context() -> MCPContext:
    """Get the global MCP context instance"""
    return _context


def reset_context():
    """Reset context (useful for testing)"""
    global _context
    _context = MCPContext()
    _request_id_var.set(None)
    _correlation_id_var.set(None)
