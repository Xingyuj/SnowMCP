# MCP scope authorization and local testing

The MCP server has two separate OAuth boundaries:

- inbound MCP JWT authentication protects `/mcp` and checks each tool's scopes;
- `SERVICENOW_OAUTH_SCOPE` is only used when the server obtains a downstream ServiceNow token.

The tool-to-scope mapping is:

| Tool | Default required scope |
| --- | --- |
| `search_knowledge` | `knowledge.search` |
| `list_knowledge_categories` | `knowledge.category.read` |
| `get_knowledge_article` | `knowledge.article.read` |
| `get_knowledge_attachment` | `knowledge.attachment.read` |

The names can be changed with `MCP_SEARCH_SCOPE`, `MCP_CATEGORY_READ_SCOPE`,
`MCP_ARTICLE_READ_SCOPE`, and `MCP_ATTACHMENT_READ_SCOPE`. When `MCP_AUTH_ENABLED=false`, inbound authentication and tool
scope checks are intentionally disabled for local backward compatibility. Deployed HTTP
environments should enable authentication.

## Production JWT verification

Use an authorization server's HTTPS JWKS endpoint and RS256:

```dotenv
MCP_AUTH_ENABLED=true
MCP_JWT_JWKS_URI=https://login.example.com/.well-known/jwks.json
MCP_JWT_PUBLIC_KEY=
MCP_JWT_ISSUER=https://login.example.com/
MCP_JWT_AUDIENCE=servicenow-knowledge-mcp
MCP_JWT_ALGORITHM=RS256
```

The server verifies the JWT signature, issuer, audience, expiry, and then the selected tool's
scope. Configure exactly one of `MCP_JWT_JWKS_URI` and `MCP_JWT_PUBLIC_KEY`.

## Local tokens with different scopes

HS256 is convenient for local testing only. Use a sufficiently long throwaway secret and do not
reuse it outside the local environment:

```bash
export MCP_AUTH_ENABLED=true
export MCP_JWT_PUBLIC_KEY='local-only-secret-change-me-32-bytes-minimum'
export MCP_JWT_JWKS_URI=
export MCP_JWT_ISSUER='https://local.test'
export MCP_JWT_AUDIENCE='servicenow-knowledge-mcp'
export MCP_JWT_ALGORITHM=HS256

SEARCH_TOKEN="$(.venv/bin/python scripts/generate_test_jwt.py \
  --secret "$MCP_JWT_PUBLIC_KEY" knowledge.search)"

CATEGORY_TOKEN="$(.venv/bin/python scripts/generate_test_jwt.py \
  --secret "$MCP_JWT_PUBLIC_KEY" knowledge.category.read)"

ARTICLE_TOKEN="$(.venv/bin/python scripts/generate_test_jwt.py \
  --secret "$MCP_JWT_PUBLIC_KEY" knowledge.article.read)"

ALL_TOKEN="$(.venv/bin/python scripts/generate_test_jwt.py \
  --secret "$MCP_JWT_PUBLIC_KEY" \
  knowledge.search knowledge.category.read knowledge.article.read knowledge.attachment.read)"
```

Start the server in another terminal with the same exported configuration:

```bash
.venv/bin/servicenow-knowledge-mcp
```

The client sends its token on initialization, tool listing, and tool calls. Either pass it
directly or use `MCP_ACCESS_TOKEN`:

```bash
.venv/bin/python scripts/mcp_client.py --token "$SEARCH_TOKEN" list
MCP_ACCESS_TOKEN="$ARTICLE_TOKEN" .venv/bin/python scripts/mcp_client.py list
MCP_ACCESS_TOKEN="$ALL_TOKEN" .venv/bin/python scripts/mcp_client.py list
```

Expected tool visibility:

- `SEARCH_TOKEN` lists only `search_knowledge`;
- `CATEGORY_TOKEN` lists only `list_knowledge_categories`;
- `ARTICLE_TOKEN` lists only `get_knowledge_article`;
- `ALL_TOKEN` lists all four tools.

Example calls:

```bash
MCP_ACCESS_TOKEN="$SEARCH_TOKEN" .venv/bin/python scripts/mcp_client.py \
  search "remote access" --limit 5

MCP_ACCESS_TOKEN="$CATEGORY_TOKEN" .venv/bin/python scripts/mcp_client.py categories

MCP_ACCESS_TOKEN="$ARTICLE_TOKEN" .venv/bin/python scripts/mcp_client.py \
  article ARTICLE_SYS_ID

MCP_ACCESS_TOKEN="$ALL_TOKEN" .venv/bin/python scripts/mcp_client.py \
  attachment ARTICLE_SYS_ID ATTACHMENT_SYS_ID --output attachment.bin
```

Calling a tool with a valid JWT but without that tool's required scope is rejected before the
ServiceNow client is invoked. An invalid, expired, wrong-issuer, or wrong-audience token receives
HTTP 401 at the MCP endpoint.
