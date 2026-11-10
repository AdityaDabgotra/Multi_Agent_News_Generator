"""Agent task/result messages and failure types."""

from enum import StrEnum
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from meridian.schemas.common import (
    SCHEMA_VERSION,
    BudgetSlice,
    ConfidenceMeta,
    MeridianModel,
    ShortStr,
    Trust,
    Usage,
)


class UntrustedText(MeridianModel):
    """Text from the outside world. It is data, never an instruction."""

    text: str
    source_url: str | None = None
    trust: Trust = Trust.UNTRUSTED

    @model_validator(mode="after")
    def _must_be_untrusted(self) -> Self:
        if self.trust is not Trust.UNTRUSTED:
            raise ValueError("UntrustedText.trust must be 'untrusted'")
        return self


class FailureCode(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    PROVIDER_DOWN = "provider_down"
    SCHEMA_INVALID = "schema_invalid"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TOOL_ERROR = "tool_error"
    INJECTION_SUSPECTED = "injection_suspected"
    NO_EVIDENCE = "no_evidence"
    POLICY_BLOCKED = "policy_blocked"
    INTERNAL = "internal"


class AgentFailure(MeridianModel):
    code: FailureCode
    retryable: bool
    message: ShortStr
    details: dict[str, Any] = Field(default_factory=dict)
    occurred_at: AwareDatetime


class AgentTask(MeridianModel):
    schema_version: str = SCHEMA_VERSION
    task_id: UUID
    investigation_id: UUID
    parent_task_id: UUID | None = None
    agent_id: str = Field(pattern=r"^A\d{2}$")
    agent_version: str
    prompt_version: str
    objective: ShortStr
    input_refs: dict[str, list[UUID]] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    budget: BudgetSlice
    attempt: int = Field(default=0, ge=0)
    idempotency_key: str
    created_at: AwareDatetime


class AgentResult(MeridianModel):
    schema_version: str = SCHEMA_VERSION
    task_id: UUID
    agent_id: str = Field(pattern=r"^A\d{2}$")
    status: Literal["ok", "partial", "failed"]
    output_refs: dict[str, list[UUID]] = Field(default_factory=dict)
    summary: ShortStr | None = None
    confidence: ConfidenceMeta | None = None
    warnings: list[ShortStr] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    error: AgentFailure | None = None

    @model_validator(mode="after")
    def _failed_requires_error(self) -> Self:
        if self.status == "failed" and self.error is None:
            raise ValueError("status 'failed' requires an error")
        if self.status != "failed" and self.error is not None:
            raise ValueError("error is only allowed when status is 'failed'")
        return self


__all__ = [
    "AgentFailure",
    "AgentResult",
    "AgentTask",
    "FailureCode",
    "UntrustedText",
]
