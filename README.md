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

The client centralizes authentication headers, endpoint construction, field selection, bounded transient retries, timeout/error mapping, JSON normalization, and binary attachment limits. Credentials, authorization headers, article content, and attachment bodies are not logged.

## Tool mapping

```text
search_knowledge
    → GET /knowledge/articles

get_knowledge_article
    → GET /knowledge/articles/{id}

get_knowledge_attachment
    → GET /knowledge/articles/{article_sys_id}/attachments/{attachment_sys_id}
```

`search_knowledge` preserves ServiceNow result ordering and returns compact candidates. It does not claim semantic, vector, AI, or full-text behavior. `get_knowledge_article` returns the selected canonical article and useful validity metadata. `get_knowledge_attachment` returns bounded binary data as base64 because structured MCP output is JSON-compatible; callers must decode it, and no parsing or OCR is performed.

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

## Configuration

All settings are shown in [.env.example](.env.example). `SERVICENOW_BASE_URL` is required at runtime. Authentication can use a static `SERVICENOW_ACCESS_TOKEN`, or `SERVICENOW_CLIENT_ID` and `SERVICENOW_CLIENT_SECRET` to obtain and cache a token from `SERVICENOW_OAUTH_TOKEN_PATH`. A static access token takes precedence. Search and article field selections are centralized in `SERVICENOW_SEARCH_FIELDS` and `SERVICENOW_ARTICLE_FIELDS` so verified standard or custom fields can be adopted without modifying the client.

The default API path and query parameter names are implementation assumptions that must be checked against the selected ServiceNow Knowledge Management API version. Search can be scoped with configured or per-tool Knowledge Base and language values. The requested result limit, article content length, attachment bytes, timeout, and transient retries are bounded.

## Authorization boundary

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
