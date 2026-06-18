"""
Tests for ExcelFilesystemConnector — P15-S9 D4b real impl.

All tests use ``tmp_path`` so no shared state escapes the test session.
We build real .xlsx files via openpyxl (small workbooks, ~1 KB each)
so the metadata-extraction path runs end-to-end without mocks.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from openpyxl import Workbook

from ingestion.connectors.excel_filesystem import ExcelFilesystemConnector
from ingestion.connectors.excel_filesystem.connector import _derive_event_id


TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ─── Fixtures ────────────────────────────────────────────────────────


def _write_workbook(
    path: Path,
    *,
    creator: str = "Anh Yuta",
    last_modified_by: str = "Anh Yuta",
    sheet_data: list[list[str]] | None = None,
) -> None:
    """Build a minimal real .xlsx with explicit OOXML core properties."""
    wb = Workbook()
    wb.properties.creator = creator
    wb.properties.lastModifiedBy = last_modified_by
    wb.properties.modified = datetime(2026, 5, 8, tzinfo=timezone.utc)
    ws = wb.active
    ws.title = "data"
    for row in (sheet_data or [["a", "b"], [1, 2]]):
        ws.append(row)
    wb.save(path)


def _connector(watch_path: Path, **extra) -> ExcelFilesystemConnector:
    config = {"watch_path": str(watch_path)}
    config.update(extra)
    return ExcelFilesystemConnector(tenant_id=TENANT, config=config)


async def _collect(it):
    """Drain an async generator into a list — utility for short tests."""
    out = []
    async for ev in it:
        out.append(ev)
    return out


# ─── Config validation ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_missing_watch_path_raises_value_error():
    """No watch_path config → ValueError at extract_events time. Fail
    loud rather than silently scanning an empty default."""
    c = ExcelFilesystemConnector(tenant_id=TENANT, config={})
    with pytest.raises(ValueError, match="watch_path"):
        async for _ in c.extract_events():
            break


@pytest.mark.asyncio
async def test_nonexistent_watch_path_raises(tmp_path):
    """Non-existent path is misconfiguration, not a normal-state empty
    folder. Refuse to auto-create — that would mask the bug."""
    c = _connector(tmp_path / "does-not-exist")
    with pytest.raises(FileNotFoundError):
        async for _ in c.extract_events():
            break


@pytest.mark.asyncio
async def test_file_path_as_watch_path_raises(tmp_path):
    """Operator pointed watch_path at a single file by mistake — refuse."""
    leaf = tmp_path / "leaf.xlsx"
    _write_workbook(leaf)
    c = _connector(leaf)
    with pytest.raises(NotADirectoryError):
        async for _ in c.extract_events():
            break


# ─── Happy path scan ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scan_emits_one_event_per_xlsx(tmp_path):
    """Each matching file → one NormalizedEvent."""
    _write_workbook(tmp_path / "a.xlsx")
    _write_workbook(tmp_path / "b.xlsx")
    # Non-matching extension — must be filtered out by glob
    (tmp_path / "ignore.txt").write_text("not excel")

    events = await _collect(_connector(tmp_path).extract_events())

    paths = {ev.payload["path"] for ev in events}
    assert paths == {str(tmp_path / "a.xlsx"), str(tmp_path / "b.xlsx")}
    for ev in events:
        assert ev.tenant_id == TENANT
        assert ev.source == "excel_filesystem"
        assert ev.event_type == "file.modified"
        assert ev.event_id.startswith("excel_filesystem:")


@pytest.mark.asyncio
async def test_recursive_glob_descends_subdirectories(tmp_path):
    """Default pattern '**/*.xlsx' finds files in nested folders so
    the watch root can be a tenant share with department subfolders."""
    sub = tmp_path / "sales" / "2026"
    sub.mkdir(parents=True)
    _write_workbook(sub / "orders.xlsx")
    _write_workbook(tmp_path / "top.xlsx")

    events = await _collect(_connector(tmp_path).extract_events())
    assert len(events) == 2


@pytest.mark.asyncio
async def test_workbook_metadata_populates_payload_and_actor(tmp_path):
    """Creator + lastModifiedBy land on payload; lastModifiedBy is also
    promoted to NormalizedEvent.actor for Process Mining grouping."""
    f = tmp_path / "report.xlsx"
    _write_workbook(f, creator="CSM Anh Yuta", last_modified_by="Sales Lead Hằng")

    events = await _collect(_connector(tmp_path).extract_events())
    assert len(events) == 1
    ev = events[0]
    assert ev.payload["creator"] == "CSM Anh Yuta"
    assert ev.payload["last_modified_by"] == "Sales Lead Hằng"
    assert ev.actor == "Sales Lead Hằng"
    assert "data" in ev.payload["sheet_names"]


@pytest.mark.asyncio
async def test_case_id_groups_by_path_for_process_mining(tmp_path):
    """All revisions of the same file share case_id = path so the
    Process Mining sequence reconstruction can cluster them."""
    f = tmp_path / "shared.xlsx"
    _write_workbook(f)

    events = await _collect(_connector(tmp_path).extract_events())
    assert events[0].case_id == str(f)


# ─── since/until window filtering ────────────────────────────────────


@pytest.mark.asyncio
async def test_since_excludes_files_modified_before_window(tmp_path):
    """File mtime < since → skipped. The connector trusts mtime so
    callers checkpointing on previous-run-end-time don't reprocess."""
    f = tmp_path / "old.xlsx"
    _write_workbook(f)

    # Set file mtime to 2 days ago
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
    import os
    os.utime(f, (two_days_ago, two_days_ago))

    # Window starts 1 day ago — file mtime = 2 days ago is excluded
    one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    events = await _collect(
        _connector(tmp_path).extract_events(since=one_day_ago)
    )
    assert events == []


