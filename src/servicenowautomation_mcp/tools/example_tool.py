"""
Example MCP Tool

Demonstrates tool definition pattern for the servicenowautomation-mcp server.
"""

import logging
from typing import Annotated, Optional

from fastmcp import FastMCP
from pydantic import Field

logger = logging.getLogger(__name__)

example_mcp = FastMCP("example-tools")


@example_mcp.tool()
def demo_tool(
    message: Annotated[str, Field(description="The message to process")],
    extra_context: Annotated[
        Optional[str], Field(description="Optional context for processing")
    ] = None,
) -> str:
    """
    Example tool demonstrating MCP tool patterns.
    Processes a message with optional context.
    """
    logger.info(f"Tool called: demo_tool with message={message}")

    result = f"Processed: {message}"
    if extra_context:
        result += f" | Context: {extra_context}"

    return result
