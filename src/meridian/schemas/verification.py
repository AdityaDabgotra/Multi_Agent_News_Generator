"""Verification schemas: evidence strength, decision features and verification results."""

from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from meridian.schemas.common import (
    AdversarialOutcome,
    Impact,
    Label,
    MeridianModel,
    ShortStr,
    TemporalFlag,
)


class EvidenceStrength(MeridianModel):
    """Explainable evidence summary. Masses are in [0, 1]; counts are credible origin groups."""

    support_mass: float = Field(ge=0, le=1)
    refute_mass: float = Field(ge=0, le=1)
    coverage: float = Field(ge=0, le=1)
    n_support_groups: int = Field(ge=0)
    n_refute_groups: int = Field(ge=0)
    has_primary_support: bool
    has_primary_refute: bool


class VerificationFeatures(MeridianModel):
    """Everything the decision table needs. The label is a pure function of this object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    strength: EvidenceStrength
    impact: Impact = Impact.LOW
    needs_context: bool = False
    temporal_flags: frozenset[TemporalFlag] = frozenset()
    scope_mismatch: bool = False
    circular_sourcing: bool = False
    adversarial: AdversarialOutcome = AdversarialOutcome.NOT_RUN


class VerificationResult(MeridianModel):
    verification_id: UUID
    claim_id: UUID
    label: Label
    rule_id: str = Field(pattern=r"^R[1-8]$")
    strength: EvidenceStrength
    calibrated_probability: float | None = Field(default=None, ge=0, le=1)
    calibration_version: str | None = None
    key_evidence_ids: list[UUID] = Field(default_factory=list)
    refuting_evidence_ids: list[UUID] = Field(default_factory=list)
    missing_information: list[ShortStr] = Field(default_factory=list)
    adversarial_queries: list[ShortStr] = Field(default_factory=list)
    adversarial_outcome: AdversarialOutcome
    justification: str
    computed_at: AwareDatetime
    claim_version: int = Field(ge=1)
    pipeline_version: str

    @model_validator(mode="after")
    def _calibration_consistency(self) -> Self:
        if self.calibrated_probability is not None and not self.calibration_version:
            raise ValueError("calibrated_probability requires calibration_version")
        return self
