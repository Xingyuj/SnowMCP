"""Compatibility entry point for the consolidated ServiceNowAutomation MCP package."""

from .server import main, mcp, mcp_app

__all__ = ["main", "mcp", "mcp_app"]


if __name__ == "__main__":
    main()
