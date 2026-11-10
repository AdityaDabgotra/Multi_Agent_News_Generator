from pathlib import Path

import pytest

from meridian.core.errors import PolicyError
from meridian.verification import default_policy, load_policy
from meridian.verification.policy import VerificationPolicy


def test_yaml_policy_matches_in_code_defaults(repo_root: Path) -> None:
    """config/verification_policy.yaml and default_policy() must never drift apart."""
    loaded = load_policy(repo_root / "config" / "verification_policy.yaml")
    assert loaded == default_policy()


def test_missing_file_raises_policy_error(tmp_path: Path) -> None:
    with pytest.raises(PolicyError):
        load_policy(tmp_path / "nope.yaml")


def test_invalid_yaml_raises_policy_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [unclosed", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_non_mapping_raises_policy_error(tmp_path: Path) -> None:
    bad = tmp_path / "list.yaml"
    bad.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_unknown_key_raises_policy_error(tmp_path: Path) -> None:
    bad = tmp_path / "unknown.yaml"
    bad.write_text("min_coverage: 0.5\nmystery: 1\n", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_out_of_range_value_raises_policy_error(tmp_path: Path) -> None:
    bad = tmp_path / "range.yaml"
    bad.write_text("min_coverage: 1.5\n", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_inconsistent_thresholds_rejected() -> None:
    with pytest.raises(ValueError):
        VerificationPolicy.model_validate(
            {
                "strongly_supported": {"max_refute_mass": 0.5},
                "supported": {"max_refute_mass": 0.2},
            }
        )


def test_policy_is_immutable() -> None:
    policy = default_policy()
    with pytest.raises(ValueError):
        policy.min_coverage = 0.1  # type: ignore[misc]
