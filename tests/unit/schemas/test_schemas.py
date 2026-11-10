from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from meridian.core import uuid7
from meridian.schemas import (
    AgentFailure,
    AgentResult,
    AgentTask,
    ArticleSentence,
    BudgetSlice,
    Claim,
    ClaimType,
    ConfidenceMeta,
    Directness,
    Evidence,
    FailureCode,
    GeneratedArticle,
    Impact,
    Label,
    SourceType,
    Stance,
    Trust,
    UntrustedText,
    VerificationResult,
    VerificationStatus,
)
from meridian.schemas.verification import EvidenceStrength

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def make_claim(**overrides: object) -> Claim:
    data: dict[str, object] = {
        "claim_id": uuid7(),
        "article_id": uuid7(),
        "text": "The central bank raised its rate by 25 basis points on 5 November 2026.",
        "original_span": (10, 90),
        "claim_type": ClaimType.EVENT,
        "check_worthiness": 0.9,
        "verifiable": True,
        "impact": Impact.MEDIUM,
    }
    data.update(overrides)
    return Claim.model_validate(data)


def make_evidence(**overrides: object) -> Evidence:
    data: dict[str, object] = {
        "evidence_id": uuid7(),
        "claim_ids": [uuid7()],
        "source_id": uuid7(),
        "url": "https://example.org/press/1",
        "publisher": "Example Central Bank",
        "retrieved_at": NOW,
        "snapshot_ref": "snapshots/ab/abcdef",
        "snapshot_sha256": "a" * 64,
        "excerpt": "The Committee decided to raise the target rate by 25 basis points.",
        "excerpt_char_start": 10,
        "excerpt_char_end": 77,
        "evidence_type": SourceType.PRIMARY_OFFICIAL,
        "directness": Directness.PRIMARY,
        "stance": Stance.SUPPORTS,
        "stance_confidence": ConfidenceMeta(kind="rule_derived", value=0.9),
        "extraction_method": "llm_quarantined",
        "verification_status": VerificationStatus.QUOTE_VERIFIED,
    }
    data.update(overrides)
    return Evidence.model_validate(data)


def test_claim_round_trip_json() -> None:
    claim = make_claim()
    again = Claim.model_validate_json(claim.model_dump_json())
    assert again == claim


def test_claim_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        make_claim(surprise="x")


@pytest.mark.parametrize("span", [(5, 5), (9, 3), (-1, 4)])
def test_claim_rejects_bad_span(span: tuple[int, int]) -> None:
    with pytest.raises(ValidationError):
        make_claim(original_span=span)


def test_non_verifiable_claim_needs_reason() -> None:
    with pytest.raises(ValidationError):
        make_claim(verifiable=False)
    claim = make_claim(verifiable=False, non_verifiable_reason="opinion")
    assert claim.verifiable is False


def test_claim_rejects_naive_reference_period() -> None:
    with pytest.raises(ValidationError):
        make_claim(reference_period=(datetime(2026, 1, 1), None))


def test_claim_rejects_reversed_reference_period() -> None:
    with pytest.raises(ValidationError):
        make_claim(reference_period=(NOW, NOW - timedelta(days=1)))


def test_evidence_round_trip_and_invariants() -> None:
    evidence = make_evidence()
    assert Evidence.model_validate_json(evidence.model_dump_json()) == evidence
    with pytest.raises(ValidationError):
        make_evidence(excerpt_char_start=50, excerpt_char_end=50)
    with pytest.raises(ValidationError):
        make_evidence(excerpt="x" * 601)
    with pytest.raises(ValidationError):
        make_evidence(snapshot_sha256="not-a-hash")
    with pytest.raises(ValidationError):
        make_evidence(claim_ids=[])


def test_confidence_calibrated_requires_value() -> None:
    with pytest.raises(ValidationError):
        ConfidenceMeta(kind="calibrated")
    assert ConfidenceMeta(kind="self_reported").value is None


