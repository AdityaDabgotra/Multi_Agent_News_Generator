"""Evidence strength computation (blueprint 5.6).

For each origin group g and stance:  w_g = max over items in g of (r * d * t * q)
  r = source reliability, d = directness weight, t = temporal relevance, q = stance quality.
Mass for a stance:  M = 1 - prod(1 - w_g)  over groups with that stance.
Only *origin groups* are counted, never URLs: ten copies of one wire story are one group.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from meridian.schemas.common import Directness, Stance
from meridian.schemas.verification import EvidenceStrength
from meridian.verification.policy import VerificationPolicy


@dataclass(frozen=True, slots=True)
class WeightedEvidence:
    """Minimal, pure-logic view of one verified evidence item."""

    evidence_id: UUID
    origin_group_id: UUID
    stance: Stance
    directness: Directness
    reliability: float
    temporal_relevance: float = 1.0
    stance_quality: float = 1.0

    def __post_init__(self) -> None:
        for name in ("reliability", "temporal_relevance", "stance_quality"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")


@dataclass(frozen=True, slots=True)
class GroupWeight:
    origin_group_id: UUID
    stance: Stance
    weight: float
    primary_weight: float  # best weight among PRIMARY-directness items in the group (0 if none)

    def is_credible(self, policy: VerificationPolicy) -> bool:
        return self.weight >= policy.credible_group_threshold

    def is_credible_primary(self, policy: VerificationPolicy) -> bool:
        return self.primary_weight >= policy.credible_group_threshold


def item_weight(item: WeightedEvidence, policy: VerificationPolicy) -> float:
    directness = policy.directness_weights[item.directness]
    return item.reliability * directness * item.temporal_relevance * item.stance_quality


def group_weights(
    items: Iterable[WeightedEvidence], policy: VerificationPolicy
) -> list[GroupWeight]:
    """Collapse items into one weight per (origin group, stance). CONTEXT/IRRELEVANT are ignored."""
    best: dict[tuple[UUID, Stance], float] = {}
    best_primary: dict[tuple[UUID, Stance], float] = {}
    for item in items:
        if item.stance not in (Stance.SUPPORTS, Stance.REFUTES):
            continue
        key = (item.origin_group_id, item.stance)
        weight = item_weight(item, policy)
        best[key] = max(best.get(key, 0.0), weight)
        if item.directness is Directness.PRIMARY:
            best_primary[key] = max(best_primary.get(key, 0.0), weight)
    return [
        GroupWeight(
            origin_group_id=group,
            stance=stance,
            weight=weight,
            primary_weight=best_primary.get((group, stance), 0.0),
        )
        for (group, stance), weight in best.items()
    ]


def combine_mass(weights: Iterable[float]) -> float:
    """Noisy-OR combination: 1 - prod(1 - w). Monotone non-decreasing in every input."""
    remaining = 1.0
    for weight in weights:
        remaining *= 1.0 - weight
    return min(1.0, max(0.0, 1.0 - remaining))


def compute_strength(
    items: Iterable[WeightedEvidence],
    coverage: float,
    policy: VerificationPolicy,
) -> EvidenceStrength:
    """Compute the explainable evidence-strength summary for one claim."""
    if not 0.0 <= coverage <= 1.0:
        raise ValueError(f"coverage must be in [0, 1], got {coverage}")
    groups = group_weights(items, policy)
    support = [g for g in groups if g.stance is Stance.SUPPORTS]
    refute = [g for g in groups if g.stance is Stance.REFUTES]
    return EvidenceStrength(
        support_mass=combine_mass(g.weight for g in support),
        refute_mass=combine_mass(g.weight for g in refute),
        coverage=coverage,
        n_support_groups=sum(1 for g in support if g.is_credible(policy)),
        n_refute_groups=sum(1 for g in refute if g.is_credible(policy)),
        has_primary_support=any(g.is_credible_primary(policy) for g in support),
        has_primary_refute=any(g.is_credible_primary(policy) for g in refute),
    )
