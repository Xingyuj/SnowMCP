from pydantic import BaseModel, ConfigDict, Field


class KnowledgeSearchCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(description="ServiceNow sys_id of the candidate Knowledge Article.")
    number: str | None = Field(
        default=None,
        description="Human-readable ServiceNow article number, when available.",
    )
    title: str = Field(description="Title of the candidate Knowledge Article.")
    snippet: str | None = Field(
        default=None,
        description="Short search-result excerpt or description, when available.",
    )
    score: float | None = Field(
        default=None,
        description="Relevance score supplied by ServiceNow, when available.",
    )
    rank: int = Field(ge=1, description="One-based result order returned by ServiceNow.")
    link: str | None = Field(
        default=None,
        description="ServiceNow URL for the candidate article, when available.",
    )
    knowledge_base: str | None = Field(
        default=None,
        description="Display value of the article's Knowledge Base, when available.",
    )


class KnowledgeSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(description="Normalized query used for the ServiceNow search.")
    total: int = Field(ge=0, description="Number of candidates returned in this response.")
    results: list[KnowledgeSearchCandidate] = Field(
        description="Ranked Knowledge Article candidates returned by ServiceNow."
    )


class KnowledgeCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(description="ServiceNow sys_id of the Knowledge Base category.")
    label: str = Field(description="Human-readable category label.")
    value: str | None = Field(
        default=None,
        description="ServiceNow category value used by scripts, when available.",
    )
    parent_id: str | None = Field(
        default=None,
        description="ServiceNow sys_id of the parent category, when available.",
    )
    full_category: str | None = Field(
        default=None,
        description="Full category hierarchy path, when available.",
    )
    active: bool | None = Field(
        default=None,
        description="Whether the category is active, when ServiceNow provides the value.",
    )


class KnowledgeCategoriesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total: int = Field(ge=0, description="Total number of accessible categories returned.")
    results: list[KnowledgeCategory] = Field(
        description="Accessible Knowledge Base categories in hierarchy order."
    )


class KnowledgeArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(description="ServiceNow sys_id of the Knowledge Article.")
    number: str | None = Field(
        default=None,
        description="Human-readable ServiceNow article number, when available.",
    )
    title: str = Field(description="Canonical title of the Knowledge Article.")
    content: str = Field(description="Canonical article body returned by ServiceNow.")
    knowledge_base: str | None = Field(
        default=None,
        description="Display value of the article's Knowledge Base, when available.",
    )
    category: str | None = Field(
        default=None,
        description="Display value of the article's category, when available.",
    )
    workflow_state: str | None = Field(
        default=None,
        description="ServiceNow publication workflow state, when available.",
    )
    published: str | None = Field(
        default=None,
        description="ServiceNow publication timestamp or date, when available.",
    )
    valid_to: str | None = Field(
        default=None,
        description="ServiceNow article validity end date, when available.",
    )
    updated_on: str | None = Field(
        default=None,
        description="ServiceNow last-updated timestamp, when available.",
    )
    link: str | None = Field(
        default=None,
        description="ServiceNow URL for the canonical article, when available.",
    )


class KnowledgeAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    article_id: str = Field(
        description="ServiceNow sys_id of the knowledge article that owns the attachment.",
        examples=["9b4f5c1adb1230106a3e1b1f299619d2"],
    )
    attachment_id: str = Field(
        description="ServiceNow sys_id of the attachment.",
        examples=["2f6e8a91db5630106a3e1b1f299619a7"],
    )
    filename: str | None = Field(
        default=None,
        description="Original attachment filename, when provided by ServiceNow.",
        examples=["network-troubleshooting.pdf"],
    )
    content_type: str = Field(
        description="MIME type of the attachment content.",
        examples=["application/pdf"],
    )
    size_bytes: int = Field(
        ge=0,
        description="Size of the decoded attachment content in bytes.",
        examples=[24576],
    )
    content_base64: str = Field(
        description="Base64-encoded attachment content.",
        examples=["SGVsbG8gd29ybGQ="],
        json_schema_extra={"contentEncoding": "base64"},
    )
