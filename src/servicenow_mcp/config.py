from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceNowKnowledgeConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    servicenow_base_url: str = ""
    servicenow_knowledge_api_path: str = "api/sn_km_api/knowledge/articles"
    servicenow_access_token: SecretStr | None = Field(default=None, repr=False)
    servicenow_client_id: str | None = None
    servicenow_client_secret: SecretStr | None = Field(default=None, repr=False)
    servicenow_oauth_token_path: str = "oauth_token.do"
    servicenow_oauth_scope: str | None = None
    mcp_auth_enabled: bool = False
    mcp_jwt_jwks_uri: str | None = None
    mcp_jwt_public_key: SecretStr | None = Field(default=None, repr=False)
    mcp_jwt_issuer: str | None = None
    mcp_jwt_audience: str | None = None
    mcp_jwt_algorithm: str = "RS256"
    mcp_search_scope: str = "knowledge.search"
    mcp_article_read_scope: str = "knowledge.article.read"
    mcp_attachment_read_scope: str = "knowledge.attachment.read"
    servicenow_api_version: str | None = None
    servicenow_knowledge_base: str | None = None
    servicenow_language: str | None = None
    servicenow_search_fields: str = (
        "sys_id,number,short_description,description,kb_knowledge_base,score"
    )
    servicenow_article_fields: str = (
        "sys_id,number,short_description,text,kb_knowledge_base,kb_category,workflow_state,"
        "published,valid_to,sys_updated_on"
    )
    request_timeout_seconds: float = Field(default=10, gt=0, le=120)
    default_search_limit: int = Field(default=5, ge=1)
    max_search_limit: int = Field(default=20, ge=1)
    max_article_content_chars: int = Field(default=100_000, ge=100)
    max_attachment_bytes: int = Field(default=5_000_000, ge=1)
    transient_retry_attempts: int = Field(default=2, ge=0, le=5)
    retry_backoff_seconds: float = Field(default=0.2, ge=0, le=10)
    log_level: str = "INFO"
    transport: Literal["stdio", "http", "sse", "streamable-http"] = "http"
    host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)

    @field_validator("servicenow_base_url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def search_fields(self) -> tuple[str, ...]:
        return tuple(
            field.strip() for field in self.servicenow_search_fields.split(",") if field.strip()
        )

    @property
    def article_fields(self) -> tuple[str, ...]:
        return tuple(
            field.strip() for field in self.servicenow_article_fields.split(",") if field.strip()
        )

    def validate_runtime(self) -> None:
        if not self.servicenow_base_url:
            raise ValueError("SERVICENOW_BASE_URL is required")
        if not self.servicenow_access_token and not (
            self.servicenow_client_id and self.servicenow_client_secret
        ):
            raise ValueError(
                "Configure SERVICENOW_ACCESS_TOKEN or both SERVICENOW_CLIENT_ID and "
                "SERVICENOW_CLIENT_SECRET"
            )
        if self.default_search_limit > self.max_search_limit:
            raise ValueError("DEFAULT_SEARCH_LIMIT cannot exceed MAX_SEARCH_LIMIT")
        self.validate_mcp_auth()

    def validate_mcp_auth(self) -> None:
        if not self.mcp_auth_enabled:
            return
        configured_keys = bool(self.mcp_jwt_jwks_uri) + bool(self.mcp_jwt_public_key)
        if configured_keys != 1:
            raise ValueError(
                "When MCP_AUTH_ENABLED=true, configure exactly one of MCP_JWT_JWKS_URI "
                "or MCP_JWT_PUBLIC_KEY"
            )
        if not self.mcp_jwt_issuer or not self.mcp_jwt_audience:
            raise ValueError(
                "MCP_JWT_ISSUER and MCP_JWT_AUDIENCE are required when MCP auth is enabled"
            )
        if not all(
            (
                self.mcp_search_scope.strip(),
                self.mcp_article_read_scope.strip(),
                self.mcp_attachment_read_scope.strip(),
            )
        ):
            raise ValueError("Every MCP tool scope must be non-empty")


@lru_cache
def get_config() -> ServiceNowKnowledgeConfig:
    return ServiceNowKnowledgeConfig()
