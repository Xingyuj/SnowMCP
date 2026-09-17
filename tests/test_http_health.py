import httpx

from servicenowautomation_mcp.config import ServiceNowKnowledgeConfig
from servicenowautomation_mcp.server import create_mcp


async def test_http_health_endpoints_are_available_during_application_lifespan():
    server = create_mcp(config_provider=lambda: ServiceNowKnowledgeConfig(_env_file=None))
    app = server.http_app(path="/mcp", stateless_http=True)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ("/mcp/health", "/mcp/ready"):
            assert (await client.get(path)).status_code == 503

        async with app.router.lifespan_context(app):
            live = await client.get("/mcp/live")
            health = await client.get("/mcp/health")
            ready = await client.get("/mcp/ready")

        assert live.status_code == 200
        assert live.json() == {
            "status": "healthy",
            "service": "servicenowautomation-mcp",
        }
        assert health.status_code == 200
        assert health.json() == {
            "status": "ready",
            "service": "servicenowautomation-mcp",
        }
        assert ready.status_code == 200
        assert ready.json() == health.json()

        for path in ("/mcp/health", "/mcp/ready"):
            assert (await client.get(path)).status_code == 503
