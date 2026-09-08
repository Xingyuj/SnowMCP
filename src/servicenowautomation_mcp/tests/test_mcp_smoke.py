"""
Basic smoke tests for the FastMCP server.
"""

import sys

import pytest
from fastmcp import Client
from starlette.testclient import TestClient


@pytest.fixture
def mcp_client():
    """In-process test client, no HTTP required."""
    sys.path.insert(0, ".")
    from main import mcp

    return Client(mcp)


@pytest.mark.asyncio
async def test_health_check(mcp_client):
    async with mcp_client:
        result = await mcp_client.call_tool("health_health_check", {})
        assert "healthy" in result.content[0].text


@pytest.mark.asyncio
async def test_readiness(mcp_client):
    async with mcp_client:
        result = await mcp_client.call_tool("health_readiness", {})
        assert "ready" in result.content[0].text


@pytest.mark.asyncio
async def test_liveness(mcp_client):
    async with mcp_client:
        result = await mcp_client.call_tool("health_liveness", {})
        assert "live" in result.content[0].text


@pytest.mark.asyncio
async def test_demo_tool(mcp_client):
    async with mcp_client:
        result = await mcp_client.call_tool(
            "example_demo_tool",
            {
                "message": "sample-message",
                "extra_context": "sample-context",
            },
        )
        assert "Processed: sample-message" in result.content[0].text
        assert "Context: sample-context" in result.content[0].text


def test_http_liveness():
    from main import mcp_app

    with TestClient(mcp_app) as client:
        response = client.get("/mcp/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "servicenowautomation-mcp",
    }


def test_http_readiness():
    from main import mcp_app

    with TestClient(mcp_app) as client:
        response = client.get("/mcp/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "servicenowautomation-mcp",
        "environment": "development",
    }
