from pydantic import BaseModel, ConfigDict, Field


class KnowledgeSearchCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    number: str | None = None
    title: str
    snippet: str | None = None
    score: float | None = None
    rank: int = Field(ge=1)
    link: str | None = None
    knowledge_base: str | None = None


class KnowledgeSearchResponse(BaseModel):
    query: str
    total: int = Field(ge=0)
    results: list[KnowledgeSearchCandidate]


class KnowledgeCategory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    label: str
    value: str | None = None
    parent_id: str | None = None
    full_category: str | None = None
    active: bool | None = None


class KnowledgeCategoriesResponse(BaseModel):
    total: int = Field(ge=0)
    results: list[KnowledgeCategory]


class KnowledgeArticle(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    number: str | None = None
    title: str
    content: str
    knowledge_base: str | None = None
    category: str | None = None
    workflow: str | None = None
    valid_to: str | None = None
    updated_on: str | None = None
    link: str | None = None


class KnowledgeAttachment(BaseModel):
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
    )
