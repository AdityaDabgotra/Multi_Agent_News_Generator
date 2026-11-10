"""Evidence schema: every piece of evidence is traceable to a stored snapshot."""

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from meridian.schemas.common import (
    ConfidenceMeta,
    Directness,
    MeridianModel,
    SourceType,
    Stance,
    VerificationStatus,
)


class Evidence(MeridianModel):
    evidence_id: UUID
    claim_ids: list[UUID] = Field(min_length=1)
    source_id: UUID
    article_id: UUID | None = None
    url: str
    publisher: str
    author: str | None = None
    published_at: AwareDatetime | None = None
    retrieved_at: AwareDatetime
    snapshot_ref: str
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    excerpt: str = Field(min_length=1, max_length=600)
    excerpt_char_start: int = Field(ge=0)
    excerpt_char_end: int = Field(ge=1)
    evidence_type: SourceType
    directness: Directness
    stance: Stance
    stance_confidence: ConfidenceMeta
    origin_group_id: UUID | None = None
    credibility_profile_id: UUID | None = None
    extraction_method: Literal["llm_quarantined", "rule", "api"]
    verification_status: VerificationStatus

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.excerpt_char_end <= self.excerpt_char_start:
            raise ValueError("excerpt_char_end must be greater than excerpt_char_start")
        return self
