"""
Tests for scripts/vault_import.py — pure plan-building + parsing.

No Vault needed: --apply / --verify paths are exercised in CI integration
later. These tests pin the manifest semantics so a careless edit (drop
an entry, reuse a path, leak a placeholder into a real write) fails CI.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_SCRIPT_PATH = Path(__file__).resolve().parent / "vault_import.py"
_REPO_ROOT = Path(__file__).resolve().parent.parent

# Ensure ai-orchestrator path is importable so vault_import's own
# `from shared.kaori_vault import ...` resolves under pytest.
sys.path.insert(0, str(_REPO_ROOT / "services" / "ai-orchestrator"))


def _load_module():
    """Load vault_import.py as a module despite its hyphen-free filename
    living under scripts/ (not a package). Runs once per test."""
    spec = importlib.util.spec_from_file_location("vault_import", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["vault_import"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def vi():
    return _load_module()


# ---------------------------------------------------------------------------
# Placeholder detection — must filter all .env.example shapes
# ---------------------------------------------------------------------------


def test_placeholder_detection_covers_env_example_shapes(vi):
    """Every placeholder shape used in .env.example must be filtered.

    A regression here is dangerous: a placeholder leaked into Vault
    looks like a real secret + production reads back garbage at boot.
    """
    is_ph = vi._is_placeholder
    assert is_ph("")  # blank
    assert is_ph("<SECRET>")
    assert is_ph("<BASE64_ENCODED_PRIVATE_KEY>")
    assert is_ph("<BASE64_32_BYTES>")
    assert is_ph("<YOUR_EMAIL>")
    assert is_ph("<PATH>")
    assert is_ph("<EMAIL_LIST>")
    assert is_ph("<GROUP_ID>")
    # Real-looking values pass through
    assert not is_ph("sk-ant-api03-aBc123")
    assert not is_ph("smtp.gmail.com")
    assert not is_ph("587")  # port number is fine


# ---------------------------------------------------------------------------
# .env parsing — minimal but must handle quotes + comments
# ---------------------------------------------------------------------------


def test_parse_dotenv_strips_quotes_and_skips_comments(vi, tmp_path):
    sample = tmp_path / ".env.test"
    sample.write_text(
        '\n'.join([
            "# comment ignored",
            "",
            "PLAIN=value1",
            'QUOTED="value 2 with spaces"',
            "SQUOTED='value3'",
            "MIXED=val=with=equals",  # only first '=' is the delimiter
            "  SPACED_KEY  =  spaced_value  ",
            "no_equals_line",  # must be ignored, not crash
        ]),
        encoding="utf-8",
    )
    parsed = vi.parse_dotenv(sample)
    assert parsed["PLAIN"] == "value1"
    assert parsed["QUOTED"] == "value 2 with spaces"
    assert parsed["SQUOTED"] == "value3"
    assert parsed["MIXED"] == "val=with=equals"
    assert parsed["SPACED_KEY"] == "spaced_value"
    assert "no_equals_line" not in parsed


def test_parse_dotenv_missing_file_raises(vi, tmp_path):
    with pytest.raises(FileNotFoundError):
        vi.parse_dotenv(tmp_path / "does-not-exist.env")


# ---------------------------------------------------------------------------
# Plan builder — manifest-driven, only-prefix filter, payload assembly
# ---------------------------------------------------------------------------


def test_build_plan_skips_placeholders_and_assembles_real_values(vi):
    env = {
        "ANTHROPIC_API_KEY": "sk-real-anthropic-key",
        "OPENAI_API_KEY": "<SECRET>",  # placeholder must drop
        "SMTP_HOST": "smtp.kaori.local",
        "SMTP_PORT": "587",
        "SMTP_USER": "",  # blank treated as placeholder
        "SMTP_PASSWORD": "real-pw",
    }
    plans = vi.build_plan(vi.MANIFEST, env)
    by_path = {p.path: p for p in plans}

    anth = by_path["platform/api_keys/anthropic"]
    assert anth.payload == {"api_key": "sk-real-anthropic-key"}
    assert anth.skipped_envs == ()

    openai = by_path["platform/api_keys/openai"]
    assert openai.payload == {}
    assert openai.skipped_envs == ("OPENAI_API_KEY",)
    assert openai.is_empty

    smtp = by_path["platform/smtp/credentials"]
    # host + port + password assembled, user dropped because blank
    assert smtp.payload == {"host": "smtp.kaori.local", "port": "587", "password": "real-pw"}
    assert smtp.skipped_envs == ("SMTP_USER",)


def test_build_plan_only_prefix_filters_to_subset(vi):
    env = {"ANTHROPIC_API_KEY": "x", "SMTP_HOST": "y", "JWT_PRIVATE_KEY": "z"}
    plans = vi.build_plan(vi.MANIFEST, env, only_prefix="platform/api_keys")
    assert all(p.path.startswith("platform/api_keys") for p in plans)
    # Three api_keys entries (anthropic + openai + google) exist in manifest
    assert {p.path for p in plans} >= {
        "platform/api_keys/anthropic",
        "platform/api_keys/openai",
        "platform/api_keys/google",
    }
    # Non-matching paths excluded
    assert not any(p.path.startswith("platform/smtp") for p in plans)


# ---------------------------------------------------------------------------
# Render — must NOT print secret values, only key + length
# ---------------------------------------------------------------------------


def test_render_plan_does_not_leak_secret_values(vi):
    """Stdout must be safe to copy-paste into a chat or PR comment.

    The render path prints `key=<N chars>` not the value itself; this
    test fails if anyone wires the value back in.
    """
    env = {"ANTHROPIC_API_KEY": "sk-this-must-not-appear-in-output"}
    plans = vi.build_plan(vi.MANIFEST, env, only_prefix="platform/api_keys/anthropic")
    out = vi.render_plan(plans)
    assert "sk-this-must-not-appear-in-output" not in out
    assert "api_key=<33 chars>" in out


# ---------------------------------------------------------------------------
# Manifest sanity — pin invariants so a careless edit fails CI
# ---------------------------------------------------------------------------


def test_manifest_paths_are_unique(vi):
    """Two manifest entries with the same path would silently overwrite
    each other on apply. Keep paths unique."""
    paths = [e.vault_path for e in vi.MANIFEST]
    assert len(paths) == len(set(paths)), "duplicate vault_path in MANIFEST"


def test_manifest_paths_use_canonical_kaori_vault_helpers(vi):
    """Every manifest path must start with platform/, tenant/, or
    service/ — the three buckets KaoriVault.platform_path /
    tenant_path / service_path produce. Anything else means an entry
    bypassed the helpers + would land outside RLS-aligned conventions."""
    for entry in vi.MANIFEST:
        assert entry.vault_path.startswith(("platform/", "tenant/", "service/")), (
            f"non-canonical path: {entry.vault_path}"
        )
