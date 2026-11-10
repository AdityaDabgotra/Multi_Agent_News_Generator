import unicodedata

import pytest

from meridian.evidence import locate_quote, normalize_text, sha256_text, verify_quote

TEXT = "Intro line.\nThe Committee decided to raise the target\nrate by 25 basis points.\nEnd."


def test_verify_exact_match() -> None:
    excerpt = "The Committee decided"
    start = TEXT.index(excerpt)
    result = verify_quote(TEXT, excerpt, start, start + len(excerpt))
    assert result.ok


def test_verify_rejects_paraphrase() -> None:
    result = verify_quote(TEXT, "The committee decided", 12, 33)  # lowercase c
    assert not result.ok


def test_verify_rejects_wrong_offsets_and_out_of_range() -> None:
    assert not verify_quote(TEXT, "The Committee decided", 0, 21).ok
    assert not verify_quote(TEXT, "x", -1, 3).ok
    assert not verify_quote(TEXT, "x", 5, 5).ok
    assert not verify_quote(TEXT, "x", 5, len(TEXT) + 10).ok


def test_verify_rejects_empty_excerpt() -> None:
    assert not verify_quote(TEXT, "   ", 0, 3).ok


def test_verify_nfc_normalization_only() -> None:
    composed = "caf\u00e9 reopened"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    assert verify_quote(composed, decomposed[:5], 0, 4).ok is True


def test_locate_exact() -> None:
    span = locate_quote(TEXT, "decided to raise")
    assert span is not None
    assert TEXT[span[0] : span[1]] == "decided to raise"


def test_locate_whitespace_flexible_returns_original_offsets() -> None:
    span = locate_quote(TEXT, "raise the target rate by 25 basis points")  # newline in snapshot
    assert span is not None
    assert TEXT[span[0] : span[1]] == "raise the target\nrate by 25 basis points"


def test_locate_missing_and_empty() -> None:
    assert locate_quote(TEXT, "central bank cut rates") is None
    assert locate_quote(TEXT, "   ") is None


def test_locate_does_not_match_different_words() -> None:
    assert locate_quote(TEXT, "raise the target rates by 25") is None


def test_sha256_is_stable_and_hex() -> None:
    digest = sha256_text("abc")
    assert digest == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert len(digest) == 64


def test_normalize_text_is_nfc() -> None:
    assert normalize_text(unicodedata.normalize("NFD", "é")) == "é"


@pytest.mark.parametrize("excerpt", ["Committee", "basis points"])
def test_locate_then_verify_roundtrip(excerpt: str) -> None:
    span = locate_quote(TEXT, excerpt)
    assert span is not None
    assert verify_quote(TEXT, excerpt, *span).ok
