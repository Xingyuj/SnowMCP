# servicenowautomation-mcp

Bupa ServiceNowAutomation - Sync FASTMCP for servicenowautomation services

## Overview

This is a **Sync (FastMCP)** pattern application built with FastMCP framework. It implements the Model Context Protocol for standardized tool exposure and AI integration within the Bupa ecosystem.

**Pattern**: Sync with FastMCP  
**Framework**: FastMCP  
**Type**: Xapi  
**Version**: 1.0.0

## Getting Started

### Prerequisites

- Python 3.12 or higher
- pip or poetry for dependency management
- Azure CLI (for local development with Azure authentication)

### Installation

1. **Navigate to the application directory**:
   ```bash
   cd servicenowautomation-mcp
   ```

2. **Install dependencies** (interactive restore recommended):
   ```bash
   pip install -r requirements.txt
   # OR using poetry
   poetry install
   ```

3. **Configure environment**:
   ```bash
   cp .env.local .env
   # Edit .env with your configuration
   ```

### Running Locally

1. **Start the MCP server**:
   ```bash
   python run.py
   ```
   The server will start on `http://0.0.0.0:8000` by default.

2. **Health checks**:
   - Liveness: `GET /mcp/health`
   - Readiness: `GET /mcp/ready`
   - Alive: `GET /mcp/live`

## Project Structure

```
servicenowautomation-mcp/
├── main.py                 # FastMCP server factory
├── config.py              # Pydantic Settings
├── authentication.py      # Azure auth setup
├── exceptions.py          # Custom exceptions
├── handlers/
│   ├── health.py         # K8s health probes
│   └── __init__.py
├── tools/
│   ├── example_tool.py   # Sample tool
│   └── __init__.py
├── context/
│   ├── mcpcontext.py     # Request context management
│   └── __init__.py
├── pyproject.toml        # Dependencies & metadata
└── .env.local            # Environment variables
```

## Key Components

### Tools (`tools/`)
MCP tools are exposed services that external clients can call:
- `example_tool` - Demonstrates tool pattern

### Handlers (`handlers/`)
Request handlers for MCP operations:
- `health.py` - Kubernetes health check endpoints

### Context (`context/`)
Request-scoped context management:
- `mcpcontext.py` - Correlation ID and request ID tracking

## Health Checks

The application exposes three Kubernetes probe endpoints:

1. **Liveness** (`/mcp/health`) - Simple status check
   ```json
   {"status": "healthy", "service": "servicenowautomation-mcp"}
   ```

2. **Readiness** (`/mcp/ready`) - Checks if ready for traffic
   ```json
   {"status": "ready", "service": "servicenowautomation-mcp", "environment": "development"}
   ```

3. **Liveness Probe** (`/mcp/live`) - Detailed status with version
   ```json
   {"status": "alive", "service": "servicenowautomation-mcp", "version": "1.0.0", "correlation_id": "..."}
   ```

## Configuration

Configuration is managed through `config.py` using Pydantic `BaseSettings`:
- Loads from `.env` file
- Supports environment variable overrides
- Azure credential handling via `DefaultAzureCredential()`

**Key Settings**:
- `mcp_name` - Service name
- `environment` - Current environment (dev/test/uat/prod)
- `log_level` - Logging level
- `server_host` / `server_port` - Server binding

## Development

### Running Tests
```bash
pytest
```

### Code Quality
```bash
# Linting
ruff check .

# Type checking
mypy .

# Formatting
ruff format .
```

### Docker

Build and run in Docker:
```bash
docker build -f Dockerfile -t devopsdockercontainers.azurecr.io/servicenowautomation-mcp:latest .
docker run -p 8000:8000 devopsdockercontainers.azurecr.io/servicenowautomation-mcp:latest
```

## Authentication

The application uses Azure `DefaultAzureCredential` for authentication, which supports:
1. Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
2. Managed Identity (when running in Azure)
3. Azure CLI credentials
4. Interactive browser login

## Logging

Serilog-based structured logging with correlation IDs for request tracking across microservices.

## Contributing

Follow PEP 8 and Bupa code standards. Ensure tests pass before submission.

## License

Licensed by Bupa Team

## Support

For issues or questions, contact the Bupa platform team.