@pytest.mark.asyncio
async def test_until_excludes_files_modified_after_window(tmp_path):
    """until is exclusive: mtime >= until → skipped. Useful for
    deterministic windowed runs ('process Q1 2026 only')."""
    f = tmp_path / "future.xlsx"
    _write_workbook(f)

    # Set mtime to "now"
    import os
    now_ts = datetime.now(timezone.utc).timestamp()
    os.utime(f, (now_ts, now_ts))

    # until = 5 minutes ago → file (now) is after the window
    five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    events = await _collect(
        _connector(tmp_path).extract_events(until=five_minutes_ago)
    )
    assert events == []


@pytest.mark.asyncio
async def test_naive_since_treated_as_utc(tmp_path):
    """Passing a naive datetime works (treated as UTC) so callers
    don't have to wrap every checkpoint timestamp in tzinfo plumbing."""
    _write_workbook(tmp_path / "f.xlsx")
    naive_since = datetime(2020, 1, 1)  # well before mtime
    events = await _collect(
        _connector(tmp_path).extract_events(since=naive_since)
    )
    # File modified now is ≥ 2020-01-01 → included, no tz error
    assert len(events) == 1


# ─── Robustness ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unreadable_file_logs_and_skips_metadata(tmp_path):
    """A corrupt .xlsx (truncated bytes) must NOT break the scan — the
    connector logs + emits the event with empty workbook metadata.
    Process Mining downstream still benefits from the mtime+size signal."""
    bad = tmp_path / "corrupt.xlsx"
    bad.write_bytes(b"PK\x03\x04not a valid xlsx")

    events = await _collect(_connector(tmp_path).extract_events())

    assert len(events) == 1
    ev = events[0]
    # Metadata fields absent (workbook unreadable)
    assert "creator" not in ev.payload
    # mtime + size still present (filesystem stat succeeded)
    assert ev.payload["size_bytes"] > 0
    assert ev.payload["mtime"]


@pytest.mark.asyncio
async def test_read_workbook_false_skips_openpyxl(tmp_path):
    """Performance opt-out: huge folder scan can disable the per-file
    openpyxl open and ride on filesystem stat alone."""
    _write_workbook(tmp_path / "f.xlsx")
    events = await _collect(
        _connector(tmp_path, read_workbook=False).extract_events()
    )
    assert len(events) == 1
    ev = events[0]
    assert "creator" not in ev.payload
    assert "sheet_names" not in ev.payload
    # Stat fields still present
    assert "mtime" in ev.payload
    assert "size_bytes" in ev.payload


# ─── event_id determinism ────────────────────────────────────────────


def test_event_id_deterministic_for_same_path_and_mtime(tmp_path):
    """Same (path, mtime) → same event_id. Required for Kafka consumer-
    side dedupe; a re-scan after restart must not double-publish."""
    p = tmp_path / "x.xlsx"
    p.write_bytes(b"")
    mtime = datetime(2026, 5, 8, 12, tzinfo=timezone.utc)
    a = _derive_event_id(p, mtime)
    b = _derive_event_id(p, mtime)
    assert a == b
    assert a.startswith("excel_filesystem:")


def test_event_id_differs_when_mtime_changes(tmp_path):
    """A new revision (different mtime) yields a new event_id so the
    revised file gets re-processed — that's the whole point of the
    watcher."""
    p = tmp_path / "x.xlsx"
    p.write_bytes(b"")
    a = _derive_event_id(p, datetime(2026, 5, 8, tzinfo=timezone.utc))
    b = _derive_event_id(p, datetime(2026, 5, 9, tzinfo=timezone.utc))
    assert a != b
