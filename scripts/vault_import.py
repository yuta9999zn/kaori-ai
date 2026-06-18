"""
vault_import — env → Vault migration helper (P15-S9 D2 / K-18).

Reads a dotenv file and pushes each secret to its canonical Vault KV v2
path so production can stop loading secrets from environment variables.

Path mapping is declared explicitly below (MANIFEST). Adding a secret
requires touching this file — no implicit env→path inference. The point
is auditability: a reader can see every secret Kaori intends to migrate
and where it lands without grepping all four kaori_vault.py copies.

Usage
=====
Dry run (default — prints plan, writes nothing)::

    python scripts/vault_import.py --env .env

Apply (writes to Vault — needs VAULT_ADDR + VAULT_TOKEN)::

    python scripts/vault_import.py --env .env --apply

Filter to a single bucket (handy for incremental migrations)::

    python scripts/vault_import.py --env .env --apply --only platform/api_keys

Verify the import landed (read-back, no writes)::

    python scripts/vault_import.py --env .env --verify

Exit codes
==========
    0  all entries handled (skipped placeholders count as success)
    1  CLI / IO / Vault error during apply or verify
    2  manifest declares an env var that .env doesn't define
       (only when --strict; default is to warn + skip)

Why dry-run by default
======================
Vault writes are versioned but a botched bulk import still pollutes the
history + audit log. Default to --dry-run; force --apply when ready.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Path bootstrap so `from services.ai_orchestrator.shared.kaori_vault import ...`
# works whether the script is invoked from repo root or scripts/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# All four kaori_vault.py copies are byte-identical (verified pre-commit).
# Import the ai-orchestrator one as the canonical implementation.
sys.path.insert(0, str(_REPO_ROOT / "services" / "ai-orchestrator"))
from shared.kaori_vault import KaoriVault, VaultError  # noqa: E402


# ---------------------------------------------------------------------------
# Migration manifest — single source of truth for env → Vault mapping.
#
# Each entry maps one Vault path to a set of (env_var, key) pairs. Multiple
# env vars collapse into a single Vault secret when they belong to the
# same logical bundle (e.g. SMTP host + user + password live in one secret).
# Single-env secrets get a synthetic key matching the env var name lower-
# cased — readers can still pass `key=` to disambiguate.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecretEntry:
    vault_path: str
    env_to_key: tuple[tuple[str, str], ...]  # ((env_var, vault_key), ...)
    note: str = ""


MANIFEST: tuple[SecretEntry, ...] = (
    # Platform LLM API keys — K-4 vendor adapter pluggable, ADR-0015
    SecretEntry(
        vault_path=KaoriVault.platform_path("api_keys", "anthropic"),
        env_to_key=(("ANTHROPIC_API_KEY", "api_key"),),
        note="Anthropic Claude (vendor adapter when consent_external=true)",
    ),
    SecretEntry(
        vault_path=KaoriVault.platform_path("api_keys", "openai"),
        env_to_key=(("OPENAI_API_KEY", "api_key"),),
        note="OpenAI GPT-4o vendor adapter",
    ),
    SecretEntry(
        vault_path=KaoriVault.platform_path("api_keys", "google"),
        env_to_key=(("GOOGLE_API_KEY", "api_key"),),
        note="Google Gemini vendor adapter",
    ),
    # Platform SMTP — bundled (host + user + password together)
    SecretEntry(
        vault_path=KaoriVault.platform_path("smtp", "credentials"),
        env_to_key=(
            ("SMTP_HOST", "host"),
            ("SMTP_PORT", "port"),
            ("SMTP_USER", "user"),
            ("SMTP_PASSWORD", "password"),
        ),
        note="Notification-service SMTP outbox creds",
    ),
    # Platform databases — Phase 1 legacy DSN parts
    SecretEntry(
        vault_path=KaoriVault.platform_path("db", "postgres"),
        env_to_key=(("POSTGRES_PASSWORD", "password"),),
        note="Primary Postgres root password (P15-S9 will rotate per-tenant)",
    ),
    SecretEntry(
        vault_path=KaoriVault.platform_path("db", "legacy"),
        env_to_key=(
            ("DB_HOST", "host"),
            ("DB_PORT", "port"),
            ("DB_NAME", "database"),
            ("DB_USER", "user"),
            ("DB_PASSWORD", "password"),
        ),
        note="Legacy ETL Postgres DSN (etl/ scripts only)",
    ),
    # Platform observability
    SecretEntry(
        vault_path=KaoriVault.platform_path("observability", "grafana"),
        env_to_key=(
            ("GRAFANA_USER", "user"),
            ("GRAFANA_PASSWORD", "password"),
        ),
        note="Grafana admin credentials",
    ),
    # Auth-service — JWT keypair + MFA master key
    SecretEntry(
        vault_path=KaoriVault.service_path("auth-service", "jwt_keypair"),
        env_to_key=(
            ("JWT_PRIVATE_KEY", "private_key"),
            ("JWT_PUBLIC_KEY", "public_key"),
        ),
        note="JWT RS256 base64-PEM keypair (rotation: regenerate + re-import)",
    ),
    SecretEntry(
        vault_path=KaoriVault.service_path("auth-service", "mfa_master_key"),
        env_to_key=(("KAORI_MFA_KEY", "master_key"),),
        note="AES-256 master key for TOTP secret encryption (CLAUDE.md §15)",
    ),
    # Platform connectors — Phase 1 Zalo (Phase 2 Zalo Bot adapter)
    SecretEntry(
        vault_path=KaoriVault.platform_path("connectors", "zalo"),
        env_to_key=(
            ("ZALO_ACCESS_TOKEN", "access_token"),
            ("ZALO_GROUP_ID", "group_id"),
        ),
        note="Zalo OA legacy report dispatcher",
    ),
)


# ---------------------------------------------------------------------------
# .env parsing — minimal, no dotenv dependency.
# Supports `KEY=value`, ignores blanks + `#` comments, strips matching quotes.
# ---------------------------------------------------------------------------


_PLACEHOLDER_PATTERNS = ("<SECRET>", "<BASE64_", "<YOUR_", "<PATH>", "<EMAIL_LIST>", "<GROUP_ID>")


def _is_placeholder(value: str) -> bool:
    """Treat .env.example placeholders + empty strings as 'not set'.

    The migration script must not push '<SECRET>' literally into Vault
    — it would mask a missing secret as a populated one and break
    production startup later when production reads back garbage.
    """
    if not value:
        return True
    return any(pat in value for pat in _PLACEHOLDER_PATTERNS)


def parse_dotenv(path: Path) -> dict[str, str]:
    """Parse a dotenv file into a flat dict.

    Intentionally minimal — we don't need variable interpolation or
    multiline values for the secret set we're migrating.
    """
    out: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"dotenv file not found: {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip a single matching pair of quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


# ---------------------------------------------------------------------------
# Plan + apply
# ---------------------------------------------------------------------------


@dataclass
class ImportPlan:
    path: str
    payload: dict[str, str]
    skipped_envs: tuple[str, ...]
    note: str

    @property
    def is_empty(self) -> bool:
        """Path with zero usable env values — nothing to push."""
        return not self.payload


def build_plan(
    manifest: Iterable[SecretEntry],
    env: dict[str, str],
    *,
    only_prefix: str | None = None,
) -> list[ImportPlan]:
    plans: list[ImportPlan] = []
    for entry in manifest:
        if only_prefix and not entry.vault_path.startswith(only_prefix):
            continue
        payload: dict[str, str] = {}
        skipped: list[str] = []
        for env_var, key in entry.env_to_key:
            value = env.get(env_var, "")
            if _is_placeholder(value):
                skipped.append(env_var)
                continue
            payload[key] = value
        plans.append(
            ImportPlan(
                path=entry.vault_path,
                payload=payload,
                skipped_envs=tuple(skipped),
                note=entry.note,
            )
        )
    return plans


def render_plan(plans: list[ImportPlan]) -> str:
    """Human-readable plan summary. Never prints secret values — only
    keys + lengths so a copy-paste of stdout to a chat doesn't leak."""
    lines = []
    pushed = 0
    empty = 0
    for plan in plans:
        marker = "  WRITE" if plan.payload else "  SKIP "
        if plan.payload:
            pushed += 1
        else:
            empty += 1
        keys_summary = ", ".join(
            f"{k}=<{len(v)} chars>" for k, v in sorted(plan.payload.items())
        ) or "(no values)"
        lines.append(f"{marker} {plan.path}")
        lines.append(f"         keys: {keys_summary}")
        if plan.skipped_envs:
            lines.append(f"         skipped envs: {', '.join(plan.skipped_envs)}")
        if plan.note:
            lines.append(f"         note: {plan.note}")
    lines.append("")
    lines.append(f"Plan summary: {pushed} writes, {empty} skipped (no values).")
    return "\n".join(lines)


