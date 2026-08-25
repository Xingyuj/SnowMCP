# MCP Python Client Cheatsheet

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
SERVICENOW_ACCESS_TOKEN=your-access-token
TRANSPORT=http
HOST=0.0.0.0
PORT=8080
```

Do not commit an `.env` file containing a real access token.

## 3. Start the MCP server

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

## 4. Display client help

Show all available commands:

```bash
.venv/bin/python scripts/mcp_client.py --help
```

Show the arguments for each subcommand:

```bash
.venv/bin/python scripts/mcp_client.py search --help
.venv/bin/python scripts/mcp_client.py article --help
.venv/bin/python scripts/mcp_client.py attachment --help
```

## 5. List MCP tools

```bash
.venv/bin/python scripts/mcp_client.py list
```

Expected tools:

```text
search_knowledge
get_knowledge_article
get_knowledge_attachment
```

## 6. Search for Knowledge Articles

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

## 7. Retrieve a complete article

Replace `ARTICLE_SYS_ID` with an `id` returned by the search command:

```bash
.venv/bin/python scripts/mcp_client.py article ARTICLE_SYS_ID
```

Example:

```bash
.venv/bin/python scripts/mcp_client.py article 0123456789abcdef0123456789abcdef
```

The response can include the title, content, Knowledge Base, category, publication state, validity date, and update timestamp.

## 8. Retrieve attachment data

Print the attachment metadata and Base64-encoded content without saving a file:

```bash
.venv/bin/python scripts/mcp_client.py attachment \
  ARTICLE_SYS_ID \
  ATTACHMENT_SYS_ID
```

The returned `content_base64` field contains the binary attachment encoded as Base64.

## 9. Download an attachment

Use `--output` to decode the Base64 content and save it as a file:

```bash
.venv/bin/python scripts/mcp_client.py attachment \
  ARTICLE_SYS_ID \
  ATTACHMENT_SYS_ID \
  --output downloaded-attachment.pdf
```

Example:

```bash
.venv/bin/python scripts/mcp_client.py attachment \
  0123456789abcdef0123456789abcdef \
  fedcba9876543210fedcba9876543210 \
  --output guide.pdf
```

Confirm that the file was created:

```bash
ls -lh guide.pdf
```

The client writes a file only when `--output` is explicitly provided.

## 10. Use a different MCP endpoint

`--server` and `--timeout` are global arguments. They must appear before the `list`, `search`, `article`, or `attachment` subcommand.

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

## 11. Complete workflow

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

If you have an attachment ID, download the attachment:

```bash
.venv/bin/python scripts/mcp_client.py attachment \
  ARTICLE_SYS_ID \
  ATTACHMENT_SYS_ID \
  --output attachment.bin
```

## 12. Troubleshooting

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

Make sure `.env` contains an access token:

```dotenv
SERVICENOW_ACCESS_TOKEN=your-access-token
```

Restart the MCP server after changing `.env`.

### FORBIDDEN

ServiceNow accepted the authentication details, but the integration identity cannot access the requested content. Check its roles, ACLs, User Criteria, and Knowledge Base permissions.

### NOT_FOUND

The article or attachment ID does not exist, or the integration identity cannot see it. Confirm that you are using the search result's `id` value.

### RATE_LIMITED

ServiceNow rejected the request because a rate limit was reached. Retry later and check the instance's API rate-limit configuration.

### PAYLOAD_TOO_LARGE

The attachment is larger than the configured limit:

```dotenv
MAX_ATTACHMENT_BYTES=5000000
```

Confirm that the attachment is trusted and required before increasing this value. Restart the server after changing `.env`.

## 13. Run automated tests

Test the MCP tools without calling a real ServiceNow instance:

```bash
.venv/bin/python -m pytest tests/test_tools.py -v
```

Run the complete test suite:

```bash
.venv/bin/python -m pytest -q
```
