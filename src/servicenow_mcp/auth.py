from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

from .errors import ErrorCode, KnowledgeMcpError


class AuthorizationContext(BaseModel):
    """Reserved context for a confirmed end-user authorization mechanism."""

    model_config = ConfigDict(extra="ignore")
    subject_id: str | None = None
    delegated_token: str | None = Field(default=None, repr=False, exclude=True)


class ServiceNowAuthenticator(ABC):
    @abstractmethod
    def headers(self, context: AuthorizationContext | None = None) -> dict[str, str]: ...


class IntegrationTokenAuthenticator(ServiceNowAuthenticator):
    """Authenticate as the configured integration identity."""

    def __init__(self, token: str | None) -> None:
        self._token = token

    def headers(self, context: AuthorizationContext | None = None) -> dict[str, str]:
        if context and context.delegated_token:
            return {"Authorization": f"Bearer {context.delegated_token}"}
        if not self._token:
            raise KnowledgeMcpError(
                ErrorCode.UNAUTHENTICATED, "ServiceNow authentication is not configured"
            )
        return {"Authorization": f"Bearer {self._token}"}
