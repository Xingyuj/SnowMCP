import logging

from fastmcp import Client

import servicenowautomation_mcp.server as server_module
from servicenowautomation_mcp import telemetry
from servicenowautomation_mcp.config import ServiceNowKnowledgeConfig
from servicenowautomation_mcp.server import create_mcp


def test_telemetry_is_disabled_without_connection_string(monkeypatch, caplog):
    monkeypatch.setattr(telemetry, "_telemetry_configured", False)

    with caplog.at_level(logging.INFO):
        configured = telemetry.set_up_telemetry(
            connection_string=None,
            service_name="servicenowautomation-mcp",
            environment="test",
        )

    assert configured is False
    assert "missing connection string" in caplog.text


def test_telemetry_configures_azure_monitor_only_once(monkeypatch):
    calls = []

    def configure_azure_monitor(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(telemetry, "_telemetry_configured", False)
    monkeypatch.setattr(
        "azure.monitor.opentelemetry.configure_azure_monitor", configure_azure_monitor
    )

    for _ in range(2):
        assert telemetry.set_up_telemetry(
            connection_string="InstrumentationKey=test-key",
            service_name="servicenowautomation-mcp",
            environment="test",
        )

    assert calls == [{"connection_string": "InstrumentationKey=test-key"}]


async def test_server_lifespan_initializes_telemetry(monkeypatch):
    calls = []
    config = ServiceNowKnowledgeConfig(
        _env_file=None,
        applicationinsights_connection_string="InstrumentationKey=test-key",
        environment="test",
    )

    monkeypatch.setattr(
        server_module,
        "set_up_telemetry",
        lambda **kwargs: calls.append(kwargs),
    )
    server = create_mcp(config_provider=lambda: config)

    async with Client(server) as client:
        await client.list_tools()

    assert calls == [
        {
            "connection_string": "InstrumentationKey=test-key",
            "service_name": "servicenowautomation-mcp",
            "environment": "test",
        }
    ]
