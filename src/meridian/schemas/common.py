"""Shared enums, base model and small value objects used by every schema."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = "1.0"

ShortStr = Annotated[str, StringConstraints(max_length=500)]


class MeridianModel(BaseModel):
    """Base for all schema models: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class Trust(StrEnum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


class SourceType(StrEnum):
    PRIMARY_OFFICIAL = "primary_official"
    PRIMARY_ORIGINAL_REPORTING = "primary_original_reporting"
    SECONDARY = "secondary"
    AGGREGATOR = "aggregator"
    FACT_CHECK = "fact_check"
    SOCIAL = "social"
    ACADEMIC = "academic"


class Directness(StrEnum):
    PRIMARY = "primary"
    DIRECT_SECONDARY = "direct_secondary"
    INDIRECT = "indirect"


class Stance(StrEnum):
    SUPPORTS = "supports"
    REFUTES = "refutes"
    CONTEXT = "context"
    IRRELEVANT = "irrelevant"


class ClaimType(StrEnum):
    EVENT = "event"
    STATISTIC = "statistic"
    QUOTE = "quote"
    ATTRIBUTION = "attribution"
    CAUSAL = "causal"
    PREDICTION = "prediction"
    OPINION = "opinion"
    DEFINITION = "definition"


class Impact(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Label(StrEnum):
    """Verification labels. There is deliberately no plain true/false."""

    STRONGLY_SUPPORTED = "strongly_supported"
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONTRADICTED = "contradicted"
    MIXED_EVIDENCE = "mixed_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNVERIFIED = "unverified"
    OUTDATED_OR_MISLEADING_CONTEXT = "outdated_or_misleading_context"


class AdversarialOutcome(StrEnum):
    NONE_FOUND = "none_found"
    FOUND_REFUTATION = "found_refutation"
    FOUND_CAVEAT = "found_caveat"
    NOT_RUN = "not_run"


class TemporalFlag(StrEnum):
    OLD_AS_NEW = "old_as_new"
    PERIOD_MISMATCH = "period_mismatch"
    SUPERSEDED = "superseded"
    MISSING_QUALIFIER = "missing_qualifier"


class VerificationStatus(StrEnum):
    QUOTE_VERIFIED = "quote_verified"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"


class ConfidenceMeta(MeridianModel):
    """Confidence with its provenance. ``self_reported`` must never be shown as a probability."""

    kind: Literal["self_reported", "rule_derived", "calibrated"]
    value: float | None = Field(default=None, ge=0, le=1)
    note: ShortStr | None = None

    @model_validator(mode="after")
    def _calibrated_needs_value(self) -> Self:
        if self.kind == "calibrated" and self.value is None:
            raise ValueError("calibrated confidence requires a value")
        return self


class Usage(MeridianModel):
    llm_calls: int = Field(default=0, ge=0)
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)
    model_ids: list[str] = Field(default_factory=list)


class BudgetSlice(MeridianModel):
    max_llm_calls: int = Field(ge=0)
    max_tokens: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    deadline: AwareDatetime
    max_depth: int = Field(ge=0)
