"""Small HTTP client for exercising the local ServiceNow Knowledge MCP server."""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Self

import httpx


class McpHttpClient:
    """Minimal Streamable HTTP/JSON-RPC client for this stateless MCP server."""

    def __init__(
        self,
        server_url: str,
        timeout: float,
        token: str | None = None,
    ) -> None:
        self._next_id = 0
        self._session_id: str | None = None
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=server_url,
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        )

    async def __aenter__(self) -> Self:
        await self.initialize()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        if self._session_id:
            return {"Mcp-Session-Id": self._session_id}
        return {}

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        request_id = self._next_id
        response = await self._client.post(
            "",
            headers=self._headers(),
            json={
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            },
        )
        response.raise_for_status()
        self._session_id = response.headers.get("Mcp-Session-Id") or self._session_id
        message = _parse_mcp_response(response, request_id)
        if "error" in message:
            error = message["error"]
            raise RuntimeError(f"MCP error {error.get('code')}: {error.get('message')}")
        result = message.get("result")
        if not isinstance(result, dict):
            raise TypeError("MCP response did not contain an object result")
        return result

    async def _notify(self, method: str) -> None:
        response = await self._client.post(
            "",
            headers=self._headers(),
            json={"jsonrpc": "2.0", "method": method},
        )
        response.raise_for_status()

    async def initialize(self) -> None:
        await self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "local-python-client", "version": "1.0"},
            },
        )
        await self._notify("notifications/initialized")

    async def list_tools(self) -> dict[str, Any]:
        return await self._request("tools/list", {})

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )


def _parse_mcp_response(response: httpx.Response, request_id: int) -> dict[str, Any]:
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        payload = response.json()
        if isinstance(payload, dict):
            return payload
        raise RuntimeError("MCP server returned non-object JSON")

    messages: list[dict[str, Any]] = []
    for line in response.text.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            payload = json.loads(line.removeprefix("data:").strip())
        except json.JSONDecodeError as exc:
            raise RuntimeError("MCP server returned malformed SSE data") from exc
        if isinstance(payload, dict):
            messages.append(payload)

    for message in messages:
        if message.get("id") == request_id:
            return message
    raise RuntimeError("MCP server returned no matching JSON-RPC response")


def _tool_output(result: dict[str, Any]) -> Any:
    return result.get("structuredContent", result)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call the local ServiceNow Knowledge MCP server")
    parser.add_argument("--server", default="http://127.0.0.1:8080/mcp")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--token",
        default=os.getenv("MCP_ACCESS_TOKEN"),
        help="Bearer token (defaults to MCP_ACCESS_TOKEN)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List tools exposed by the MCP server")
    subparsers.add_parser("categories", help="Call list_knowledge_categories")

    search = subparsers.add_parser("search", help="Call search_knowledge")
    search.add_argument("query")
    search.add_argument("--limit", type=int)
    search.add_argument("--knowledge-base")
    search.add_argument("--language")

    article = subparsers.add_parser("article", help="Call get_knowledge_article")
    article.add_argument("article_id")

    return parser


async def _run(args: argparse.Namespace) -> None:
    async with McpHttpClient(args.server, args.timeout, args.token) as client:
        if args.command == "list":
            result = await client.list_tools()
            tools = result.get("tools", [])
            for tool in tools:
                print(f"{tool['name']}: {tool.get('description', '')}")
            return

        if args.command == "categories":
            result = await client.call_tool("list_knowledge_categories", {})
        elif args.command == "search":
            arguments = {
                key: value
                for key, value in {
                    "query": args.query,
                    "limit": args.limit,
                    "knowledge_base": args.knowledge_base,
                    "language": args.language,
                }.items()
                if value is not None
            }
            result = await client.call_tool("search_knowledge", arguments)
        elif args.command == "article":
            result = await client.call_tool(
                "get_knowledge_article", {"article_id": args.article_id}
            )
        else:
            raise AssertionError(f"Unhandled command: {args.command}")

        if result.get("isError"):
            content = result.get("content")
            if isinstance(content, list):
                messages = [
                    item["text"]
                    for item in content
                    if isinstance(item, dict) and isinstance(item.get("text"), str)
                ]
                if messages:
                    raise RuntimeError("; ".join(messages))
            raise RuntimeError("MCP tool call failed")

        output = _tool_output(result)
        print(json.dumps(output, indent=2, ensure_ascii=False))


def main() -> int:
    args = _parser().parse_args()
    try:
        asyncio.run(_run(args))
    except (httpx.HTTPError, RuntimeError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
