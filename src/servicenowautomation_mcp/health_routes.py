from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .runtime import ServiceRuntime

SERVICE_NAME = "servicenowautomation-mcp"


def register_health_routes(server: FastMCP, runtime: ServiceRuntime) -> None:
    @server.custom_route("/mcp/live", methods=["GET"])
    async def health_live(_: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": SERVICE_NAME})

    @server.custom_route("/mcp/health", methods=["GET"])
    @server.custom_route("/mcp/ready", methods=["GET"])
    async def health_ready(_: Request) -> JSONResponse:
        is_ready = runtime.ready
        return JSONResponse(
            {
                "status": "ready" if is_ready else "not_ready",
                "service": SERVICE_NAME,
            },
            status_code=200 if is_ready else 503,
        )
