#!/usr/bin/env python3
"""
Issue #4 — Kafka schema additive-only enforcement.

Diffs every JSON schema under ``infrastructure/kafka/schemas/`` against
its committed version on the base branch (``origin/main`` by default).
Exits 0 when every change is additive, 1 when at least one change is
breaking.

Allowed (silent OK)
-------------------
  * Adding a new optional field
  * Adding a new required field WHEN the schema file itself is new in
    this PR (i.e., did not exist on the base branch)
  * Tweaking a description / comment

Blocked (exit 1)
----------------
  * Renaming or removing a field (required OR optional)
  * Marking an existing optional field as required
  * Tightening a type (e.g., string → integer, integer → number→int)
  * Tightening ``additionalProperties`` (true → false)
  * Adding a new required field to an EXISTING schema (consumers
    deployed before the producer would crash)

How it locates the base branch
------------------------------
1. ``KAORI_KAFKA_BASE_REF`` env var (used by the CI workflow to point
   at the PR target branch in detached-HEAD mode).
2. ``origin/main`` — works for local ``git`` checkouts.
3. ``HEAD~1`` — last-resort fallback for shallow clones.

The script prints a per-schema verdict so a maintainer reviewing CI
can tell at a glance which file broke the rule and why.

Usage
-----
::

    python scripts/check-kafka-contracts.py            # default base
    python scripts/check-kafka-contracts.py --base main
    python scripts/check-kafka-contracts.py --schemas /custom/path

Exit codes: 0 = OK, 1 = breaking change, 2 = CLI / git error.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


# ─── git plumbing ────────────────────────────────────────────────

def _git(args: list[str]) -> tuple[int, str, str]:
    """Run a git command from the repo root, return (rc, stdout, stderr)."""
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _resolve_base(explicit: str | None) -> str:
    """Pick the base ref to diff against. Order of preference:
    explicit CLI flag → KAORI_KAFKA_BASE_REF env → origin/main → HEAD~1.
    """
    if explicit:
        return explicit
    env = os.environ.get("KAORI_KAFKA_BASE_REF")
    if env:
        return env
    rc, _, _ = _git(["rev-parse", "--verify", "origin/main"])
    if rc == 0:
        return "origin/main"
    return "HEAD~1"


def _file_at_ref(ref: str, path: Path) -> str | None:
    """Return the contents of ``path`` at git ref ``ref``, or None when
    the file did not exist there. Uses ``git show ref:path`` so a
    file-not-found surfaces as exit code 128 + a recognisable message
    on stderr."""
    rc, stdout, stderr = _git(["show", f"{ref}:{path.as_posix()}"])
    if rc == 0:
        return stdout
    if "exists on disk, but not in" in stderr or "does not exist" in stderr or "fatal: path" in stderr:
        return None
    # Other git failures (corrupt ref, broken repo) — re-raise as a
    # CLI-level error so the user sees the real cause.
    raise RuntimeError(f"git show {ref}:{path}: {stderr.strip()}")


# ─── schema diff ─────────────────────────────────────────────────

def _required(schema: dict) -> set[str]:
    return set(schema.get("required") or [])


def _properties(schema: dict) -> dict[str, Any]:
    return dict(schema.get("properties") or {})


def _type_of(prop: dict) -> str | list[str] | None:
    return prop.get("type")


def _classify_changes(old: dict, new: dict) -> list[str]:
    """Return a list of human-readable BREAKING messages, empty when
    every change is additive."""
    breaks: list[str] = []

    old_props = _properties(old)
    new_props = _properties(new)
    old_required = _required(old)
    new_required = _required(new)

    # Removed properties (rename shows up as "removed X + added Y" — both
    # are flagged; the developer reading CI sees one as a removal and one
    # as a missing-from-old which is enough context).
    for name in old_props:
        if name not in new_props:
            breaks.append(
                f"property '{name}' was removed (rename or drop). "
                "Use a deprecation window: add the new name as optional, "
                "dual-emit, then remove the old name in a later release."
            )

    # Type narrowing (broad → narrow). We only flag the obvious
    # narrowings; the catch-all is "type changed at all" which is
    # almost never safe.
    for name in old_props:
        if name not in new_props:
            continue
        old_type = _type_of(old_props[name])
        new_type = _type_of(new_props[name])
        if old_type != new_type:
            # Allow None → typed (legacy schemas with no `type`).
            if old_type is None:
                continue
            breaks.append(
                f"property '{name}' type changed from {old_type!r} to "
                f"{new_type!r}. Existing producers may emit values "
                "outside the new constraint; consumers will start "
                "rejecting otherwise-valid messages."
            )

    # Required tightening: optional → required is a break.
    newly_required = new_required - old_required
    # The intersection with old_props isolates "was already a property,
    # just got promoted to required". A field that's both new (not in
    # old_props) AND required is a new-required-on-existing-schema —
    # also a break, handled below.
    for name in newly_required:
        if name in old_props:
            breaks.append(
                f"property '{name}' became required (was optional). "
                "Producers that haven't deployed yet would emit "
                "payloads missing this field; the validator would "
                "reject them. Stage in two PRs: producers start "
                "emitting -> consumers move to required next release."
            )

    # New required field on an existing schema. (For brand-new schemas
    # the caller has filtered this case out before reaching here.)
    new_only_required = (newly_required - set(old_props))
    for name in new_only_required:
        breaks.append(
            f"new required property '{name}' on an existing schema. "
            "Consumers deployed before the producer would crash on the "
            "first event without this field."
        )

    # additionalProperties tightening (true → false).
    old_extra = old.get("additionalProperties", True)
    new_extra = new.get("additionalProperties", True)
    # JSON Schema treats both `True` and an object as "additional
    # allowed in some shape"; only False is a hard close.
    if old_extra is not False and new_extra is False:
        breaks.append(
            "additionalProperties tightened from "
            f"{old_extra!r} to false. Producers may already be sending "
            "fields outside the schema; the validator will start "
            "rejecting them."
        )

    return breaks


# ─── main loop ───────────────────────────────────────────────────

def _list_schemas(schema_dir: Path) -> list[Path]:
    return sorted(p for p in schema_dir.glob("*.json") if p.is_file())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--base", default=None,
        help="git ref to diff against (default: KAORI_KAFKA_BASE_REF env, "
             "then origin/main, then HEAD~1)",
    )
    ap.add_argument(
        "--schemas", default="infrastructure/kafka/schemas",
        help="directory of JSON schema files (default: infrastructure/kafka/schemas)",
    )
    args = ap.parse_args(argv)

    schema_dir = Path(args.schemas)
    if not schema_dir.is_dir():
        print(f"error: schema directory not found: {schema_dir}", file=sys.stderr)
        return 2

    base = _resolve_base(args.base)
    print(f"Base ref: {base}")
    print(f"Schemas:  {schema_dir}")
    print()

    schemas = _list_schemas(schema_dir)
    if not schemas:
        print("(no schema files — nothing to check)")
        return 0

    any_break = False
    for path in schemas:
        rel = path.relative_to(Path.cwd()) if path.is_absolute() else path

        # Current contents
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"BREAKING  {rel}: file is not valid JSON ({e})")
            any_break = True
            continue

        # Old contents from the base ref
        try:
            old_text = _file_at_ref(base, path)
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2

        if old_text is None:
            # Brand-new schema in this PR — every field is "added", so
            # nothing to compare. We trust the author to have authored
            # the file correctly; the runtime validator will catch
            # producer payloads that don't match.
            print(f"OK        {rel} (new schema)")
            continue

        try:
            old = json.loads(old_text)
        except json.JSONDecodeError as e:
            # The old version on main was bad — rare, but possible if
            # the base ref is a commit that pre-dates the validator.
            # Treat as "everything is new" rather than blocking the PR
            # on a historical bug.
            print(f"OK        {rel} (base was unparseable: {e}; treating as new)")
            continue

        breaks = _classify_changes(old, current)
        if breaks:
            any_break = True
            print(f"BREAKING  {rel}")
            for b in breaks:
                # ASCII bullet so the script can run on a Windows shell
                # whose stdout encoding is cp1252 (default for git-bash
                # subprocess capture). The Linux CI runner doesn't
                # care; the local-dev case does.
                print(f"          - {b}")
        else:
            print(f"OK        {rel}")

    print()
    if any_break:
        print("FAIL — at least one schema change is not additive. See above.")
        return 1
    print("PASS — every schema change is additive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
