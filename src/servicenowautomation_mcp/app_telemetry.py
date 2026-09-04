"""Application Insights telemetry setup for the MCP service."""

import logging

from config import settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_CONNECTION_STRING = "---your connection string---"


def set_up_telemetry() -> None:
    """Configure Azure Monitor telemetry when a valid connection string is provided."""
    connection_string = settings.applicationinsights_connection_string
    if not connection_string:
        logger.info("Application Insights telemetry disabled: missing connection string")
        return

    if connection_string.strip() == _PLACEHOLDER_CONNECTION_STRING:
        logger.warning(
            "Application Insights telemetry disabled: placeholder connection string configured"
        )
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ModuleNotFoundError:
        logger.warning(
            "Application Insights telemetry disabled: azure-monitor-opentelemetry package is not installed"  # noqa: E501
        )
        return

    try:
        configure_azure_monitor(connection_string=connection_string)
    except Exception:
        logger.exception("Failed to configure Application Insights telemetry")
        return

    logger.info(
        "Application Insights telemetry enabled for service=%s environment=%s",
        settings.mcp_name,
        settings.environment,
    )
