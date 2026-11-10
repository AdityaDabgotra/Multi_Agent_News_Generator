"""Compound-claim aggregation: combine the labels of atomic claims into one label.

A compound claim is the conjunction of its atoms, but partial truth must stay representable,
so the result is not a simple AND.
"""

from __future__ import annotations

from collections.abc import Sequence

from meridian.core.errors import DecisionError
from meridian.schemas.common import Label

_SUPPORTED_LEVELS = (Label.STRONGLY_SUPPORTED, Label.SUPPORTED)
_UNKNOWN_LEVELS = (Label.UNVERIFIED, Label.INSUFFICIENT_EVIDENCE)


def aggregate_compound(atom_labels: Sequence[Label]) -> Label:
    """Aggregate atom labels (documented order of precedence).

    1. Any outdated/misleading atom -> outdated_or_misleading_context.
    2. Any mixed atom -> mixed_evidence.
    3. Any contradicted atom: if anything else is supported/partial -> partially_supported,
       otherwise contradicted (a conjunction with a false atom is false).
    4. All atoms supported -> the weakest supported level.
    5. Some atoms supported/partial and the rest unknown -> partially_supported.
    6. Only unknown atoms -> unverified if any is unverified, else insufficient_evidence.
    """
    if not atom_labels:
        raise DecisionError("cannot aggregate zero atoms")
    labels = set(atom_labels)

    if Label.OUTDATED_OR_MISLEADING_CONTEXT in labels:
        return Label.OUTDATED_OR_MISLEADING_CONTEXT
    if Label.MIXED_EVIDENCE in labels:
        return Label.MIXED_EVIDENCE

    has_support = any(label in labels for label in _SUPPORTED_LEVELS)
    has_partial = Label.PARTIALLY_SUPPORTED in labels
    if Label.CONTRADICTED in labels:
        return Label.PARTIALLY_SUPPORTED if (has_support or has_partial) else Label.CONTRADICTED

    if labels <= set(_SUPPORTED_LEVELS):
        return Label.SUPPORTED if Label.SUPPORTED in labels else Label.STRONGLY_SUPPORTED

    if has_support or has_partial:
        return Label.PARTIALLY_SUPPORTED

    return Label.UNVERIFIED if Label.UNVERIFIED in labels else Label.INSUFFICIENT_EVIDENCE
