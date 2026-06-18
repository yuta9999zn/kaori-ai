"""
Import VinFast fake data bundle into workflow a167bf64-be0e-4703-980b-0ae88cc49f07
via the same /api/v1/upload pipeline as the FE — so workflow_step_documents
rows + Bronze rows land exactly like a real user upload.

Bundle layout (extracted from D:\\Kaori Document\\fake data):
  - orders.csv             — 280 work-order rows
  - step_timings.csv       — 6160 step-execution rows
  - 5 sample PDFs          — per-order documents

Mapping (README says):
  S01 Vehicle Request Intake   → 3 PO PDFs + orders.csv
  S02 Order Enrichment & MDM   → step_timings.csv
  S08 Export Doc               → INV PDF (node not present today → skip)
  S11/S12 Transit & Import     → BOL PDF (node not present today → skip)

Usage
-----
    python scripts/import_vinfast_fake_data.py \\
        --bundle /tmp/vinfast/vinfast_test_bundle \\
        --workflow a167bf64-be0e-4703-980b-0ae88cc49f07

The script logs in as vinfast@kaori.local (created manually 2026-05-17 with the
same password hash as vingroup@kaori.local). The user belongs to the VinFast
enterprise that owns the workflow.

Idempotent: K-8 SHA-256 dedupe — re-running uploads the same files and the
ingestor returns the existing run_id without re-processing.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import uuid
from pathlib import Path
from typing import Optional

import httpx


# Force stdout to UTF-8 on Windows so the Vietnamese + arrow characters
# in progress lines don't blow up with UnicodeEncodeError on cp1252.
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)


GATEWAY_DEFAULT  = "http://localhost:8080"
AUTH_DEFAULT     = "http://localhost:8091"
LOGIN_EMAIL      = "vinfast@kaori.local"
LOGIN_PASSWORD   = "Admin@kaori1"


def _login(auth_url: str) -> str:
    with httpx.Client(timeout=15.0) as c:
        r = c.post(
            f"{auth_url}/auth/login",
            json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
        )
        r.raise_for_status()
        return r.json()["accessToken"]


def _upload(
    *,
    gateway_url:      str,
    jwt:              str,
    enterprise_id:    str,
    user_id:          str,
    workflow_step_id: str,
    department_id:    str,
    file_path:        Path,
    content_type:     str = "application/octet-stream",
) -> dict:
    """POST to /api/v1/upload with workflow attachment headers. Returns the
    response body so the caller can show run_id + status."""
    with httpx.Client(timeout=60.0) as c:
        with file_path.open("rb") as fh:
            r = c.post(
                f"{gateway_url}/api/v1/upload",
                files={"file": (file_path.name, fh, content_type)},
                headers={
                    "Authorization":       f"Bearer {jwt}",
                    "X-Enterprise-ID":     enterprise_id,
                    "X-User-ID":           user_id,
                    "X-Workflow-Step-ID":  workflow_step_id,
                    "X-Department-ID":     department_id,
                    "Idempotency-Key":     str(uuid.uuid4()),
                },
            )
        if r.status_code != 200:
            return {"error": True, "status": r.status_code, "body": r.text[:300]}
        return r.json()


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle", required=True,
                    help="Path to the unzipped vinfast_test_bundle directory.")
    ap.add_argument("--workflow", required=True,
                    help="Workflow UUID (anh's pre-built distribution workflow).")
    ap.add_argument("--gateway", default=GATEWAY_DEFAULT)
    ap.add_argument("--auth",    default=AUTH_DEFAULT)
    args = ap.parse_args(argv)

    bundle = Path(args.bundle)
    if not bundle.is_dir():
        print(f"[err] bundle dir not found: {bundle}", file=sys.stderr)
        return 1

    # ── Login ─────────────────────────────────────────────────────
    print(f"[1/3] login as {LOGIN_EMAIL} …", flush=True)
    jwt = _login(args.auth)
    # The JWT carries enterprise_id + user_id; the gateway forwards them as
    # X-* headers, but for direct script-to-gateway calls we send them
    # explicitly so the ingestor knows which tenant scope to apply.
    import base64
    payload = json.loads(base64.urlsafe_b64decode(jwt.split(".")[1] + "==").decode())
    enterprise_id = payload["enterprise_id"]
    user_id       = payload["sub"]
    print(f"      jwt OK; enterprise_id={enterprise_id} user_id={user_id}")

    # ── Resolve workflow nodes ────────────────────────────────────
    print(f"[2/3] resolve workflow {args.workflow} …", flush=True)
    with httpx.Client(timeout=15.0) as c:
        r = c.get(
            f"{args.gateway}/api/v1/workflows/{args.workflow}/tree",
            headers={
                "Authorization":   f"Bearer {jwt}",
                "X-Enterprise-ID": enterprise_id,
                "X-User-ID":       user_id,
            },
        )
        r.raise_for_status()
        tree = r.json()
    nodes_by_prefix = {n["title"].split()[0]: n for n in tree["nodes"]}
    dept_id = None
    for n in tree["nodes"]:
        if n.get("category") == "data_input":
            # workflow_nodes carries department_id but the tree endpoint
            # doesn't surface it; resolve from the workflow header instead.
            break
    # Pull dept_id from the workflow header — every node in a single workflow
    # shares the same dept (mig 053).
    with httpx.Client(timeout=15.0) as c:
        r = c.get(
            f"{args.gateway}/api/v1/workflows/{args.workflow}",
            headers={
                "Authorization":   f"Bearer {jwt}",
                "X-Enterprise-ID": enterprise_id,
            },
        )
        r.raise_for_status()
        dept_id = r.json()["department_id"]
    print(f"      department_id={dept_id}; nodes={list(nodes_by_prefix.keys())}")

    # ── Map files to nodes ────────────────────────────────────────
    s01 = nodes_by_prefix.get("S01")
    s02 = nodes_by_prefix.get("S02")
    if s01 is None:
        print("[err] workflow has no S01 node — abort.", file=sys.stderr)
        return 1
    s01_id = s01["node_id"]
    s02_id = s02["node_id"] if s02 else s01_id   # fall back

    plan: list[tuple[str, Path, str, str]] = []
    # (label, path, content_type, target_node_id)

    # Tabular intake — formats the Bronze ingestor accepts today.
    plan.append(("orders.csv → S01", bundle / "orders.csv",
                 "text/csv", s01_id))
    plan.append(("step_timings.csv → S02", bundle / "step_timings.csv",
                 "text/csv", s02_id))
    plan.append(("vinfast_workflow_dataset.xlsx → S02",
                 bundle / "vinfast_workflow_dataset.xlsx",
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 s02_id))

    # NOTE — PDFs (sample_documents/*.pdf) + workflow_dataset.json are NOT
    # uploaded today: the Stage 1 ingestor only handles tabular data. PDFs
    # belong in Stage 6 Knowledge Extraction (out of scope until DocSage
    # lands P15-S11). JSON has no Bronze schema. Re-add when endpoints
    # exist.

    # ── Upload ────────────────────────────────────────────────────
    print(f"[3/3] uploading {len(plan)} files …", flush=True)
    results: list[dict] = []
    for label, path, ct, node_id in plan:
        if not path.exists():
            print(f"  - skip (missing) {label}")
            continue
        size_mb = path.stat().st_size / 1_048_576
        print(f"  - {label}  ({size_mb:.2f} MB) …", end=" ", flush=True)
        resp = _upload(
            gateway_url=args.gateway,
            jwt=jwt,
            enterprise_id=enterprise_id,
            user_id=user_id,
            workflow_step_id=node_id,
            department_id=dept_id,
            file_path=path,
            content_type=ct,
        )
        if resp.get("error"):
            print(f"FAIL HTTP {resp['status']}: {resp['body'][:120]}")
        else:
            print(f"OK run_id={resp.get('run_id', '?')[:8]} "
                  f"status={resp.get('status', '?')}")
        results.append({"label": label, **resp})

    n_ok    = sum(1 for r in results if not r.get("error"))
    n_dup   = sum(1 for r in results if r.get("status") == "duplicate")
    n_err   = sum(1 for r in results if r.get("error"))
    print()
    print(f"Summary: {n_ok}/{len(plan)} ok  ({n_dup} dedup'd)  {n_err} fail")
    return 0 if n_err == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
