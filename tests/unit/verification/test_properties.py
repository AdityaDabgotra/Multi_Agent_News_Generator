"""Property-based tests: invariants that must hold for ANY input."""

from hypothesis import given, settings
from hypothesis import strategies as st

from meridian.core import uuid7
from meridian.schemas import (
    AdversarialOutcome,
    EvidenceStrength,
    Impact,
    Label,
    TemporalFlag,
    VerificationFeatures,
)
from meridian.verification import combine_mass, decide, default_policy

unit = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


@given(st.lists(unit, max_size=12), unit)
def test_adding_an_independent_group_never_lowers_mass(weights: list[float], extra: float) -> None:
    assert combine_mass([*weights, extra]) >= combine_mass(weights) - 1e-12


@given(st.lists(unit, max_size=12))
def test_mass_stays_in_unit_interval(weights: list[float]) -> None:
    assert 0.0 <= combine_mass(weights) <= 1.0


@given(st.lists(unit, max_size=12))
def test_mass_is_order_independent(weights: list[float]) -> None:
    assert abs(combine_mass(weights) - combine_mass(list(reversed(weights)))) < 1e-9


features_strategy = st.builds(
    VerificationFeatures,
    strength=st.builds(
        EvidenceStrength,
        support_mass=unit,
        refute_mass=unit,
        coverage=unit,
        n_support_groups=st.integers(0, 8),
        n_refute_groups=st.integers(0, 8),
        has_primary_support=st.booleans(),
        has_primary_refute=st.booleans(),
    ),
    impact=st.sampled_from(Impact),
    needs_context=st.booleans(),
    temporal_flags=st.frozensets(st.sampled_from(TemporalFlag)),
    scope_mismatch=st.booleans(),
    circular_sourcing=st.booleans(),
    adversarial=st.sampled_from(AdversarialOutcome),
)


@settings(max_examples=300)
@given(features_strategy)
def test_decide_is_total_and_returns_valid_label_and_rule(features: VerificationFeatures) -> None:
    decision = decide(features, default_policy())
    assert isinstance(decision.label, Label)
    assert decision.rule_id in {f"R{i}" for i in range(1, 9)}


@settings(max_examples=300)
@given(features_strategy)
def test_strong_support_never_with_circular_flag_or_refutation(
    features: VerificationFeatures,
) -> None:
    decision = decide(features, default_policy())
    if decision.label is Label.STRONGLY_SUPPORTED:
        assert not features.circular_sourcing
        assert features.adversarial is not AdversarialOutcome.FOUND_REFUTATION
        assert features.strength.refute_mass < 0.15
        assert not features.temporal_flags


@settings(max_examples=300)
@given(features_strategy)
def test_low_coverage_always_unverified(features: VerificationFeatures) -> None:
    policy = default_policy()
    decision = decide(features, policy)
    if features.strength.coverage < policy.min_coverage:
        assert decision.label is Label.UNVERIFIED and decision.rule_id == "R1"


def test_uuid_helper_import_is_used() -> None:
    assert uuid7().version == 7
