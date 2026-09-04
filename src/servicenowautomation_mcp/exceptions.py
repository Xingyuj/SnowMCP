"""
Custom exception definitions for the MCP server
"""


class MCPServerException(Exception):
    """Base exception for MCP server errors"""
    pass


class ConfigurationError(MCPServerException):
    """Raised when configuration is invalid or missing"""
    pass


class AuthenticationError(MCPServerException):
    """Raised when authentication fails"""
    pass


class ValidationError(MCPServerException):
    """Raised when input validation fails"""
    pass


class ToolExecutionError(MCPServerException):
    """Raised when a tool execution fails"""
    pass
