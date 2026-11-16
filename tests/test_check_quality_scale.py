# SPDX-License-Identifier: Apache-2.0
"""Tests of the release tier ratchet in scripts/check_quality_scale.py."""

import importlib.util
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "check_quality_scale.py"
spec = importlib.util.spec_from_file_location("check_quality_scale", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def write(tmp_path, body: str) -> pathlib.Path:
    """Write a pyproject.toml fixture."""
    path = tmp_path / "pyproject.toml"
    path.write_text(body, encoding="utf-8")
    return path


def policy(declared: str, released: dict[str, str] | None = None) -> str:
    """Build the [tool.arpav_meteo_idro] section."""
    text = f'[tool.arpav_meteo_idro]\nrelease_tier = "{declared}"\n'
    if released:
        text += "[tool.arpav_meteo_idro.released]\n"
        text += "".join(f'"{version}" = "{tier}"\n' for version, tier in released.items())
    return text


def test_repository_policy_is_valid():
    """The committed pyproject.toml passes its own ratchet."""
    declared, errors = checker.check_ratchet(checker.PYPROJECT)
    assert errors == []
    assert declared in checker.TIERS


@pytest.mark.parametrize(
    ("declared", "released"),
    [
        ("silver", {"0.15.5": "bronze"}),
        ("silver", {"0.16.0": "silver"}),
        ("gold", {"0.16.0": "silver"}),
        ("bronze", None),
    ],
)
def test_ratchet_accepts_same_or_higher_tier(tmp_path, declared, released):
    """A tier equal to or above the latest release passes."""
    result, errors = checker.check_ratchet(write(tmp_path, policy(declared, released)))
    assert errors == []
    assert result == declared


def test_ratchet_rejects_lowered_tier(tmp_path):
    """Negative proof: lowering the tier below the released one fails."""
    declared, errors = checker.check_ratchet(write(tmp_path, policy("bronze", {"0.16.0": "silver"})))
    assert declared == "bronze"
    assert len(errors) == 1
    assert "lower than" in errors[0]


def test_ratchet_compares_with_highest_released_tier(tmp_path):
    """Only the highest released tier matters, whatever the order of the entries."""
    body = policy("silver", {"0.17.0": "gold", "0.16.0": "silver"})
    _, errors = checker.check_ratchet(write(tmp_path, body))
    assert errors


@pytest.mark.parametrize(
    "body",
    [
        "[tool.other]\nx = 1\n",
        '[tool.arpav_meteo_idro]\nrelease_tier = "diamond"\n',
        "[tool.arpav_meteo_idro]\nrelease_tier = 2\n",
        policy("silver", {"0.16.0": "diamond"}),
    ],
)
def test_ratchet_rejects_invalid_declarations(tmp_path, body):
    """A missing, unknown or mistyped tier is an error."""
    _, errors = checker.check_ratchet(write(tmp_path, body))
    assert errors


def test_ratchet_rejects_unreadable_file(tmp_path):
    """A missing or malformed pyproject.toml is an error, not a crash."""
    _, errors = checker.check_ratchet(tmp_path / "missing.toml")
    assert errors
    _, errors = checker.check_ratchet(write(tmp_path, "not = [valid"))
    assert errors


def test_ratchet_command_prints_the_tier(tmp_path, capsys, monkeypatch):
    """--ratchet prints only the tier on success (read by the release workflow)."""
    monkeypatch.setattr(checker, "PYPROJECT", write(tmp_path, policy("silver", {"0.15.5": "bronze"})))
    monkeypatch.setattr("sys.argv", ["check_quality_scale.py", "--ratchet"])
    assert checker.main() == 0
    assert capsys.readouterr().out.strip() == "silver"


def test_ratchet_command_fails_on_lowered_tier(tmp_path, capsys, monkeypatch):
    """--ratchet exits non-zero and prints nothing on stdout when the tier is lowered."""
    monkeypatch.setattr(checker, "PYPROJECT", write(tmp_path, policy("bronze", {"0.16.0": "silver"})))
    monkeypatch.setattr("sys.argv", ["check_quality_scale.py", "--ratchet"])
    assert checker.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "lower than" in captured.err
