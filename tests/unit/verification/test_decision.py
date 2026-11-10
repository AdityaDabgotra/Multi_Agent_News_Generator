"""Exhaustive tests for the decision table: every rule R1..R8 and the evaluation order."""

from collections.abc import Callable

import pytest

from meridian.schemas import (
    AdversarialOutcome,
    Impact,
    Label,
    TemporalFlag,
    VerificationFeatures,
)
from meridian.verification import VerificationPolicy, decide

MakeFeatures = Callable[..., VerificationFeatures]


def test_r1_needs_context(policy: VerificationPolicy, make_features: MakeFeatures) -> None:
    d = decide(make_features(needs_context=True, support_mass=0.99, n_support=3), policy)
    assert (d.label, d.rule_id) == (Label.UNVERIFIED, "R1")


def test_r1_low_coverage_overrides_strong_evidence(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(
        make_features(coverage=0.5, support_mass=0.99, n_support=3, primary_support=True), policy
    )
    assert (d.label, d.rule_id) == (Label.UNVERIFIED, "R1")


def test_r2_outdated_context(policy: VerificationPolicy, make_features: MakeFeatures) -> None:
    d = decide(
        make_features(support_mass=0.7, n_support=2, flags=frozenset({TemporalFlag.OLD_AS_NEW})),
        policy,
    )
    assert (d.label, d.rule_id) == (Label.OUTDATED_OR_MISLEADING_CONTEXT, "R2")


def test_r2_requires_some_support(policy: VerificationPolicy, make_features: MakeFeatures) -> None:
    d = decide(make_features(support_mass=0.1, flags=frozenset({TemporalFlag.SUPERSEDED})), policy)
    assert d.rule_id == "R8"


def test_period_mismatch_alone_is_not_misleading_but_blocks_strong(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    flags = frozenset({TemporalFlag.PERIOD_MISMATCH})
    d = decide(
        make_features(support_mass=0.95, n_support=3, primary_support=True, flags=flags), policy
    )
    assert (d.label, d.rule_id) == (Label.SUPPORTED, "R5")


def test_r3_contradicted_by_two_groups(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(make_features(refute_mass=0.8, n_refute=2, support_mass=0.1), policy)
    assert (d.label, d.rule_id) == (Label.CONTRADICTED, "R3")


def test_r3_contradicted_by_single_primary(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(make_features(refute_mass=0.5, n_refute=1, primary_refute=True), policy)
    assert (d.label, d.rule_id) == (Label.CONTRADICTED, "R3")


def test_r3_not_applied_when_support_is_substantial(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(make_features(refute_mass=0.8, n_refute=2, support_mass=0.8, n_support=2), policy)
    assert d.rule_id == "R6"
    assert d.label is Label.MIXED_EVIDENCE


def test_r4_strong_with_primary_plus_independent(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(make_features(support_mass=0.95, n_support=2, primary_support=True), policy)
    assert (d.label, d.rule_id) == (Label.STRONGLY_SUPPORTED, "R4")


def test_r4_strong_with_three_independent_no_primary(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(make_features(support_mass=0.9, n_support=3), policy)
    assert (d.label, d.rule_id) == (Label.STRONGLY_SUPPORTED, "R4")


def test_two_independent_without_primary_is_only_supported(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(make_features(support_mass=0.8, n_support=2), policy)
    assert (d.label, d.rule_id) == (Label.SUPPORTED, "R5")


def test_circular_sourcing_blocks_strong(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(
        make_features(support_mass=0.95, n_support=4, primary_support=True, circular=True), policy
    )
    assert d.label is Label.SUPPORTED


def test_adversarial_found_refutation_blocks_strong_and_supported(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(
        make_features(
            support_mass=0.95,
            n_support=4,
            primary_support=True,
            adversarial=AdversarialOutcome.FOUND_REFUTATION,
        ),
        policy,
    )
    assert d.label is Label.INSUFFICIENT_EVIDENCE and d.rule_id == "R8"


def test_high_impact_requires_adversarial_run_for_strong(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    not_run = make_features(
        support_mass=0.95,
        n_support=3,
        primary_support=True,
        impact=Impact.HIGH,
        adversarial=AdversarialOutcome.NOT_RUN,
    )
    assert decide(not_run, policy).label is Label.SUPPORTED
    ran = make_features(
        support_mass=0.95,
        n_support=3,
        primary_support=True,
        impact=Impact.HIGH,
        adversarial=AdversarialOutcome.NONE_FOUND,
    )
    assert decide(ran, policy).label is Label.STRONGLY_SUPPORTED


def test_found_caveat_does_not_block(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(
        make_features(
            support_mass=0.95,
            n_support=3,
            primary_support=True,
            adversarial=AdversarialOutcome.FOUND_CAVEAT,
        ),
        policy,
    )
    assert d.label is Label.STRONGLY_SUPPORTED


def test_r5_single_primary_group_is_supported(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(make_features(support_mass=0.7, n_support=1, primary_support=True), policy)
    assert (d.label, d.rule_id) == (Label.SUPPORTED, "R5")


def test_r5_blocked_by_meaningful_refutation(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    d = decide(make_features(support_mass=0.8, n_support=2, refute_mass=0.3, n_refute=1), policy)
    assert d.label is not Label.SUPPORTED


def test_r6_mixed(policy: VerificationPolicy, make_features: MakeFeatures) -> None:
    d = decide(make_features(support_mass=0.5, n_support=1, refute_mass=0.5, n_refute=1), policy)
    assert (d.label, d.rule_id) == (Label.MIXED_EVIDENCE, "R6")


def test_r7_partially_supported(policy: VerificationPolicy, make_features: MakeFeatures) -> None:
    d = decide(make_features(support_mass=0.5, n_support=1, scope_mismatch=True), policy)
    assert (d.label, d.rule_id) == (Label.PARTIALLY_SUPPORTED, "R7")


def test_r8_insufficient(policy: VerificationPolicy, make_features: MakeFeatures) -> None:
    d = decide(make_features(support_mass=0.1, n_support=0), policy)
    assert (d.label, d.rule_id) == (Label.INSUFFICIENT_EVIDENCE, "R8")


def test_no_evidence_with_good_coverage_is_insufficient_not_unverified(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    """'We looked and found nothing' differs from 'we could not look'."""
    assert decide(make_features(coverage=0.9), policy).label is Label.INSUFFICIENT_EVIDENCE
    assert decide(make_features(coverage=0.2), policy).label is Label.UNVERIFIED


@pytest.mark.parametrize("coverage", [0.6, 0.61])
def test_coverage_boundary_is_inclusive(
    policy: VerificationPolicy, make_features: MakeFeatures, coverage: float
) -> None:
    assert decide(make_features(coverage=coverage), policy).rule_id == "R8"


def test_decision_is_deterministic(policy: VerificationPolicy, make_features: MakeFeatures) -> None:
    features = make_features(support_mass=0.8, n_support=2, refute_mass=0.1)
    assert decide(features, policy) == decide(features, policy)


def test_decision_reason_is_informative(
    policy: VerificationPolicy, make_features: MakeFeatures
) -> None:
    assert "coverage" in decide(make_features(coverage=0.1), policy).reason
