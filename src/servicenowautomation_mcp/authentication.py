"""
Azure Authentication Module
Provides credentials for Azure service communication
"""

import logging

from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential

logger = logging.getLogger(__name__)

# Lazy-loaded singleton
_azure_credential = None
_async_azure_credential = None


def get_azure_credential() -> DefaultAzureCredential:
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
    global _azure_credential

    if _azure_credential is None:
        _azure_credential = DefaultAzureCredential()
        logger.info("Azure DefaultAzureCredential initialized")

    return _azure_credential


def get_async_azure_credential() -> AsyncDefaultAzureCredential:
    """
    Get Azure credentials for async authentication flows.

    Returns:
        AsyncDefaultAzureCredential: Azure credential object
    """
    global _async_azure_credential

    if _async_azure_credential is None:
        _async_azure_credential = AsyncDefaultAzureCredential()
        logger.info("Azure async DefaultAzureCredential initialized")

    return _async_azure_credential


async def close_async_azure_credential() -> None:
    """Close the async Azure credential if it was created."""
    global _async_azure_credential

    if _async_azure_credential is not None:
        await _async_azure_credential.close()
        _async_azure_credential = None
