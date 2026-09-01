# APIM claims authorization and local testing

## Trust model

The production MCP endpoint sits behind Azure API Management:

1. Microsoft Entra ID issues an access token to the MCP client.
2. APIM validates the token with `validate-azure-ad-token`, including signature, issuer, audience,
   and expiry.
3. APIM forwards the original validated `Authorization: Bearer ...` header.
4. Enforced network controls guarantee that the MCP backend is reachable only through APIM.
5. The MCP server decodes the already-validated token claims without verifying its signature again
   and applies per-tool scope checks.

The APIM-only network route is part of the authentication boundary, not an optional deployment
optimization. If any caller can bypass APIM, it can present forged claims because the MCP server
intentionally does not repeat cryptographic token validation.

## Tool scopes

| Tool | Default required scope |
| --- | --- |
| `search_knowledge` | `knowledge.search` |
| `list_knowledge_categories` | `knowledge.category.read` |
| `get_knowledge_article` | `knowledge.article.read` |

The names can be changed with `MCP_SEARCH_SCOPE`, `MCP_CATEGORY_READ_SCOPE`, and
`MCP_ARTICLE_READ_SCOPE`.

The server reads subjects from `oid` and then `sub` by default. It combines scopes from `scp`,
`scope`, and `roles`, supporting both delegated scopes and application roles. Override the claim
name lists with `APIM_SUBJECT_CLAIM_NAMES` and `APIM_SCOPE_CLAIM_NAMES` when APIM forwards a
different validated token shape.

## Production configuration

```dotenv
APIM_AUTH_ENABLED=true
APIM_SCOPE_CLAIM_NAMES=scp,scope,roles
APIM_SUBJECT_CLAIM_NAMES=oid,sub

MCP_SEARCH_SCOPE=knowledge.search
MCP_CATEGORY_READ_SCOPE=knowledge.category.read
MCP_ARTICLE_READ_SCOPE=knowledge.article.read
```

APIM must preserve the user bearer token after validation so the MCP server can extract the
authorized subject and scopes.

When `APIM_AUTH_ENABLED=false`, claims extraction and all tool scope checks are disabled. This mode
is intended only for local development without APIM.

## Local testing

For a local APIM-auth simulation, enable APIM claims authorization:

```bash
export APIM_AUTH_ENABLED=true
```

Generate a locally signed JWT containing the desired claims. The local server intentionally does
not verify this signature because APIM would perform that validation in production:

```bash
export LOCAL_JWT_SECRET='local-only-token-secret-at-least-32-bytes'

SEARCH_TOKEN="$(.venv/bin/python scripts/generate_test_jwt.py \
  --secret "$LOCAL_JWT_SECRET" knowledge.search)"

ALL_TOKEN="$(.venv/bin/python scripts/generate_test_jwt.py \
  --secret "$LOCAL_JWT_SECRET" \
  knowledge.search knowledge.category.read knowledge.article.read)"
```

Start the server in another terminal with the same APIM environment:

```bash
.venv/bin/servicenow-knowledge-mcp
```

The helper client sends the bearer token:

```bash
MCP_ACCESS_TOKEN="$SEARCH_TOKEN" \
.venv/bin/python scripts/mcp_client.py list
```

Expected tool visibility:

- a token with `knowledge.search` lists only `search_knowledge`;
- a token with all three scopes lists all three tools;
- a token missing a tool's scope cannot list or call that tool.

This local simulation does not establish the production APIM trust boundary. Production safety
depends on APIM token validation and blocked direct backend access.
