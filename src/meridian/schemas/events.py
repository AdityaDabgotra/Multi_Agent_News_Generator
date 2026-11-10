"""News event schema (a cluster of articles about the same real-world event)."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from meridian.schemas.common import Impact, MeridianModel


class NewsEvent(MeridianModel):
    event_id: UUID
    title: str = Field(min_length=1)
    first_seen_at: AwareDatetime
    last_updated_at: AwareDatetime
    status: Literal["developing", "stable", "closed"]
    article_ids: list[UUID] = Field(default_factory=list)
    entity_ids: list[UUID] = Field(default_factory=list)
    impact: Impact = Impact.LOW
    summary_claim_ids: list[UUID] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
