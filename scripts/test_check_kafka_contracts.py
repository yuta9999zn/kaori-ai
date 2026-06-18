"""
Tests for ``scripts/check-kafka-contracts.py`` — Issue #4 CI guard.

Each test stands up a tiny temporary git repo, commits an "old" schema
on a base branch, switches to a feature branch with a "new" schema,
then invokes the script as a subprocess (so the real argv + exit-code
contract is exercised, not a mocked variant).

Why subprocess + tmp_path: the script's logic intentionally depends on
``git show base:path`` and ``git rev-parse``; mocking those would
re-implement git in Python and tell us nothing about whether the real
script works. The cost is a few hundred ms per test — acceptable for
the safety net.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "check-kafka-contracts.py"
SCHEMA_DIR_REL = Path("infrastructure") / "kafka" / "schemas"


# ─── git helpers ─────────────────────────────────────────────────

def _git(repo: Path, *args: str) -> str:
    """Run a git command inside ``repo``, return stdout. Raises on
    non-zero exit so test setup failures are loud."""
    proc = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {proc.stderr.strip()}"
        )
    return proc.stdout


def _setup_repo(tmp_path: Path, base_schema: dict) -> Path:
    """Initialise a git repo with one schema committed on the default
    branch. Returns the repo path. Caller can then switch branches and
    mutate the schema for the diff test."""
    repo = tmp_path / "repo"
    repo.mkdir()

    _git(repo, "init", "--quiet", "--initial-branch=main")
    _git(repo, "config", "user.email", "test@kaori.io")
    _git(repo, "config", "user.name",  "Kaori Test")

    schemas_dir = repo / SCHEMA_DIR_REL
    schemas_dir.mkdir(parents=True)
    schema_path = schemas_dir / "kaori.test.event.json"
    schema_path.write_text(json.dumps(base_schema, indent=2), encoding="utf-8")

    _git(repo, "add", str(SCHEMA_DIR_REL / "kaori.test.event.json"))
    _git(repo, "commit", "--quiet", "-m", "initial schema")

    # Branch off so we can mutate without disturbing the base ref.
    _git(repo, "checkout", "--quiet", "-b", "feature")
    return repo


def _run_script(repo: Path, base: str = "main") -> tuple[int, str]:
    """Invoke check-kafka-contracts.py inside ``repo`` against ``base``.
    Returns (exit_code, combined_stdout_stderr)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", base],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _commit_change(repo: Path, schema: dict, msg: str = "mutate schema") -> None:
    schema_path = repo / SCHEMA_DIR_REL / "kaori.test.event.json"
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    _git(repo, "add", str(SCHEMA_DIR_REL / "kaori.test.event.json"))
    _git(repo, "commit", "--quiet", "-m", msg)


# ─── Skip the suite when git is unavailable ──────────────────────

if shutil.which("git") is None:                        # pragma: no cover
    pytest.skip("git not available", allow_module_level=True)


# ─── ALLOWED — additive changes ──────────────────────────────────

def test_add_optional_field_passes(tmp_path):
    base = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": True,
        "required": ["run_id"],
        "properties": {"run_id": {"type": "string"}},
    }
    repo = _setup_repo(tmp_path, base)

    new = json.loads(json.dumps(base))
    new["properties"]["new_optional"] = {"type": "string"}
    _commit_change(repo, new, "add optional field")

    rc, out = _run_script(repo)
    assert rc == 0, out
    assert "PASS" in out


def test_brand_new_schema_with_required_fields_passes(tmp_path):
    """A schema file added in this PR can have any required fields —
    there's no "old version" for consumers to break against."""
    # Setup: one existing schema on main.
    base_existing = {"type": "object", "additionalProperties": True, "properties": {}}
    repo = _setup_repo(tmp_path, base_existing)

    # On the feature branch, add a NEW schema file with required fields.
    new_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": True,
        "required": ["run_id", "enterprise_id", "must_have"],
        "properties": {
            "run_id":        {"type": "string"},
            "enterprise_id": {"type": "string"},
            "must_have":     {"type": "string"},
        },
    }
    new_path = repo / SCHEMA_DIR_REL / "kaori.brand.new.event.json"
    new_path.write_text(json.dumps(new_schema, indent=2), encoding="utf-8")
    _git(repo, "add", str(SCHEMA_DIR_REL / "kaori.brand.new.event.json"))
    _git(repo, "commit", "--quiet", "-m", "add brand-new topic")

    rc, out = _run_script(repo)
    assert rc == 0, out
    assert "kaori.brand.new.event.json (new schema)" in out


def test_no_changes_passes(tmp_path):
    """When the feature branch hasn't touched any schema, the script is
    a no-op success."""
    base = {
        "type": "object", "additionalProperties": True,
        "required": ["run_id"], "properties": {"run_id": {"type": "string"}},
    }
    repo = _setup_repo(tmp_path, base)
    rc, out = _run_script(repo)
    assert rc == 0, out


