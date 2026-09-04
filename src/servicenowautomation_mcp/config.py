"""
Configuration Management using Pydantic Settings
Environment-based configuration with .env file support
"""

import logging
from typing import List, Optional

from azure.identity import DefaultAzureCredential
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    Automatically loads from .env file and environment variables.
    """

    # MCP Configuration
    mcp_name: str = "servicenowautomation-mcp"
    mcp_description: str = (
        "Bupa ServiceNowAutomation - Sync FASTMCP for servicenowautomation services"
    )
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    mcp_transport: str = "streamable-http"  # or 'stdio'
    app_type: str = "Xapi"
    app_pattern: str = "Sync"

    # Environment
    environment: str = "development"
    log_level: str = "INFO"
    debug: bool = False
    applicationinsights_connection_string: Optional[str] = None

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    # CORS
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
    ]

    # Azure Configuration
    azure_tenant_id: Optional[str] = None
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def get_azure_credential(self) -> DefaultAzureCredential:
        """
        Get Azure credentials for authentication.
        Uses DefaultAzureCredential which tries multiple auth methods:
        1. Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
        2. Managed Identity (when running in Azure)
        3. Azure CLI credentials
        4. Interactive browser login

        Returns:
            DefaultAzureCredential: Azure credential object
        """
        return DefaultAzureCredential()


# Create a singleton settings instance
settings = Settings()