async def apply_plan(plans: list[ImportPlan], vault: KaoriVault) -> tuple[int, int]:
    """Apply non-empty plans. Returns (written, failed)."""
    written = 0
    failed = 0
    for plan in plans:
        if plan.is_empty:
            continue
        try:
            await vault.put(plan.path, plan.payload)
            print(f"  OK   {plan.path}", flush=True)
            written += 1
        except VaultError as exc:
            print(f"  FAIL {plan.path}: {exc}", file=sys.stderr, flush=True)
            failed += 1
    return written, failed


async def verify_plan(plans: list[ImportPlan], vault: KaoriVault) -> tuple[int, int, int]:
    """Read-back each non-empty plan and assert keys present. Does not
    print values — only key count + match status. Returns
    (matched, mismatched, missing)."""
    matched = mismatched = missing = 0
    for plan in plans:
        if plan.is_empty:
            continue
        try:
            stored = await vault.get(plan.path)
        except VaultError as exc:
            print(f"  MISS {plan.path}: {exc}", file=sys.stderr, flush=True)
            missing += 1
            continue
        expected_keys = set(plan.payload.keys())
        actual_keys = set(stored.keys())
        if expected_keys.issubset(actual_keys):
            print(f"  OK   {plan.path} ({len(expected_keys)} keys)")
            matched += 1
        else:
            print(
                f"  DIFF {plan.path}: expected {sorted(expected_keys)} "
                f"got {sorted(actual_keys)}",
                file=sys.stderr,
            )
            mismatched += 1
    return matched, mismatched, missing


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate .env secrets to Vault paths declared in MANIFEST.",
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=Path(".env"),
        help="Path to the dotenv file to read (default: .env)",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Only process Vault paths starting with this prefix (e.g. platform/api_keys).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Actually write to Vault (default is dry-run).",
    )
    mode.add_argument(
        "--verify",
        action="store_true",
        help="Read-back each path and check expected keys are present.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit code 2 if a manifest entry has no usable values "
        "(default: warn + skip).",
    )
    return parser


