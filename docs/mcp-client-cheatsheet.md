# MCP Python Client Cheatsheet

## Windows Git Bash: direct ServiceNow diagnostics

The commands in this section run from Windows Git Bash and call ServiceNow directly without
going through MCP. Use them to separate environment, DNS, proxy, TLS, OAuth, and ServiceNow API
problems from MCP implementation problems. Do not share output containing access tokens, client
IDs, or client secrets.

### Quick Python/httpx connectivity check

Use this after the `SERVICENOW_*` variables have already been loaded into the current shell. It
makes an unauthenticated request to the OAuth endpoint; any HTTP response proves that Python can
reach the endpoint, while a traceback indicates a network or TLS problem.

```bash
python - <<'PY'
import os
import httpx

url = (
    os.environ["SERVICENOW_BASE_URL"].rstrip("/")
    + "/"
    + os.environ["SERVICENOW_OAUTH_TOKEN_PATH"].lstrip("/")
)
response = httpx.get(url, timeout=10)
print(response.status_code)
print(response.text[:500])
PY
```

### Inspect the effective URL, proxy settings, and DNS

Use this when Python reports `getaddrinfo failed` or connects to an unexpected path. It prints no
credentials, but it reveals hidden characters, Git Bash path conversion, active proxy variables,
and DNS resolution results.

```bash
set -a
source .env
set +a

python - <<'PY'
import os
import socket
from urllib.parse import urlsplit

url = (
    os.environ["SERVICENOW_BASE_URL"].rstrip("/")
    + "/"
    + os.environ["SERVICENOW_OAUTH_TOKEN_PATH"].lstrip("/")
)
parsed = urlsplit(url)

print("URL:", repr(url))
print("Hostname:", repr(parsed.hostname))

for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
    print(f"{name}:", repr(os.environ.get(name)))

try:
    print("DNS:", socket.getaddrinfo(parsed.hostname, 443))
except Exception as exc:
    print("DNS failed:", repr(exc))
PY
```

### Print the complete Python/httpx connection error

Use this when the MCP result only reports `UPSTREAM_UNAVAILABLE`. The full traceback distinguishes
DNS, proxy, timeout, and certificate-verification failures.

```bash
set -a
source .env
set +a

python - <<'PY'
import os
import traceback
import httpx

url = (
    os.environ["SERVICENOW_BASE_URL"].rstrip("/")
    + "/"
    + os.environ["SERVICENOW_OAUTH_TOKEN_PATH"].lstrip("/")
)

try:
    response = httpx.get(url, timeout=10)
    print("HTTP status:", response.status_code)
    print(response.text[:500])
except Exception:
    traceback.print_exc()
PY
```

### End-to-end OAuth and Knowledge API check without MCP or jq

This obtains a client-credentials token and searches ServiceNow Knowledge directly. It uses
Python for JSON parsing, so `jq` is not required. `--ssl-revoke-best-effort` is intended for
Windows Schannel diagnostics when the corporate network cannot complete a revocation check.

```bash
set -a; source .env; set +a; \
SN_ACCESS_TOKEN="$(curl --ssl-revoke-best-effort -sS -X POST \
  "${SERVICENOW_BASE_URL%/}/${SERVICENOW_OAUTH_TOKEN_PATH#/}" \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode "client_id=${SERVICENOW_CLIENT_ID}" \
  --data-urlencode "client_secret=${SERVICENOW_CLIENT_SECRET}" \
  --data-urlencode "scope=${SERVICENOW_OAUTH_SCOPE}" |
  python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')" && \
curl --ssl-revoke-best-effort -sS -G \
  "${SERVICENOW_BASE_URL%/}/${SERVICENOW_KNOWLEDGE_API_PATH#/}" \
  -H 'Accept: application/json' \
  -H "Authorization: Bearer ${SN_ACCESS_TOKEN}" \
  --data-urlencode 'query=remote access' \
  --data-urlencode 'limit=1' \
  --data-urlencode 'fields=sys_id,number,short_description' |
  python -m json.tool
```

### Show the raw OAuth token endpoint response

Use this to diagnose `invalid_client`, `unsupported_grant_type`, or scope configuration. The
response may contain an access token, so do not paste or screenshot successful output without
redacting it.

```bash
set -a; source .env; set +a

curl --ssl-revoke-best-effort -sS -X POST \
  "${SERVICENOW_BASE_URL%/}/${SERVICENOW_OAUTH_TOKEN_PATH#/}" \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode "client_id=${SERVICENOW_CLIENT_ID}" \
  --data-urlencode "client_secret=${SERVICENOW_CLIENT_SECRET}" \
  --data-urlencode "scope=${SERVICENOW_OAUTH_SCOPE}"
```

