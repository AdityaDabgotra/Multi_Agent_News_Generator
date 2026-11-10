"""Project-wide exception types."""

from __future__ import annotations


class MeridianError(Exception):
    """Base class for all Meridian errors."""


class PolicyError(MeridianError):
    """Raised when a policy file is missing, malformed or inconsistent."""


class DecisionError(MeridianError):
    """Raised when verdict logic receives input it cannot decide on."""
