from starlette.testclient import TestClient

from servicenow_mcp.server import mcp_app


def test_http_health_endpoints_are_available_during_application_lifespan():
    with TestClient(mcp_app) as client:
        live = client.get("/mcp/live")
        health = client.get("/mcp/health")
        ready = client.get("/mcp/ready")

    assert live.status_code == 200
    assert live.json() == {
        "status": "healthy",
        "service": "servicenow-knowledge-mcp",
    }
    assert health.status_code == 200
    assert health.json() == {
        "status": "ready",
        "service": "servicenow-knowledge-mcp",
    }
    assert ready.status_code == 200
    assert ready.json() == health.json()