This guide explains how to use [`scripts/mcp_client.py`](../scripts/mcp_client.py) to call the local ServiceNow Knowledge MCP server.

The client communicates over HTTP/JSON-RPC and does not require the `fastmcp` CLI.

## 1. Open the project directory

Run all commands below from the project root unless stated otherwise:

```bash
cd /Users/xingyuji/workspace/BupaMCP/SnowMCP
```

Confirm that the Python virtual environment exists:

```bash
.venv/bin/python --version
```

If the virtual environment does not exist, create it and install the project:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## 2. Configure ServiceNow

Create a local environment file the first time you run the server:

```bash
cp .env.example .env
```

Edit `.env` and provide at least these settings:

```dotenv
SERVICENOW_BASE_URL=https://your-instance.service-now.com
SERVICENOW_ACCESS_TOKEN=
SERVICENOW_CLIENT_ID=your-client-id
SERVICENOW_CLIENT_SECRET=your-client-secret
SERVICENOW_OAUTH_TOKEN_PATH=oauth_token.do
SERVICENOW_OAUTH_SCOPE=
TRANSPORT=http
HOST=0.0.0.0
PORT=8080
```

When `SERVICENOW_ACCESS_TOKEN` is empty, the server uses the client ID and secret to obtain
and cache an OAuth access token automatically. If Snow supplied a scope, set it in
`SERVICENOW_OAUTH_SCOPE`; otherwise leave it empty. A configured static access token takes
precedence over client credentials.

Do not commit an `.env` file containing a real access token or client secret.

## 3. Test ServiceNow directly (without MCP)

Run this from the project root after filling in `.env`. It obtains an OAuth token and then
calls the ServiceNow Knowledge API directly, so it isolates ServiceNow connectivity,
credentials, scope, ACL, and Knowledge API behavior from the MCP implementation. `jq` is
required.

```bash
set -a; source .env; set +a; \
SN_ACCESS_TOKEN="$(curl -sS -X POST \
  "${SERVICENOW_BASE_URL%/}/${SERVICENOW_OAUTH_TOKEN_PATH#/}" \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode "client_id=${SERVICENOW_CLIENT_ID}" \
  --data-urlencode "client_secret=${SERVICENOW_CLIENT_SECRET}" \
  --data-urlencode "scope=${SERVICENOW_OAUTH_SCOPE}" | jq -er '.access_token')" && \
curl -sS -G "${SERVICENOW_BASE_URL%/}/${SERVICENOW_KNOWLEDGE_API_PATH#/}" \
  -H 'Accept: application/json' \
  -H "Authorization: Bearer ${SN_ACCESS_TOKEN}" \
  --data-urlencode 'query=remote access' \
  --data-urlencode 'limit=1' \
  --data-urlencode 'fields=sys_id,number,short_description' | jq .
```

This command talks only to ServiceNow; it does not start or call the MCP server. A successful
check returns JSON containing a `result` value. A successful empty `result` still proves that
OAuth and the API call worked, but may indicate that the test query has no visible matches.

## 4. Start the MCP server

Run the server in the first terminal:

```bash
cd /Users/xingyuji/workspace/BupaMCP/SnowMCP
.venv/bin/python -m servicenow_mcp.server
```

The default MCP endpoint is:

```text
http://127.0.0.1:8080/mcp
```

Leave this terminal running and use a second terminal for the client commands.

## 5. Display client help

Show all available commands:

```bash
.venv/bin/python scripts/mcp_client.py --help
```

Show the arguments for each subcommand:

```bash
.venv/bin/python scripts/mcp_client.py search --help
.venv/bin/python scripts/mcp_client.py article --help
```

## 6. List MCP tools

```bash
.venv/bin/python scripts/mcp_client.py list
```

Expected tools:

```text
search_knowledge
list_knowledge_categories
get_knowledge_article
```

List every Knowledge category visible to the configured ServiceNow identity (the server
automatically follows Table API pagination):

```bash
.venv/bin/python scripts/mcp_client.py categories
```

## 7. Search for Knowledge Articles

Basic search:

```bash
.venv/bin/python scripts/mcp_client.py search "remote access"
```

Return up to five results:

```bash
.venv/bin/python scripts/mcp_client.py search "remote access" --limit 5
```

Specify a language:

```bash
.venv/bin/python scripts/mcp_client.py search "remote access" --language en
```

Specify a Knowledge Base:

