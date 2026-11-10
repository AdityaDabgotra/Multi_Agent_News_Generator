"""Generated article schema: every factual sentence maps to claims and evidence."""

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from meridian.schemas.common import MeridianModel, ShortStr


class ArticleSentence(MeridianModel):
    index: int = Field(ge=0)
    text: str = Field(min_length=1)
    kind: Literal["claim", "connective", "attribution", "uncertainty_note"]
    claim_ids: list[UUID] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _claims_need_ids(self) -> Self:
        if self.kind == "claim" and not self.claim_ids:
            raise ValueError("a 'claim' sentence must reference at least one claim id")
        return self


class GeneratedArticle(MeridianModel):
    article_id: UUID
    event_id: UUID | None = None
    version: int = Field(ge=1)
    genre: Literal["news", "profile", "commentary", "explainer", "verification_report"]
    headline: str = Field(min_length=1)
    sentences: list[ArticleSentence]
    unknowns: list[ShortStr] = Field(default_factory=list)
    status: Literal["draft", "audited", "pending_human", "approved", "published", "retracted"]
    model_ids: list[str] = Field(default_factory=list)
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _sentence_indexes(self) -> Self:
        indexes = [s.index for s in self.sentences]
        if indexes != list(range(len(indexes))):
            raise ValueError("sentence indexes must be 0..n-1 in order")
        return self
