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
    workflow_state: str | None = None
    published: str | None = None
    valid_to: str | None = None
    updated_on: str | None = None
    link: str | None = None
