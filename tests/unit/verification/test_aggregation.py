import pytest

from meridian.core.errors import DecisionError
from meridian.schemas import Label
from meridian.verification import aggregate_compound

SS, S, P = Label.STRONGLY_SUPPORTED, Label.SUPPORTED, Label.PARTIALLY_SUPPORTED
C, M, U = Label.CONTRADICTED, Label.MIXED_EVIDENCE, Label.UNVERIFIED
INS, OUT = Label.INSUFFICIENT_EVIDENCE, Label.OUTDATED_OR_MISLEADING_CONTEXT


@pytest.mark.parametrize(
    ("atoms", "expected"),
    [
        ([SS], SS),
        ([SS, SS], SS),
        ([SS, S], S),  # weakest supported level wins
        ([S, S, SS], S),
        ([C, S], P),  # contradicted + supported -> partial
        ([C, SS, U], P),
        ([C, C], C),
        ([C, U], C),  # conjunction with a false atom and nothing supported
        ([S, U], P),  # unknown atoms leave the compound partial
        ([SS, INS], P),
        ([P, U], P),
        ([P, P], P),
        ([U, U], U),
        ([INS, INS], INS),
        ([U, INS], U),
        ([M, S], M),
        ([M, C], M),
        ([OUT, S], OUT),
        ([OUT, M, C], OUT),
    ],
)
def test_compound_aggregation_table(atoms: list[Label], expected: Label) -> None:
    assert aggregate_compound(atoms) is expected


def test_empty_input_rejected() -> None:
    with pytest.raises(DecisionError):
        aggregate_compound([])


def test_order_of_atoms_does_not_matter() -> None:
    assert aggregate_compound([C, S, U]) is aggregate_compound([U, S, C])
