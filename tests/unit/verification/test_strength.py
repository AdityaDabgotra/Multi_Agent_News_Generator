from collections.abc import Callable

import pytest

from meridian.core import uuid7
from meridian.schemas import Directness, Stance
from meridian.verification import (
    VerificationPolicy,
    WeightedEvidence,
    combine_mass,
    compute_strength,
    group_weights,
    item_weight,
)

MakeItem = Callable[..., WeightedEvidence]


def test_item_weight_is_product_of_factors(policy: VerificationPolicy, make_item: MakeItem) -> None:
    item = make_item(
        directness=Directness.DIRECT_SECONDARY, reliability=0.8, temporal=0.5, quality=0.5
    )
    assert item_weight(item, policy) == pytest.approx(0.8 * 0.7 * 0.5 * 0.5)


def test_weighted_evidence_validates_ranges() -> None:
    with pytest.raises(ValueError):
        WeightedEvidence(
            evidence_id=uuid7(),
            origin_group_id=uuid7(),
            stance=Stance.SUPPORTS,
            directness=Directness.PRIMARY,
            reliability=1.2,
        )


def test_combine_mass_basics() -> None:
    assert combine_mass([]) == 0.0
    assert combine_mass([0.5]) == pytest.approx(0.5)
    assert combine_mass([0.5, 0.5]) == pytest.approx(0.75)
    assert combine_mass([1.0, 0.3]) == 1.0


def test_ten_copies_of_one_origin_count_as_one_group(
    policy: VerificationPolicy, make_item: MakeItem
) -> None:
    """The core independence rule: ten outlets repeating one wire story are ONE origin."""
    origin = uuid7()
    copies = [make_item(group=origin) for _ in range(10)]
    single = compute_strength(copies[:1], coverage=0.9, policy=policy)
    many = compute_strength(copies, coverage=0.9, policy=policy)
    assert many.n_support_groups == 1
    assert many.support_mass == pytest.approx(single.support_mass)


def test_independent_groups_increase_mass_and_count(
    policy: VerificationPolicy, make_item: MakeItem
) -> None:
    one = compute_strength([make_item()], 0.9, policy)
    three = compute_strength([make_item(), make_item(), make_item()], 0.9, policy)
    assert three.n_support_groups == 3
    assert three.support_mass > one.support_mass


def test_context_and_irrelevant_are_ignored(
    policy: VerificationPolicy, make_item: MakeItem
) -> None:
    items = [make_item(stance=Stance.CONTEXT), make_item(stance=Stance.IRRELEVANT)]
    strength = compute_strength(items, 0.9, policy)
    assert strength.support_mass == 0.0 and strength.refute_mass == 0.0
    assert group_weights(items, policy) == []


def test_low_reliability_group_is_not_credible(
    policy: VerificationPolicy, make_item: MakeItem
) -> None:
    weak = make_item(reliability=0.3, directness=Directness.INDIRECT)  # 0.3 * 0.4 = 0.12
    strength = compute_strength([weak], 0.9, policy)
    assert strength.support_mass == pytest.approx(0.12)
    assert strength.n_support_groups == 0


def test_primary_flag_requires_credible_primary_item(
    policy: VerificationPolicy, make_item: MakeItem
) -> None:
    primary = make_item(directness=Directness.PRIMARY, reliability=0.9)
    secondary = make_item(directness=Directness.DIRECT_SECONDARY, reliability=0.9)
    assert compute_strength([primary], 0.9, policy).has_primary_support is True
    assert compute_strength([secondary], 0.9, policy).has_primary_support is False
    weak_primary = make_item(directness=Directness.PRIMARY, reliability=0.2)
    assert compute_strength([weak_primary], 0.9, policy).has_primary_support is False


def test_refuting_items_build_refute_mass(policy: VerificationPolicy, make_item: MakeItem) -> None:
    items = [make_item(stance=Stance.REFUTES), make_item(stance=Stance.REFUTES)]
    strength = compute_strength(items, 0.9, policy)
    assert strength.n_refute_groups == 2
    assert strength.refute_mass > 0.7
    assert strength.support_mass == 0.0


def test_group_takes_max_weight_not_sum(policy: VerificationPolicy, make_item: MakeItem) -> None:
    origin = uuid7()
    strong = make_item(group=origin, reliability=0.9)
    weak = make_item(group=origin, reliability=0.4)
    weights = group_weights([strong, weak], policy)
    assert len(weights) == 1
    assert weights[0].weight == pytest.approx(item_weight(strong, policy))


def test_coverage_range_checked(policy: VerificationPolicy) -> None:
    with pytest.raises(ValueError):
        compute_strength([], 1.5, policy)
