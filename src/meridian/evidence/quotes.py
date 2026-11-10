"""Verbatim quote verification (blueprint 5.3 invariant 1).

Evidence is only accepted when its excerpt occurs *verbatim* in the stored snapshot text at the
recorded offsets. Snapshots are stored NFC-normalized by the extractor (S03), so offsets are
stable; the excerpt is NFC-normalized before comparison. No fuzzy matching is performed.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass


def normalize_text(text: str) -> str:
    """Unicode NFC normalization (the only normalization applied to snapshots and quotes)."""
    return unicodedata.normalize("NFC", text)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class QuoteCheck:
    ok: bool
    reason: str


def verify_quote(snapshot_text: str, excerpt: str, start: int, end: int) -> QuoteCheck:
    """Check that ``snapshot_text[start:end]`` equals ``excerpt`` exactly (after NFC)."""
    if not excerpt.strip():
        return QuoteCheck(False, "empty excerpt")
    if start < 0 or end <= start or end > len(snapshot_text):
        return QuoteCheck(False, "offsets out of range")
    if normalize_text(snapshot_text[start:end]) != normalize_text(excerpt):
        return QuoteCheck(False, "excerpt does not match snapshot at the given offsets")
    return QuoteCheck(True, "verbatim match")


def locate_quote(snapshot_text: str, excerpt: str) -> tuple[int, int] | None:
    """Find an excerpt in a snapshot. Exact match first; then whitespace-flexible match.

    Whitespace-flexible means runs of whitespace in the excerpt may match any run of whitespace
    in the snapshot (line wraps). Returned offsets always refer to the original snapshot text.
    """
    needle = excerpt.strip()
    if not needle:
        return None
    index = snapshot_text.find(needle)
    if index >= 0:
        return index, index + len(needle)
    tokens = needle.split()
    pattern = r"\s+".join(re.escape(token) for token in tokens)
    match = re.search(pattern, snapshot_text)
    if match is None:
        return None
    return match.start(), match.end()