def test_untrusted_text_cannot_be_marked_trusted() -> None:
    assert UntrustedText(text="hello").trust is Trust.UNTRUSTED
    with pytest.raises(ValidationError):
        UntrustedText(text="hello", trust=Trust.TRUSTED)


def make_budget() -> BudgetSlice:
    return BudgetSlice(
        max_llm_calls=4, max_tokens=20000, max_tool_calls=0, deadline=NOW, max_depth=1
    )


def test_agent_task_validates_agent_id_pattern() -> None:
    base = {
        "task_id": uuid7(),
        "investigation_id": uuid7(),
        "agent_id": "A03",
        "agent_version": "1.0.0",
        "prompt_version": "claim_extract@3",
        "objective": "Extract claims",
        "budget": make_budget(),
        "idempotency_key": "sha256:abc",
        "created_at": NOW,
    }
    assert AgentTask.model_validate(base).agent_id == "A03"
    with pytest.raises(ValidationError):
        AgentTask.model_validate({**base, "agent_id": "agent-3"})


def test_agent_result_failed_requires_error_and_vice_versa() -> None:
    failure = AgentFailure(
        code=FailureCode.SCHEMA_INVALID,
        retryable=True,
        message="bad output",
        occurred_at=NOW,
    )
    ok = AgentResult(task_id=uuid7(), agent_id="A03", status="ok")
    assert ok.error is None
    failed = AgentResult(task_id=uuid7(), agent_id="A03", status="failed", error=failure)
    assert failed.error is not None
    with pytest.raises(ValidationError):
        AgentResult(task_id=uuid7(), agent_id="A03", status="failed")
    with pytest.raises(ValidationError):
        AgentResult(task_id=uuid7(), agent_id="A03", status="ok", error=failure)


def make_strength() -> EvidenceStrength:
    return EvidenceStrength(
        support_mass=0.9,
        refute_mass=0.0,
        coverage=0.9,
        n_support_groups=3,
        n_refute_groups=0,
        has_primary_support=True,
        has_primary_refute=False,
    )


def test_verification_result_rule_id_and_calibration_consistency() -> None:
    base = {
        "verification_id": uuid7(),
        "claim_id": uuid7(),
        "label": Label.STRONGLY_SUPPORTED,
        "rule_id": "R4",
        "strength": make_strength(),
        "adversarial_outcome": "none_found",
        "justification": "Primary statement confirms.",
        "computed_at": NOW,
        "claim_version": 1,
        "pipeline_version": "0.1.0",
    }
    assert VerificationResult.model_validate(base).calibrated_probability is None
    with pytest.raises(ValidationError):
        VerificationResult.model_validate({**base, "rule_id": "R9"})
    with pytest.raises(ValidationError):
        VerificationResult.model_validate({**base, "calibrated_probability": 0.8})
    ok = VerificationResult.model_validate(
        {**base, "calibrated_probability": 0.8, "calibration_version": "cal-1"}
    )
    assert ok.calibrated_probability == 0.8


def test_label_enum_has_no_binary_true_false() -> None:
    values = {label.value for label in Label}
    assert "true" not in values and "false" not in values
    assert len(values) == 8


def test_article_sentence_rules() -> None:
    with pytest.raises(ValidationError):
        ArticleSentence(index=0, text="A fact.", kind="claim")
    ArticleSentence(index=0, text="However,", kind="connective")


def test_generated_article_sentence_indexes_must_be_sequential() -> None:
    sentences = [
        ArticleSentence(index=0, text="One.", kind="connective"),
        ArticleSentence(index=2, text="Three.", kind="connective"),
    ]
    with pytest.raises(ValidationError):
        GeneratedArticle(
            article_id=uuid7(),
            version=1,
            genre="news",
            headline="Headline",
            sentences=sentences,
            status="draft",
            created_at=NOW,
        )
