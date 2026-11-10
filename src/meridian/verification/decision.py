"""The verdict decision table (blueprint 5.6). A PURE function: no I/O, no LLM, no randomness.

Rules are evaluated in order and the first match fires:
  R1 unverified | R2 outdated_or_misleading_context | R3 contradicted | R4 strongly_supported
  R5 supported  | R6 mixed_evidence | R7 partially_supported | R8 insufficient_evidence
The LLM never selects the label; it only writes the justification afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass

from meridian.schemas.common import AdversarialOutcome, Impact, Label
from meridian.schemas.verification import VerificationFeatures
from meridian.verification.policy import VerificationPolicy


@dataclass(frozen=True, slots=True)
class Decision:
    label: Label
    rule_id: str
    reason: str


def decide(features: VerificationFeatures, policy: VerificationPolicy) -> Decision:
    s = features.strength

    # R1: we could not look hard enough (or the claim is not standalone yet).
    if features.needs_context:
        return Decision(Label.UNVERIFIED, "R1", "claim needs context before it can be verified")
    if s.coverage < policy.min_coverage:
        return Decision(
            Label.UNVERIFIED,
            "R1",
            f"coverage {s.coverage:.2f} is below minimum {policy.min_coverage:.2f}",
        )

    # R2: literally supported but presented out of time or context.
    misleading = features.temporal_flags & policy.misleading_temporal_flags
    if misleading and s.support_mass >= policy.outdated.min_support_mass:
        names = ", ".join(sorted(f.value for f in misleading))
        return Decision(
            Label.OUTDATED_OR_MISLEADING_CONTEXT, "R2", f"temporal/context flags present: {names}"
        )

    # R3: contradicted.
    c = policy.contradicted
    refute_strong = (
        s.refute_mass >= c.min_refute_mass and s.n_refute_groups >= c.min_refute_groups
    ) or (s.has_primary_refute)
    if refute_strong and s.support_mass < c.max_support_mass:
        return Decision(Label.CONTRADICTED, "R3", "credible refuting evidence and little support")

    # R4: strongly supported.
    ss = policy.strongly_supported
    enough_groups = (
        s.has_primary_support and s.n_support_groups >= ss.min_groups_with_primary
    ) or (s.n_support_groups >= ss.min_groups_without_primary)
    adversarial_ok = features.adversarial is not AdversarialOutcome.FOUND_REFUTATION and not (
        features.impact is Impact.HIGH and features.adversarial is AdversarialOutcome.NOT_RUN
    )
    if (
        enough_groups
        and s.refute_mass < ss.max_refute_mass
        and adversarial_ok
        and not features.circular_sourcing
        and not features.temporal_flags
    ):
        return Decision(
            Label.STRONGLY_SUPPORTED,
            "R4",
            "primary/independent corroboration, no credible refutation",
        )

    # R5: supported.
    sp = policy.supported
    supported_ok = (
        s.support_mass >= sp.min_support_mass and s.n_support_groups >= sp.min_groups
    ) or (s.has_primary_support)
    if (
        supported_ok
        and s.refute_mass < sp.max_refute_mass
        and features.adversarial is not AdversarialOutcome.FOUND_REFUTATION
    ):
        return Decision(
            Label.SUPPORTED, "R5", "credible supporting evidence, no credible refutation"
        )

    # R6: credible evidence on both sides.
    m = policy.mixed
    if (
        s.support_mass >= m.min_support_mass
        and s.refute_mass >= m.min_refute_mass
        and s.n_support_groups >= 1
        and s.n_refute_groups >= 1
    ):
        return Decision(Label.MIXED_EVIDENCE, "R6", "credible supporting and refuting evidence")

    # R7: the core is supported but specifics differ.
    if features.scope_mismatch and s.support_mass >= policy.partially_supported.min_support_mass:
        return Decision(
            Label.PARTIALLY_SUPPORTED, "R7", "core supported; numbers, scope or attribution differ"
        )

    # R8: we looked adequately and found too little.
    return Decision(
        Label.INSUFFICIENT_EVIDENCE, "R8", "adequate coverage but evidence below thresholds"
    )
