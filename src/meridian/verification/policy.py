"""Verification policy: thresholds for the decision table, loaded from YAML or defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ConfigDict, Field, ValidationError, model_validator

from meridian.core.errors import PolicyError
from meridian.schemas.common import Directness, MeridianModel, TemporalFlag


class _Frozen(MeridianModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OutdatedRule(_Frozen):
    min_support_mass: float = Field(default=0.25, ge=0, le=1)


class ContradictedRule(_Frozen):
    min_refute_mass: float = Field(default=0.6, ge=0, le=1)
    min_refute_groups: int = Field(default=2, ge=1)
    max_support_mass: float = Field(default=0.25, ge=0, le=1)


class StronglySupportedRule(_Frozen):
    max_refute_mass: float = Field(default=0.15, ge=0, le=1)
    min_groups_with_primary: int = Field(default=2, ge=1)
    min_groups_without_primary: int = Field(default=3, ge=1)


class SupportedRule(_Frozen):
    min_support_mass: float = Field(default=0.6, ge=0, le=1)
    min_groups: int = Field(default=2, ge=1)
    max_refute_mass: float = Field(default=0.25, ge=0, le=1)


class MixedRule(_Frozen):
    min_support_mass: float = Field(default=0.35, ge=0, le=1)
    min_refute_mass: float = Field(default=0.35, ge=0, le=1)


class PartiallySupportedRule(_Frozen):
    min_support_mass: float = Field(default=0.35, ge=0, le=1)


def _default_directness_weights() -> dict[Directness, float]:
    return {
        Directness.PRIMARY: 1.0,
        Directness.DIRECT_SECONDARY: 0.7,
        Directness.INDIRECT: 0.4,
    }


def _default_misleading_flags() -> frozenset[TemporalFlag]:
    return frozenset(
        {TemporalFlag.OLD_AS_NEW, TemporalFlag.SUPERSEDED, TemporalFlag.MISSING_QUALIFIER}
    )


class VerificationPolicy(_Frozen):
    version: str = "1.0"
    min_coverage: float = Field(default=0.6, ge=0, le=1)
    credible_group_threshold: float = Field(default=0.35, ge=0, le=1)
    directness_weights: dict[Directness, float] = Field(default_factory=_default_directness_weights)
    misleading_temporal_flags: frozenset[TemporalFlag] = Field(
        default_factory=_default_misleading_flags
    )
    outdated: OutdatedRule = OutdatedRule()
    contradicted: ContradictedRule = ContradictedRule()
    strongly_supported: StronglySupportedRule = StronglySupportedRule()
    supported: SupportedRule = SupportedRule()
    mixed: MixedRule = MixedRule()
    partially_supported: PartiallySupportedRule = PartiallySupportedRule()

    @model_validator(mode="after")
    def _consistency(self) -> VerificationPolicy:
        missing = set(Directness) - set(self.directness_weights)
        if missing:
            names = sorted(d.value for d in missing)
            raise ValueError(f"directness_weights missing: {names}")
        for key, weight in self.directness_weights.items():
            if not 0 <= weight <= 1:
                raise ValueError(f"directness weight for {key.value} must be in [0, 1]")
        if self.strongly_supported.max_refute_mass > self.supported.max_refute_mass:
            raise ValueError("strongly_supported.max_refute_mass must not exceed supported's")
        return self


def default_policy() -> VerificationPolicy:
    """Policy built from in-code defaults (kept in sync with config/verification_policy.yaml)."""
    return VerificationPolicy()


def load_policy(path: str | Path) -> VerificationPolicy:
    """Load and validate a policy YAML file. Raises PolicyError on any problem."""
    file = Path(path)
    try:
        raw: Any = yaml.safe_load(file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyError(f"policy file not found: {file}") from exc
    except yaml.YAMLError as exc:
        raise PolicyError(f"policy file is not valid YAML: {file}") from exc
    if not isinstance(raw, dict):
        raise PolicyError("policy file must contain a mapping at the top level")
    try:
        return VerificationPolicy.model_validate(raw)
    except ValidationError as exc:
        raise PolicyError(f"invalid policy: {exc}") from exc
