"""ADR-0039 DMS — tabular uploads must file into the Document Repository too.

Bug (2026-07-02, found in AABW demo rehearsal): POST /upload with X-Folder-ID
for a TABULAR extension (.txt/.csv/.xlsx — SUPPORTED_EXTENSIONS) returned 200
but never created a document_repository_file row. The sync handler routed the
file into the tabular branch, which spawns _parse_and_land WITHOUT folder_id —
so the caller's explicit "file this into the repo" intent was silently dropped
(only the unstructured + duplicate branches filed). A CSV price list or TXT SOP
is still an enterprise document; filing must not depend on the parse branch.
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

import pytest

from data_pipeline.data_plane.bronze import ingestor as ing


ENT = "3d1c1a53-f924-41fa-a4ce-defade00e898"
USR = "4ebbb853-8aaf-4f0c-9e86-e5180337ee63"
DEPT = "5350969f-1abe-4e7b-8dc5-f68f3297c551"
BR = "9053a648-5349-4d68-92e6-3bd977603d82"
SRC = "307004c8-4876-4c9f-ad4e-d25d3fdf3021"
FOLDER = "019f1f5e-7108-7173-a09e-59a586e2c59f"

CSV = b"id,name\n1,a\n2,b\n"


class FakeConn:
    def __init__(self):
        self.executed: list[tuple[str, tuple]] = []

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        return "INSERT 0 1"

    async def fetchrow(self, sql, *args):
        return None

    async def fetchval(self, sql, *args):
        return None

    async def fetch(self, sql, *args):
        return []


class FakeKafka:
    async def send_event(self, topic, payload):
        return None


@pytest.fixture()
def fake_conn(monkeypatch):
    conn = FakeConn()

    @asynccontextmanager
    async def _acquire(enterprise_id):
        yield conn

    import data_pipeline.shared.db as shared_db
    monkeypatch.setattr(shared_db, "acquire_for_tenant", _acquire)
    return conn


def _dms_inserts(conn: FakeConn) -> list[tuple[str, tuple]]:
    return [(s, a) for s, a in conn.executed
            if "document_repository_file" in s]


# ═════════════════════════════════════════════════════════════════════
# 1. _parse_and_land files the doc when folder_id is given
# ═════════════════════════════════════════════════════════════════════


class TestParseAndLandFiles:

    @pytest.mark.asyncio
    async def test_folder_id_creates_repository_row(self, fake_conn):
        await ing._parse_and_land(
            CSV, ".csv", str(uuid.uuid4()), ENT, "bang_gia.csv",
            db_pool=None, kafka_producer=FakeKafka(),
            branch_id=BR, department_id=DEPT, source_id=SRC,
            uploaded_by=USR, folder_id=FOLDER,
        )
        inserts = _dms_inserts(fake_conn)
        assert len(inserts) == 1, (
            "tabular upload with folder_id must register exactly one "
            "document_repository_file row")
        sql, args = inserts[0]
        assert uuid.UUID(FOLDER) in args
        assert "bang_gia.csv" in args

    @pytest.mark.asyncio
    async def test_multi_sheet_files_once(self, fake_conn):
        """A workbook = many bronze_files rows but ONE repository document."""
        # csv parses to a single sheet; guard the invariant explicitly anyway
        await ing._parse_and_land(
            CSV, ".csv", str(uuid.uuid4()), ENT, "bang_gia.csv",
            db_pool=None, kafka_producer=FakeKafka(),
            branch_id=BR, department_id=DEPT, source_id=SRC,
            uploaded_by=USR, folder_id=FOLDER,
        )
        assert len(_dms_inserts(fake_conn)) == 1

    @pytest.mark.asyncio
    async def test_prose_txt_zero_sheets_still_files(self, fake_conn):
        """A prose .txt (SOP, quy định…) parses to ZERO tabular sheets —
        the repository row must land anyway, with file_id NULL; download
        serves the bytes from the sha256-keyed blob store."""
        prose = "SOP-01 — QUY TRÌNH THU MUA\nBước 1: Báo giá.\n".encode()
        await ing._parse_and_land(
            prose, ".txt", str(uuid.uuid4()), ENT, "SOP-01.txt",
            db_pool=None, kafka_producer=FakeKafka(),
            branch_id=BR, department_id=DEPT, source_id=SRC,
            uploaded_by=USR, folder_id=FOLDER,
        )
        inserts = _dms_inserts(fake_conn)
        assert len(inserts) == 1
        sql, args = inserts[0]
        assert uuid.UUID(FOLDER) in args
        assert "SOP-01.txt" in args

    @pytest.mark.asyncio
    async def test_no_folder_id_no_repository_row(self, fake_conn):
        await ing._parse_and_land(
            CSV, ".csv", str(uuid.uuid4()), ENT, "bang_gia.csv",
            db_pool=None, kafka_producer=FakeKafka(),
            branch_id=BR, department_id=DEPT, source_id=SRC,
            uploaded_by=USR,
        )
        assert _dms_inserts(fake_conn) == []


# ═════════════════════════════════════════════════════════════════════
# 2. K-8 duplicate branch — zero-sheet original run must still file
# ═════════════════════════════════════════════════════════════════════


class DupFakeConn(FakeConn):
    """Simulates the dedup hit whose original run landed ZERO bronze_files
    rows (prose .txt): the INSERT..SELECT FROM bronze_files inserts nothing."""

    async def fetchval(self, sql, *args):
        if "FROM pipeline_runs" in sql:
            return uuid.uuid4()  # K-8 dedup hit
        return None

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        if "document_repository_file" in sql and "FROM bronze_files" in sql:
            return "INSERT 0 0"  # zero-sheet original run → nothing selected
        return "INSERT 0 1"


class TestDuplicateBranchFiles:

    @pytest.mark.asyncio
    async def test_duplicate_of_zero_sheet_run_still_files(self, monkeypatch):
        conn = DupFakeConn()

        @asynccontextmanager
        async def _acquire(enterprise_id):
            yield conn

        import data_pipeline.shared.db as shared_db
        monkeypatch.setattr(shared_db, "acquire_for_tenant", _acquire)

        out = await ing.ingest_file(
            run_id=str(uuid.uuid4()), enterprise_id=ENT, uploaded_by=USR,
            db_pool=None, kafka_producer=FakeKafka(),
            folder_id=FOLDER,
            content="SOP prose, khong co bang.\n".encode(),
            filename="SOP-01.txt",
        )
        assert out["status"] == "duplicate"
        dms = _dms_inserts(conn)
        # 1st: the INSERT..SELECT that found no bronze rows; 2nd: fallback
        assert len(dms) == 2, "zero-sheet duplicate must fall back to a plain insert"
        fallback_sql, fallback_args = dms[-1]
        assert "FROM bronze_files" not in fallback_sql
        assert uuid.UUID(FOLDER) in fallback_args
        assert "SOP-01.txt" in fallback_args


# ═════════════════════════════════════════════════════════════════════
# 3. ingest_file passes folder_id through to the tabular spawn
# ═════════════════════════════════════════════════════════════════════


class TestIngestFileWiring:

    @pytest.mark.asyncio
    async def test_tabular_spawn_receives_folder_id(self, fake_conn, monkeypatch):
        import data_pipeline.shared.org_resolver as org_resolver

        async def _org(conn, enterprise_id, **kw):
            return {"branch_id": BR, "department_id": DEPT, "source_id": SRC}

        async def _tpl(conn, enterprise_id, source_id, fname):
            return None

        monkeypatch.setattr(org_resolver, "resolve_org_attribution", _org)
        monkeypatch.setattr(org_resolver, "match_mapping_template", _tpl)

        seen: dict = {}

        async def _fake_land(*args, **kwargs):
            seen.update(kwargs)

        monkeypatch.setattr(ing, "_parse_and_land", _fake_land)

        await ing.ingest_file(
            run_id=str(uuid.uuid4()), enterprise_id=ENT, uploaded_by=USR,
            db_pool=None, kafka_producer=FakeKafka(),
            folder_id=FOLDER, content=CSV, filename="bang_gia.csv",
        )
        await asyncio.sleep(0)  # let the created task bind/record
        assert seen.get("folder_id") == FOLDER, (
            "ingest_file tabular branch must forward folder_id to "
            "_parse_and_land so the DMS row lands")