async def _amain(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        env = parse_dotenv(args.env)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    plans = build_plan(MANIFEST, env, only_prefix=args.only)

    if args.strict:
        empty = [p for p in plans if p.is_empty]
        if empty:
            print(
                f"STRICT: {len(empty)} manifest entries have no usable values: "
                + ", ".join(p.path for p in empty),
                file=sys.stderr,
            )
            return 2

    print(render_plan(plans))

    if args.apply:
        if not os.getenv("VAULT_TOKEN"):
            print(
                "ERROR: --apply requires VAULT_TOKEN env var (and VAULT_ADDR if not http://vault:8200).",
                file=sys.stderr,
            )
            return 1
        vault = KaoriVault()
        print(f"Applying to {vault.addr} ...")
        written, failed = await apply_plan(plans, vault)
        print(f"Done. {written} written, {failed} failed.")
        return 1 if failed else 0

    if args.verify:
        if not os.getenv("VAULT_TOKEN"):
            print("ERROR: --verify requires VAULT_TOKEN env var.", file=sys.stderr)
            return 1
        vault = KaoriVault()
        print(f"Verifying against {vault.addr} ...")
        matched, mismatched, missing = await verify_plan(plans, vault)
        print(f"Done. {matched} match, {mismatched} mismatch, {missing} missing.")
        return 1 if (mismatched or missing) else 0

    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())
