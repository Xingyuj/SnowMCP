from starlette.testclient import TestClient

from main import mcp_app


def test_http_health_routes_follow_application_lifecycle():
    client = TestClient(mcp_app)
    for path in ("/mcp/health", "/mcp/ready"):
        assert client.get(path).status_code == 503
    with client:
        for path in ("/mcp/health", "/mcp/ready"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.json()["status"] == "ready"
        response = client.get("/mcp/live")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    for path in ("/mcp/health", "/mcp/ready"):
        assert client.get(path).status_code == 503
