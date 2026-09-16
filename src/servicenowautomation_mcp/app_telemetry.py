"""Azure Application Insights telemetry setup for the MCP service."""

import logging
from threading import Lock

logger = logging.getLogger(__name__)

_PLACEHOLDER_CONNECTION_STRING = "---your connection string---"
_configuration_lock = Lock()
_telemetry_configured = False


def set_up_telemetry(
    *,
    connection_string: str | None,
    service_name: str,
    environment: str,
) -> bool:
    """Configure Azure Monitor once when an Application Insights connection is available."""
    global _telemetry_configured

    if not connection_string:
        logger.info("Application Insights telemetry disabled: missing connection string")
        return False
    if connection_string.strip() == _PLACEHOLDER_CONNECTION_STRING:
        logger.warning(
            "Application Insights telemetry disabled: placeholder connection string configured"
        )
        return False

    with _configuration_lock:
        if _telemetry_configured:
            return True
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(connection_string=connection_string)
        except Exception:
            logger.exception("Failed to configure Application Insights telemetry")
            return False

        _telemetry_configured = True

    logger.info(
        "Application Insights telemetry enabled for service=%s environment=%s",
        service_name,
        environment,
    )
    return True
