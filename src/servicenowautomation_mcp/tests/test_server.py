from fastmcp import Client

from main import mcp


async def test_server_exposes_expected_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert {tool.name for tool in tools} == {
        "health_health_check",
        "health_readiness",
        "health_liveness",
        "example_demo_tool",
    }
