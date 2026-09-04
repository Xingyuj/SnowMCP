from fastmcp import Client

from servicenow_mcp.server import create_mcp

async def test_server_exposes_expected_tools():
    server = create_mcp()

    async with Client(server) as client:
        tools = await client.list_tools()

    assert [tool.name for tool in tools] == [
        "search_knowledge",
        "get_knowledge_article",
    ]