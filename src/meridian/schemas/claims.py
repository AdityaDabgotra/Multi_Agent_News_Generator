"""Claim schema: atomic, decontextualized, verifiable statements extracted from articles."""

from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from meridian.schemas.common import ClaimType, Impact, MeridianModel, ShortStr


class Claim(MeridianModel):
    claim_id: UUID
    article_id: UUID
    event_id: UUID | None = None
    text: str = Field(min_length=10, max_length=600)
    original_span: tuple[int, int]
    claim_type: ClaimType
    check_worthiness: float = Field(ge=0, le=1)
    verifiable: bool
    non_verifiable_reason: ShortStr | None = None
    needs_context: bool = False
    impact: Impact
    reference_period: tuple[AwareDatetime | None, AwareDatetime | None] = (None, None)
    parent_claim_id: UUID | None = None
    entities: list[UUID] = Field(default_factory=list)
    claim_version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _validate(self) -> Self:
        start, end = self.original_span
        if start < 0 or end <= start:
            raise ValueError("original_span must satisfy 0 <= start < end")
        if not self.verifiable and not self.non_verifiable_reason:
            raise ValueError("non-verifiable claims need a non_verifiable_reason")
        period_start, period_end = self.reference_period
        if period_start and period_end and period_end < period_start:
            raise ValueError("reference_period end precedes start")
        return self