# ─── BLOCKED — breaking changes ──────────────────────────────────

def test_remove_field_blocked(tmp_path):
    base = {
        "type": "object", "additionalProperties": True,
        "required": ["run_id"],
        "properties": {
            "run_id":   {"type": "string"},
            "filename": {"type": "string"},
        },
    }
    repo = _setup_repo(tmp_path, base)

    new = json.loads(json.dumps(base))
    del new["properties"]["filename"]
    _commit_change(repo, new, "remove filename")

    rc, out = _run_script(repo)
    assert rc == 1, out
    assert "BREAKING" in out
    assert "filename" in out
    assert "removed" in out.lower() or "rename" in out.lower()


def test_rename_field_blocked(tmp_path):
    """A rename shows up as remove(old) + add(new). The remove half
    catches it."""
    base = {
        "type": "object", "additionalProperties": True,
        "required": ["run_id"],
        "properties": {
            "run_id":   {"type": "string"},
            "filename": {"type": "string"},
        },
    }
    repo = _setup_repo(tmp_path, base)

    new = {
        "type": "object", "additionalProperties": True,
        "required": ["run_id"],
        "properties": {
            "run_id":           {"type": "string"},
            "uploaded_filename": {"type": "string"},  # renamed
        },
    }
    _commit_change(repo, new, "rename filename to uploaded_filename")

    rc, out = _run_script(repo)
    assert rc == 1, out
    assert "filename" in out


def test_optional_to_required_blocked(tmp_path):
    """Promoting an optional field to required would crash producers
    that haven't deployed yet. Stage in two PRs instead."""
    base = {
        "type": "object", "additionalProperties": True,
        "required": ["run_id"],
        "properties": {
            "run_id":   {"type": "string"},
            "filename": {"type": "string"},  # currently optional
        },
    }
    repo = _setup_repo(tmp_path, base)

    new = json.loads(json.dumps(base))
    new["required"] = ["run_id", "filename"]
    _commit_change(repo, new, "promote filename to required")

    rc, out = _run_script(repo)
    assert rc == 1, out
    assert "filename" in out
    assert "required" in out.lower()


def test_new_required_field_on_existing_schema_blocked(tmp_path):
    """Adding a brand-new required field is fine on a brand-new
    schema, but breaks an existing one — consumers deployed before
    the producer would crash."""
    base = {
        "type": "object", "additionalProperties": True,
        "required": ["run_id"], "properties": {"run_id": {"type": "string"}},
    }
    repo = _setup_repo(tmp_path, base)

    new = {
        "type": "object", "additionalProperties": True,
        "required": ["run_id", "must_have_new"],
        "properties": {
            "run_id":        {"type": "string"},
            "must_have_new": {"type": "string"},
        },
    }
    _commit_change(repo, new, "add required must_have_new")

    rc, out = _run_script(repo)
    assert rc == 1, out
    assert "must_have_new" in out


def test_type_change_blocked(tmp_path):
    base = {
        "type": "object", "additionalProperties": True,
        "required": ["run_id", "size"],
        "properties": {
            "run_id": {"type": "string"},
            "size":   {"type": "integer"},
        },
    }
    repo = _setup_repo(tmp_path, base)

    new = json.loads(json.dumps(base))
    new["properties"]["size"]["type"] = "string"  # narrow type changed
    _commit_change(repo, new, "narrow size type to string")

    rc, out = _run_script(repo)
    assert rc == 1, out
    assert "size" in out
    assert "type" in out.lower()


def test_additional_properties_tightened_blocked(tmp_path):
    """A producer that's been silently appending extra fields would
    suddenly crash when the validator rejects them."""
    base = {
        "type": "object", "additionalProperties": True,
        "required": ["run_id"], "properties": {"run_id": {"type": "string"}},
    }
    repo = _setup_repo(tmp_path, base)

    new = json.loads(json.dumps(base))
    new["additionalProperties"] = False
    _commit_change(repo, new, "lock additionalProperties")

    rc, out = _run_script(repo)
    assert rc == 1, out
    assert "additionalProperties" in out


# ─── Edge cases ──────────────────────────────────────────────────

def test_invalid_json_blocks(tmp_path):
    """Garbled JSON in the committed file is itself a break — better
    to fail CI loudly than silently let an unparseable schema through."""
    base = {
        "type": "object", "additionalProperties": True,
        "required": ["run_id"], "properties": {"run_id": {"type": "string"}},
    }
    repo = _setup_repo(tmp_path, base)

    # Write malformed JSON without going through json.dumps.
    schema_path = repo / SCHEMA_DIR_REL / "kaori.test.event.json"
    schema_path.write_text("{ this is not json", encoding="utf-8")
    _git(repo, "add", str(SCHEMA_DIR_REL / "kaori.test.event.json"))
    _git(repo, "commit", "--quiet", "-m", "break the schema")

    rc, out = _run_script(repo)
    assert rc == 1, out
    assert "not valid JSON" in out
