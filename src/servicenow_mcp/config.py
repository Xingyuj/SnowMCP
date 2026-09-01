from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceNowKnowledgeConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    servicenow_base_url: str = ""
    servicenow_knowledge_api_path: str = "api/sn_km_api/knowledge/articles"
    servicenow_categories_api_path: str = "api/now/table/kb_category"
    servicenow_access_token: SecretStr | None = Field(default=None, repr=False)
    servicenow_client_id: str | None = None
    servicenow_client_secret: SecretStr | None = Field(default=None, repr=False)
    servicenow_oauth_token_path: str = "oauth_token.do"
    servicenow_oauth_scope: str | None = None
    apim_auth_enabled: bool = False
    apim_scope_claim_names: str = "scp,scope,roles"
    apim_subject_claim_names: str = "oid,sub"
    mcp_search_scope: str = "knowledge.search"
    mcp_category_read_scope: str = "knowledge.category.read"
    mcp_article_read_scope: str = "knowledge.article.read"
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
    servicenow_category_fields: str = "sys_id,label,value,parent_id,full_category,active"
    request_timeout_seconds: float = Field(default=10, gt=0, le=120)
    default_search_limit: int = Field(default=5, ge=1)
    max_search_limit: int = Field(default=20, ge=1)
    category_page_size: int = Field(default=100, ge=1, le=500)
    max_article_content_chars: int = Field(default=100_000, ge=100)
    transient_retry_attempts: int = Field(default=2, ge=0, le=5)
    retry_backoff_seconds: float = Field(default=0.2, ge=0, le=10)
    log_level: str = "INFO"
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

    @property
    def category_fields(self) -> tuple[str, ...]:
        return tuple(
            field.strip() for field in self.servicenow_category_fields.split(",") if field.strip()
        )

    @property
    def apim_scope_claims(self) -> tuple[str, ...]:
        return tuple(
            name.strip() for name in self.apim_scope_claim_names.split(",") if name.strip()
        )

    @property
    def apim_subject_claims(self) -> tuple[str, ...]:
        return tuple(
            name.strip() for name in self.apim_subject_claim_names.split(",") if name.strip()
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
        self.validate_apim_auth()

    def validate_apim_auth(self) -> None:
        if not self.apim_auth_enabled:
            return
        if not self.apim_scope_claims or not self.apim_subject_claims:
            raise ValueError("APIM scope and subject claim name lists must be non-empty")
        if not all(
            (
                self.mcp_search_scope.strip(),
                self.mcp_category_read_scope.strip(),
                self.mcp_article_read_scope.strip(),
            )
        ):
            raise ValueError("Every MCP tool scope must be non-empty")


@lru_cache
def get_config() -> ServiceNowKnowledgeConfig:
    return ServiceNowKnowledgeConfig()
