from starlette.testclient import TestClient

from servicenowautomation_mcp.server import mcp_app


def test_http_health_endpoints_are_available_during_application_lifespan():
    client = TestClient(mcp_app)

    for path in ("/mcp/health", "/mcp/ready"):
        assert client.get(path).status_code == 503

    with client:
        live = client.get("/mcp/live")
        health = client.get("/mcp/health")
        ready = client.get("/mcp/ready")

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
        assert client.get(path).status_code == 503
