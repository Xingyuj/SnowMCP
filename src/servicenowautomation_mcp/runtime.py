from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from threading import Lock
from typing import Protocol

from fastmcp import FastMCP

from .config import ServiceNowKnowledgeConfig
from .knowledge.client import ServiceNowKnowledgeApiClient
from .knowledge.service import KnowledgeService
from .security.servicenow_auth import (
    ClientCredentialsAuthenticator,
    IntegrationTokenAuthenticator,
    ServiceNowAuthenticator,
)
from .telemetry import set_up_telemetry


class TelemetrySetup(Protocol):
    def __call__(
        self,
        *,
        connection_string: str | None,
        service_name: str,
        environment: str,
    ) -> bool: ...


ServiceBuilder = Callable[
    [ServiceNowKnowledgeConfig],
    tuple[KnowledgeService, ServiceNowKnowledgeApiClient],
]


def build_service(
    config: ServiceNowKnowledgeConfig,
) -> tuple[KnowledgeService, ServiceNowKnowledgeApiClient]:
    config.validate_runtime()
    authenticator: ServiceNowAuthenticator
    if config.servicenow_access_token:
        authenticator = IntegrationTokenAuthenticator(
            config.servicenow_access_token.get_secret_value()
        )
    else:
        assert config.servicenow_client_id is not None
        assert config.servicenow_client_secret is not None
        authenticator = ClientCredentialsAuthenticator(
            base_url=config.servicenow_base_url,
            client_id=config.servicenow_client_id,
            client_secret=config.servicenow_client_secret.get_secret_value(),
            token_path=config.servicenow_oauth_token_path,
            scope=config.servicenow_oauth_scope,
            timeout=config.request_timeout_seconds,
        )
    client = ServiceNowKnowledgeApiClient(config, authenticator)
    return KnowledgeService(client, config), client


class ServiceRuntime:
    """Own the lazily initialized service and its client lifecycle."""

    def __init__(
        self,
        config: ServiceNowKnowledgeConfig,
        service: KnowledgeService | None,
        telemetry_setup: TelemetrySetup = set_up_telemetry,
        service_builder: ServiceBuilder = build_service,
    ) -> None:
        self._config = config
        self._telemetry_setup = telemetry_setup
        self._service_builder = service_builder
        self._state: dict[str, object] = {"service": service}
        self._lock = Lock()
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    @asynccontextmanager
    async def lifespan(self, _: FastMCP) -> AsyncIterator[dict[str, object]]:
        self._telemetry_setup(
            connection_string=self._config.applicationinsights_connection_string,
            service_name="servicenowautomation-mcp",
            environment=self._config.environment,
        )
        self._ready = True
        try:
            yield self._state
        finally:
            self._ready = False
            owned_client = self._state.get("owned_client")
            if isinstance(owned_client, ServiceNowKnowledgeApiClient):
                await owned_client.aclose()

    def resolve_service(self) -> KnowledgeService:
        current = self._state.get("service")
        if isinstance(current, KnowledgeService):
            return current
        with self._lock:
            current = self._state.get("service")
            if isinstance(current, KnowledgeService):
                return current
            current, client = self._service_builder(self._config)
            self._state["service"] = current
            self._state["owned_client"] = client
            return current
