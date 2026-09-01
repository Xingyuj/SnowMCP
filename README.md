# ServiceNow Knowledge MCP

A deterministic, read-only FastMCP integration for ServiceNow Knowledge retrieval. It performs no answer generation, summarization, semantic reranking, vector search, or document parsing.

## Architecture

```text
AI platform / MCP client
        ↓
FastMCP server
        ↓
KnowledgeService
        ↓
ServiceNowKnowledgeClient
        ↓
ServiceNow Knowledge Management REST API
```

The client centralizes authentication headers, endpoint construction, field selection, bounded transient retries, timeout/error mapping, JSON normalization, and binary attachment limits. HTTPS verification uses the operating system trust store so enterprise-managed root certificates are honored. Credentials, authorization headers, article content, and attachment bodies are not logged.

## Tool mapping

```text
search_knowledge
    → GET /knowledge/articles

list_knowledge_categories
    → GET /api/now/table/kb_category (automatically paginated)

get_knowledge_article
    → GET /knowledge/articles/{id}

get_knowledge_attachment
    → GET /knowledge/articles/{article_sys_id}/attachments/{attachment_sys_id}
```

`search_knowledge` preserves ServiceNow result ordering and returns compact candidates. It does not claim semantic, vector, AI, or full-text behavior. `list_knowledge_categories` automatically paginates the `kb_category` table and returns all categories visible to the ServiceNow integration identity. `get_knowledge_article` returns the selected canonical article and useful validity metadata. `get_knowledge_attachment` returns bounded binary data as base64 because structured MCP output is JSON-compatible; callers must decode it, and no parsing or OCR is performed.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
pytest
ruff format --check src tests
ruff check src tests
mypy src
servicenow-knowledge-mcp
```

The default network transport is stateless Streamable HTTP at `http://localhost:8080/mcp`. Set `TRANSPORT=stdio` for a locally spawned MCP client.

Container build:

```bash
docker build -t servicenow-knowledge-mcp .
docker run --env-file .env -p 8080:8080 servicenow-knowledge-mcp
```

Local HTTP client (run the server first):

```bash
python scripts/mcp_client.py list
python scripts/mcp_client.py categories
python scripts/mcp_client.py search "remote access" --limit 5
python scripts/mcp_client.py article ARTICLE_ID
python scripts/mcp_client.py attachment ARTICLE_ID ATTACHMENT_ID --output attachment.bin
```

The client uses HTTP/JSON-RPC directly and does not require the `fastmcp` CLI.
See [docs/mcp-client-cheatsheet.md](docs/mcp-client-cheatsheet.md) for copy-ready commands,
examples, and troubleshooting.

## Configuration

All settings are shown in [.env.example](.env.example). `SERVICENOW_BASE_URL` is required at runtime. Authentication can use a static `SERVICENOW_ACCESS_TOKEN`, or `SERVICENOW_CLIENT_ID` and `SERVICENOW_CLIENT_SECRET` to obtain and cache a token from `SERVICENOW_OAUTH_TOKEN_PATH`. A static access token takes precedence. Search, article, and category field selections are centralized in `SERVICENOW_SEARCH_FIELDS`, `SERVICENOW_ARTICLE_FIELDS`, and `SERVICENOW_CATEGORY_FIELDS` so verified standard or custom fields can be adopted without modifying the client. The category Table API path and automatic pagination page size can be configured with `SERVICENOW_CATEGORIES_API_PATH` and `CATEGORY_PAGE_SIZE`.

The default API path and query parameter names are implementation assumptions that must be checked against the selected ServiceNow Knowledge Management API version. Search can be scoped with configured or per-tool Knowledge Base and language values. The requested result limit, article content length, attachment bytes, timeout, and transient retries are bounded.

## Authorization boundary

Inbound MCP bearer tokens can be verified as JWTs using a JWKS endpoint or configured public key.
When enabled, every tool has its own required scope. See
[MCP scope authorization and local testing](docs/mcp-scope-testing.md) for the scope mapping,
configuration, test-token generation, and client commands.

An integration identity does not by itself prove that an end user's Knowledge permissions are enforced. The authenticator accepts an internal authorization context so a confirmed delegated mechanism can be added without redesigning the client, but the MCP tools do not invent or accept a delegated credential today.

Open security question: when the MCP calls ServiceNow using an integration identity, are Knowledge Base ACLs, User Criteria, roles, group membership, and article-level restrictions evaluated only against the integration identity, or can the end-user authorization context be propagated and enforced?

Production use must not proceed until the applicable entitlement contract is confirmed and tested.

## Assumptions and open questions

The traceable Epic, Stories, Tasks, assumptions, and unresolved integration questions are maintained in [docs/implementation-plan.md](docs/implementation-plan.md). Important unresolved items include:

1. What search/indexing/ranking capability backs the `query` parameter, and does it match the Knowledge UI?
2. Which Knowledge Bases, languages, and publication states are in scope?
3. How will end-user authorization be enforced when an integration identity is used?
4. Which standard or custom field contains canonical article content?
5. Which fields are required for audience, validity, publication, citation, and freshness?
6. What authentication mechanism, API version, rate limits, and throughput apply?
7. Which non-production environment and representative retrieval-quality fixtures are available?
