"""Shared fixtures and helpers for all tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest

from meridian.core import uuid7
from meridian.schemas import (
    AdversarialOutcome,
    Directness,
    EvidenceStrength,
    Impact,
    Stance,
    TemporalFlag,
    VerificationFeatures,
)
from meridian.verification import VerificationPolicy, WeightedEvidence, default_policy

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def policy() -> VerificationPolicy:
    return default_policy()


@pytest.fixture
def make_item() -> Callable[..., WeightedEvidence]:
    def _make(
        *,
        group: UUID | None = None,
        stance: Stance = Stance.SUPPORTS,
        directness: Directness = Directness.DIRECT_SECONDARY,
        reliability: float = 0.9,
        temporal: float = 1.0,
        quality: float = 1.0,
    ) -> WeightedEvidence:
        return WeightedEvidence(
            evidence_id=uuid7(),
            origin_group_id=group or uuid7(),
            stance=stance,
            directness=directness,
            reliability=reliability,
            temporal_relevance=temporal,
            stance_quality=quality,
        )

    return _make


@pytest.fixture
def make_features() -> Callable[..., VerificationFeatures]:
    def _make(
        *,
        support_mass: float = 0.0,
        refute_mass: float = 0.0,
        coverage: float = 0.9,
        n_support: int = 0,
        n_refute: int = 0,
        primary_support: bool = False,
        primary_refute: bool = False,
        impact: Impact = Impact.LOW,
        needs_context: bool = False,
        flags: frozenset[TemporalFlag] = frozenset(),
        scope_mismatch: bool = False,
        circular: bool = False,
        adversarial: AdversarialOutcome = AdversarialOutcome.NONE_FOUND,
    ) -> VerificationFeatures:
        return VerificationFeatures(
            strength=EvidenceStrength(
                support_mass=support_mass,
                refute_mass=refute_mass,
                coverage=coverage,
                n_support_groups=n_support,
                n_refute_groups=n_refute,
                has_primary_support=primary_support,
                has_primary_refute=primary_refute,
            ),
            impact=impact,
            needs_context=needs_context,
            temporal_flags=flags,
            scope_mismatch=scope_mismatch,
            circular_sourcing=circular,
            adversarial=adversarial,
        )

    return _make
