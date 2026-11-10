"""Evidence utilities (quote verification now; snapshots and lineage in later steps)."""

from meridian.evidence.quotes import (
    QuoteCheck,
    locate_quote,
    normalize_text,
    sha256_text,
    verify_quote,
)

__all__ = ["QuoteCheck", "locate_quote", "normalize_text", "sha256_text", "verify_quote"]