```bash
.venv/bin/python scripts/mcp_client.py search "remote access" \
  --knowledge-base workplace
```

Specify all optional search arguments:

```bash
.venv/bin/python scripts/mcp_client.py search "remote access" \
  --limit 5 \
  --knowledge-base workplace \
  --language en
```

The command prints formatted JSON similar to:

```json
{
  "query": "remote access",
  "total": 1,
  "results": [
    {
      "id": "ARTICLE_SYS_ID",
      "number": "KB0010001",
      "title": "Remote access guide",
      "rank": 1
    }
  ]
}
```

Use the result's `id` value, not its `number`, when retrieving the full article.

## 8. Retrieve a complete article

Replace `ARTICLE_SYS_ID` with an `id` returned by the search command:

```bash
.venv/bin/python scripts/mcp_client.py article ARTICLE_SYS_ID
```

Example:

```bash
.venv/bin/python scripts/mcp_client.py article 0123456789abcdef0123456789abcdef
```

The response can include the title, content, Knowledge Base, category, publication state, validity date, and update timestamp.

## 9. Use a different MCP endpoint

`--server` and `--timeout` are global arguments. They must appear before the `list`, `search`, or `article` subcommand.

Connect to port 9000:

```bash
.venv/bin/python scripts/mcp_client.py \
  --server http://127.0.0.1:9000/mcp \
  list
```

Use a 60-second timeout for a search:

```bash
.venv/bin/python scripts/mcp_client.py \
  --server http://127.0.0.1:8080/mcp \
  --timeout 60 \
  search "remote access" --limit 5
```

Incorrect argument order:

```text
python scripts/mcp_client.py list --server http://127.0.0.1:9000/mcp
```

Correct argument order:

```bash
.venv/bin/python scripts/mcp_client.py \
  --server http://127.0.0.1:9000/mcp \
  list
```

## 10. Complete workflow

Start the server in the first terminal:

```bash
cd /Users/xingyuji/workspace/BupaMCP/SnowMCP
.venv/bin/python -m servicenow_mcp.server
```

List tools and search from the second terminal:

```bash
cd /Users/xingyuji/workspace/BupaMCP/SnowMCP

.venv/bin/python scripts/mcp_client.py list

.venv/bin/python scripts/mcp_client.py search "remote access" \
  --limit 5 \
  --language en
```

Copy an `id` from the search result and retrieve the article:

```bash
.venv/bin/python scripts/mcp_client.py article ARTICLE_SYS_ID
```

## 11. Troubleshooting

### Connection refused

Example error:

```text
Error: All connection attempts failed
```

The MCP server is not running, or the configured port is incorrect. Start the server:

```bash
.venv/bin/python -m servicenow_mcp.server
```

### Address already in use

Example error:

```text
address already in use
```

Another process is already listening on port 8080. The MCP server may already be running. Check it by listing the tools:

```bash
.venv/bin/python scripts/mcp_client.py list
```

### UNAUTHENTICATED

Example error:

```text
ServiceNow authentication is not configured
```

Make sure `.env` contains either an access token:

```dotenv
SERVICENOW_ACCESS_TOKEN=your-access-token
```

or both client credential values:

```dotenv
SERVICENOW_ACCESS_TOKEN=
SERVICENOW_CLIENT_ID=your-client-id
SERVICENOW_CLIENT_SECRET=your-client-secret
```

Restart the MCP server after changing `.env`.

### CERTIFICATE_VERIFY_FAILED

The MCP HTTP clients use the operating system certificate store through `truststore`, including
enterprise-managed root certificates. Reinstall the project after pulling dependency changes,
then restart the MCP server:

```bash
python -m pip install -e '.[dev]'
python -m servicenow_mcp.server
```

If verification still fails, confirm with the corporate security or network team that the TLS
inspection root certificate is installed in the Windows Trusted Root Certification Authorities
store. Do not disable TLS verification in production.

### FORBIDDEN

ServiceNow accepted the authentication details, but the integration identity cannot access the requested content. Check its roles, ACLs, User Criteria, and Knowledge Base permissions.

### NOT_FOUND

The article ID does not exist, or the integration identity cannot see it. Confirm that you are using the search result's `id` value.

### RATE_LIMITED

ServiceNow rejected the request because a rate limit was reached. Retry later and check the instance's API rate-limit configuration.

## 12. Run automated tests

Test the MCP tools without calling a real ServiceNow instance:

```bash
.venv/bin/python -m pytest tests/test_tools.py -v
```

Run the complete test suite:

```bash
.venv/bin/python -m pytest -q
```
