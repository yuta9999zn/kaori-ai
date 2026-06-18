"""
Perf baseline — Python version of perf_baseline.sh for hosts without
apache-bench installed (Windows dev laptop).

Fires N concurrent httpx requests against a fixed set of read-only
endpoints, reports p50/p95/p99 latency + req/sec. Same purpose as
the shell version: capture a number-anchor so future perf regressions
show up as deltas instead of subjective "feels slower".

Usage
-----
    python scripts/perf_baseline.py
    python scripts/perf_baseline.py --n 500 --concurrency 20
    python scripts/perf_baseline.py > docs/perf/baseline-2026-05-18.txt
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from typing import Any, Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx", file=sys.stderr)
    sys.exit(1)


ENT = os.getenv("PERF_ENT_ID", "f90e0cdb-dc0c-4b91-b86a-92c824aa1103")
USR = os.getenv("PERF_USER_ID", "dafbd87e-533a-4320-b6ec-7b905f7bf6d6")
GATEWAY = os.getenv("GATEWAY", "http://localhost:8080")
ORCH = os.getenv("ORCH", "http://localhost:8093")
LLMGW = os.getenv("LLMGW", "http://localhost:8095")


HEADERS = {"X-Enterprise-ID": ENT, "X-User-ID": USR}


async def hit_one(client: httpx.AsyncClient, method: str, url: str,
                   *, body: Optional[Any] = None) -> tuple[int, float]:
    t0 = time.perf_counter()
    if method == "GET":
        resp = await client.get(url, headers=HEADERS)
    else:
        resp = await client.post(url, headers={**HEADERS, "Content-Type": "application/json"},
                                 json=body or {})
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return resp.status_code, elapsed_ms


async def run_endpoint(name: str, method: str, url: str, n: int,
                        concurrency: int, body: Optional[Any] = None) -> None:
    print(f"\n--- [{name}] {method} {url}")
    sem = asyncio.Semaphore(concurrency)
    samples: list[tuple[int, float]] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Warm-up — 3 hits to prime any cold caches.
        for _ in range(3):
            try:
                await hit_one(client, method, url, body=body)
            except Exception:
                pass

        async def _one() -> None:
            async with sem:
                try:
                    samples.append(await hit_one(client, method, url, body=body))
                except httpx.HTTPError as e:
                    samples.append((-1, 0.0))

        t0 = time.perf_counter()
        await asyncio.gather(*(_one() for _ in range(n)))
        wall = time.perf_counter() - t0

    statuses = [s for s, _ in samples]
    latencies = [ms for s, ms in samples if s >= 0]
    failed = sum(1 for s in statuses if s < 0)
    non200 = sum(1 for s in statuses if s >= 0 and s >= 400)

    if not latencies:
        print(f"  NO successful responses (failed={failed})")
        return

    latencies.sort()
    def pct(p: float) -> float:
        idx = int(len(latencies) * p)
        return latencies[min(idx, len(latencies) - 1)]

    print(f"  Total time         : {wall:.2f} s")
    print(f"  Requests/sec       : {n/wall:.1f}")
    print(f"  Failed             : {failed}  Non-2xx: {non200}")
    print(f"  Latency p50 / p95  : {pct(0.50):.1f} ms / {pct(0.95):.1f} ms")
    print(f"  Latency p99 / max  : {pct(0.99):.1f} ms / {max(latencies):.1f} ms")
    print(f"  Latency mean       : {statistics.mean(latencies):.1f} ms")


async def main(args: argparse.Namespace) -> None:
    n = args.n
    c = args.concurrency
    print("=" * 60)
    print(f"Kaori perf baseline — {n} reqs × {c} concurrent")
    import datetime as _dt
    print(f"Captured: {_dt.datetime.utcnow().isoformat()}Z")
    print(f"Gateway : {GATEWAY}")
    print(f"Tenant  : {ENT}")
    print("=" * 60)

    targets = [
        ("health-check",            "GET",  f"{GATEWAY}/health",                              None),
        ("orch-roi-subscription",   "GET",  f"{ORCH}/economics/roi/subscription",             None),
        ("orch-reencrypt-status",   "GET",  f"{ORCH}/p2/auth/field-key/reencrypt/status",     None),
        ("orch-sso-google-start",   "GET",  f"{ORCH}/p2/auth/sso/google/start?return_url=http://localhost:3000/cb", None),
        ("gw-sso-google-start",     "GET",  f"{GATEWAY}/api/v1/p2/auth/sso/google/start?return_url=http://localhost:3000/cb", None),
        ("llm-validate-input",      "POST", f"{LLMGW}/guardrails/validate-input",
            {"text": "Doanh thu thang 5 tang 12%"}),
    ]

    for name, method, url, body in targets:
        try:
            await run_endpoint(name, method, url, n, c, body=body)
        except Exception as e:
            print(f"  EXCEPTION: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("Baseline complete.")
    print()
    print("Save to: docs/perf/baseline-<date>.txt  (>= )")
    print("Compare via: diff old new")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=int(os.getenv("PERF_N", "100")))
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("PERF_C", "10")))
    asyncio.run(main(parser.parse_args()))
