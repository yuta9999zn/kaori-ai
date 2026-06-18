#!/usr/bin/env python3
"""
Sprint 6.5 — dump OpenAPI 3 specs from FastAPI services to JSON files.

Two services are FastAPI and expose ``app.openapi()`` natively:

  * services/data-pipeline    →  docs/api-specs/pipeline.openapi.json
  * services/ai-orchestrator  →  docs/api-specs/orchestrator.openapi.json

The third backend (auth-service, Java/Spring) exposes its spec at
``/v3/api-docs`` via springdoc-openapi at runtime — see
``docs/specs/API_CODEGEN.md`` for the curl recipe to refresh
``docs/api-specs/auth.openapi.json``.

Why dump to file (instead of fetch at codegen time):

  * The frontend codegen pipeline runs offline / in CI without booting
    the whole stack.
  * The committed spec doubles as a contract snapshot — a drift in BE
    code shows up as a diff in this file, easy to review.
  * Idempotent: same code → same file. CI can ``git diff`` to flag
    schema changes that didn't refresh the FE types.

Usage::

    python scripts/dump_openapi.py            # dump both FastAPI specs
    python scripts/dump_openapi.py pipeline   # one service only
    python scripts/dump_openapi.py --check    # exit 1 if specs are stale

The ``--check`` mode is what CI uses: it dumps to a temp location and
compares against the committed spec; non-zero exit means a developer
forgot to commit a regenerated spec after touching a router signature.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "api-specs"

SERVICES = {
    "pipeline": {
        "service_dir": ROOT / "services" / "data-pipeline",
        "package":     "data_pipeline.main",
        "title":       "Kaori Data Pipeline",
    },
    "orchestrator": {
        "service_dir": ROOT / "services" / "ai-orchestrator",
        "package":     "ai_orchestrator.main",
        "title":       "Kaori AI Orchestrator",
    },
}


def _bootstrap_path(service_dir: Path) -> None:
    """Mirror the conftest.py path bootstrap so relative imports inside
    the service package resolve. Each FastAPI service is a hyphenated
    directory imported under an underscore alias by tests + this script."""
    if str(service_dir) not in sys.path:
        sys.path.insert(0, str(service_dir))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def _import_app(service: dict):
    """Import the FastAPI app object without running its lifespan
    (init_db_pool / Kafka producer / etc. — all unwanted side effects).
    The OpenAPI generation only walks routes; no I/O needed."""
    _bootstrap_path(service["service_dir"])

    # Re-register the package alias the way conftest.py does so relative
    # imports inside main.py resolve. data-pipeline = data_pipeline,
    # ai-orchestrator = ai_orchestrator.
    pkg = service["package"].split(".")[0]
    if pkg not in sys.modules:
        import types, importlib.util
        mod = types.ModuleType(pkg)
        mod.__path__ = [str(service["service_dir"])]
        mod.__package__ = pkg
        mod.__spec__ = importlib.util.spec_from_file_location(
            pkg, str(service["service_dir"] / "__init__.py"),
            submodule_search_locations=[str(service["service_dir"])])
        sys.modules[pkg] = mod

    main_mod = importlib.import_module(service["package"])
    return main_mod.app


def dump_spec(name: str, dest: Path) -> dict:
    """Generate the OpenAPI spec dict and write it to ``dest`` as
    pretty-printed JSON. Returns the spec for callers that want to inspect."""
    svc = SERVICES[name]
    app = _import_app(svc)
    spec = app.openapi()

    # Stable serialisation so git diffs are signal-only.
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return spec


def check_stale(name: str) -> bool:
    """Return True if the regenerated spec differs from the committed one.
    Used by CI — the dev workflow runs the dump command directly."""
    import tempfile

    target = OUT_DIR / f"{name}.openapi.json"
    if not target.is_file():
        print(f"[{name}] missing committed spec at {target}", file=sys.stderr)
        return True

    with tempfile.NamedTemporaryFile(
            "w+", suffix=".json", encoding="utf-8", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        dump_spec(name, tmp_path)
        committed = target.read_text(encoding="utf-8")
        regenerated = tmp_path.read_text(encoding="utf-8")
        if committed != regenerated:
            print(f"[{name}] STALE — committed spec differs from current code.",
                  file=sys.stderr)
            print(f"        Run: python scripts/dump_openapi.py {name}",
                  file=sys.stderr)
            return True
        print(f"[{name}] OK — {target.relative_to(ROOT)} matches code")
        return False
    finally:
        tmp_path.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("services", nargs="*",
                    help=f"Subset to dump (default: all of {list(SERVICES)}).")
    ap.add_argument("--check", action="store_true",
                    help="Verify committed specs match current code; exit 1 on drift.")
    args = ap.parse_args()

    targets = args.services or list(SERVICES.keys())
    unknown = [t for t in targets if t not in SERVICES]
    if unknown:
        print(f"Unknown service(s): {unknown}. Known: {list(SERVICES)}",
              file=sys.stderr)
        return 2

    if args.check:
        bad = sum(1 for name in targets if check_stale(name))
        return 1 if bad else 0

    for name in targets:
        dest = OUT_DIR / f"{name}.openapi.json"
        spec = dump_spec(name, dest)
        path_count = len(spec.get("paths", {}))
        print(f"[{name}] wrote {dest.relative_to(ROOT)}  ({path_count} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
