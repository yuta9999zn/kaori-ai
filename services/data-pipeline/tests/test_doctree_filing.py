"""ADR-0039/0042 DMS — uploads must file into the Document Repository.

Original bug (2026-07-02, AABW demo rehearsal): tabular uploads with
X-Folder-ID never created a document_repository_file row. Kept as regression
tests 1-3.

ADR-0042 (2026-07-05) moved all three ingest branches onto ONE writer,
``_file_into_repository``, with Confluence semantics:
  * folder chain inheritance — nearest ancestor's template + labels union;
  * same ``name_vi`` current in folder → version STACK (v+1, supersedes);
  * identical bytes (sha256) already current → skip (K-8).
Tests 4-6 pin those behaviours.
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
TPL = "019f1f5e-7108-7173-a09e-59a586e2c111"

CSV = b"id,name\n1,a\n2,b\n"


def _folder_row() -> dict:
    return {
        "folder_id": uuid.UUID(FOLDER), "enterprise_id": uuid.UUID(ENT),
        "department_id": uuid.UUID(DEPT), "path": "mua_hang",
    }


class FakeConn:
    """Answers the ADR-0042 helper's reads: folder lookup, inheritance chain,
    same-name lookup, sha-dup check. Configurable per scenario."""

    def __init__(self, chain=None, prev=None, sha_dup=False):
        self.executed: list[tuple[str, tuple]] = []
        self.chain = chain if chain is not None else [
            {"default_template_id": None, "default_labels": [], "page_version": 1}]
        self.prev = prev
        self.sha_dup = sha_dup

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        return "INSERT 0 1"

    async def fetchrow(self, sql, *args):
        if "FROM document_folder WHERE folder_id" in sql:
            return _folder_row()
        if "FROM document_repository_file" in sql and "name_vi = $3" in sql:
            return self.prev
        if "FROM document_type_template" in sql:
            return {"default_labels": ["loai:hop-dong"]}
        return None

    async def fetchval(self, sql, *args):
        if "sha256 = $3" in sql and "SELECT 1" in sql:
            return 1 if self.sha_dup else None
        if "INSERT INTO document_repository_file" in sql:
            self.executed.append((sql, args))
            return uuid.uuid4()
        return None

    async def fetch(self, sql, *args):
        if "FROM document_folder" in sql:
            return self.chain
        return []


class FakeKafka:
    async def send_event(self, topic, payload):
        return None


def _patch_conn(monkeypatch, conn) -> None:
    @asynccontextmanager
    async def _acquire(enterprise_id):
        yield conn

    import data_pipeline.shared.db as shared_db
    monkeypatch.setattr(shared_db, "acquire_for_tenant", _acquire)


@pytest.fixture()
def fake_conn(monkeypatch):
    conn = FakeConn()
    _patch_conn(monkeypatch, conn)
    return conn


def _dms_inserts(conn: FakeConn) -> list[tuple[str, tuple]]:
    return [(s, a) for s, a in conn.executed
            if "INSERT INTO document_repository_file" in s]


# ═════════════════════════════════════════════════════════════════════
# 1. _parse_and_land files the doc when folder_id is given (regression)
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
        the repository row must land anyway, with file_id NULL."""
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
    """Dedup hit whose original run landed ZERO bronze_files rows (prose
    .txt): the bronze_files lookup returns None → helper files with
    file_id NULL."""

    async def fetchval(self, sql, *args):
        if "FROM pipeline_runs" in sql:
            return uuid.uuid4()  # K-8 dedup hit
        return await super().fetchval(sql, *args)


class TestDuplicateBranchFiles:

    @pytest.mark.asyncio
    async def test_duplicate_of_zero_sheet_run_still_files(self, monkeypatch):
        conn = DupFakeConn()
        _patch_conn(monkeypatch, conn)

        out = await ing.ingest_file(
            run_id=str(uuid.uuid4()), enterprise_id=ENT, uploaded_by=USR,
            db_pool=None, kafka_producer=FakeKafka(),
            folder_id=FOLDER,
            content="SOP prose, khong co bang.\n".encode(),
            filename="SOP-01.txt",
        )
        assert out["status"] == "duplicate"
        dms = _dms_inserts(conn)
        assert len(dms) == 1, "zero-sheet duplicate must still file (file_id NULL)"
        sql, args = dms[0]
        assert uuid.UUID(FOLDER) in args
        assert "SOP-01.txt" in args
        assert "FROM bronze_files" not in sql


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


# ═════════════════════════════════════════════════════════════════════
# 4-6. ADR-0042 Confluence semantics of _file_into_repository
# ═════════════════════════════════════════════════════════════════════


class TestConfluenceSemantics:

    @pytest.mark.asyncio
    async def test_same_name_stacks_new_version(self, monkeypatch):
        """Upload trùng tên → phiên bản mới (v+1, supersedes), metadata cũ
        carry over; bản cũ bị flip is_current + superseded_by."""
        prev_id = uuid.uuid4()
        conn = FakeConn(prev={
            "doc_id": prev_id, "version": 1, "template_id": None,
            "metadata": "{}", "labels": [], "metadata_completeness": None,
            "validated_page_version": None, "doc_date": None, "period_kind": None,
        })
        _patch_conn(monkeypatch, conn)

        await ing._file_into_repository(
            conn, folder_id=FOLDER, file_id=None, name_vi="SOP-01.txt",
            doc_type="txt", sha256="ab" * 32, uploaded_by=uuid.UUID(USR))

        inserts = _dms_inserts(conn)
        assert len(inserts) == 1
        sql, args = inserts[0]
        assert 2 in args, "new row must carry version 2"
        assert prev_id in args, "new row must supersede the old doc"
        flips = [(s, a) for s, a in conn.executed
                 if "superseded_by" in s and s.strip().startswith("UPDATE")]
        assert len(flips) == 1 and prev_id in flips[0][1]

    @pytest.mark.asyncio
    async def test_identical_bytes_skip(self, monkeypatch):
        """Cùng sha256 đã current trong folder → K-8 skip, không tạo row."""
        conn = FakeConn(sha_dup=True)
        _patch_conn(monkeypatch, conn)

        await ing._file_into_repository(
            conn, folder_id=FOLDER, file_id=None, name_vi="SOP-01.txt",
            doc_type="txt", sha256="ab" * 32, uploaded_by=None)

        assert _dms_inserts(conn) == []

    @pytest.mark.asyncio
    async def test_folder_chain_inheritance(self, monkeypatch):
        """Folder chain có template (nearest ancestor) → row mới thừa hưởng
        template_id + labels union (chain + template default_labels)."""
        conn = FakeConn(chain=[
            {"default_template_id": None,
             "default_labels": ["quy-trinh:mua-hang"], "page_version": 4},
            {"default_template_id": uuid.UUID(TPL),
             "default_labels": ["phong-ban:mua-hang"], "page_version": 7},
        ])
        _patch_conn(monkeypatch, conn)

        await ing._file_into_repository(
            conn, folder_id=FOLDER, file_id=None, name_vi="HD-2026.pdf",
            doc_type="pdf", sha256="cd" * 32, uploaded_by=None)

        inserts = _dms_inserts(conn)
        assert len(inserts) == 1
        sql, args = inserts[0]
        assert uuid.UUID(TPL) in args, "nearest ancestor template must be inherited"
        labels = next(a for a in args if isinstance(a, list))
        assert set(labels) == {"quy-trinh:mua-hang", "phong-ban:mua-hang", "loai:hop-dong"}
        assert 7 in args, "validated_page_version = provider folder's page_version"


# ═════════════════════════════════════════════════════════════════════
# 7. ADR-0039/0042 bridge — workflow-step uploads auto-file into Kho
#    (1 file 2 mặt nhìn: chứng từ theo bước + tài liệu doanh nghiệp)
# ═════════════════════════════════════════════════════════════════════

NODE = "019f2a10-0000-7000-8000-000000000001"
WF = "019f2a10-0000-7000-8000-000000000002"
WS = "019f2a10-0000-7000-8000-000000000003"
WF_NAME = "Quy trình mua hàng"


class WorkflowFakeConn(FakeConn):
    """Extends FakeConn with the workflow-branch reads: the workflow_nodes
    join, the enterprise-wide name match, and the folder get-or-create pair
    used by the auto-filing bridge."""

    def __init__(self, name_match=None, **kw):
        super().__init__(**kw)
        self.folders: dict = {}          # (parent_id, name_vi) -> row
        self.folder_inserts: list = []   # document_folder INSERTs seen
        self.name_match = name_match     # folder trùng tên workflow (toàn Kho)

    async def fetchrow(self, sql, *args):
        if "FROM workflow_nodes n" in sql:
            return {
                "node_id": uuid.UUID(NODE), "workflow_id": uuid.UUID(WF),
                "department_id": uuid.UUID(DEPT), "branch_id": uuid.UUID(BR),
                "workspace_id": uuid.UUID(WS),
                "expected_mapping_template_id": None,
                "title": "Bước 9 — Nộp báo cáo",
                "required_document_types": [],
                "wf_name": WF_NAME,
            }
        if "FROM document_folder" in sql and "name_vi = $2" in sql:
            return self.name_match  # match trùng tên toàn enterprise
        if "FROM document_folder" in sql and "name_vi = $3" in sql:
            return self.folders.get((args[1], args[2]))
        if "INSERT INTO document_folder" in sql:
            self.folder_inserts.append((sql, args))
            row = {"folder_id": uuid.uuid4(), "path": args[3]}
            self.folders[(args[2], args[4])] = row
            return row
        return await super().fetchrow(sql, *args)


class BrokenFolderConn(WorkflowFakeConn):
    """Folder get-or-create blows up — auto-filing must fail-soft."""

    async def fetchrow(self, sql, *args):
        if "FROM document_folder" in sql and "name_vi = $3" in sql:
            raise RuntimeError("db hiccup")
        return await super().fetchrow(sql, *args)


def _patch_org(monkeypatch) -> None:
    import data_pipeline.shared.org_resolver as org_resolver

    async def _org(conn, enterprise_id, **kw):
        return {"branch_id": BR, "department_id": DEPT, "source_id": SRC}

    async def _tpl(conn, enterprise_id, source_id, fname):
        return None

    monkeypatch.setattr(org_resolver, "resolve_org_attribution", _org)
    monkeypatch.setattr(org_resolver, "match_mapping_template", _tpl)


def _patch_land(monkeypatch) -> dict:
    seen: dict = {}

    async def _fake_land(*args, **kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(ing, "_parse_and_land", _fake_land)
    return seen


class TestWorkflowAutoFiling:

    @pytest.mark.asyncio
    async def test_workflow_upload_autofiles_into_kho(self, monkeypatch):
        """Nộp file ở bước workflow (không X-Folder-ID) → tự resolve folder
        Kho 'Hồ sơ quy trình/<tên quy trình>' và forward folder_id xuống
        nhánh landing để _file_into_repository ghi row DMS."""
        conn = WorkflowFakeConn()
        _patch_conn(monkeypatch, conn)
        _patch_org(monkeypatch)
        seen = _patch_land(monkeypatch)

        await ing.ingest_file(
            run_id=str(uuid.uuid4()), enterprise_id=ENT, uploaded_by=USR,
            db_pool=None, kafka_producer=FakeKafka(),
            workflow_step_id=NODE, content=CSV, filename="bao_cao_t6.csv")
        await asyncio.sleep(0)

        assert seen.get("folder_id"), (
            "workflow upload must auto-resolve a Kho folder and forward it")
        assert len(conn.folder_inserts) == 2, "root + workflow folder created"
        _, root_args = conn.folder_inserts[0]
        assert "Hồ sơ quy trình" in root_args
        _, wf_args = conn.folder_inserts[1]
        assert WF_NAME in wf_args
        assert uuid.UUID(DEPT) in wf_args, "workflow folder carries the card's dept"

    @pytest.mark.asyncio
    async def test_second_upload_reuses_folders(self, monkeypatch):
        """Folder đã tồn tại → không INSERT thêm, vẫn resolve được id."""
        conn = WorkflowFakeConn()
        _patch_conn(monkeypatch, conn)
        _patch_org(monkeypatch)
        seen = _patch_land(monkeypatch)

        for fname in ("bao_cao_t6.csv", "bao_cao_t7.csv"):
            await ing.ingest_file(
                run_id=str(uuid.uuid4()), enterprise_id=ENT, uploaded_by=USR,
                db_pool=None, kafka_producer=FakeKafka(),
                workflow_step_id=NODE, content=CSV + fname.encode(),
                filename=fname)
            await asyncio.sleep(0)

        assert len(conn.folder_inserts) == 2, "folders created once, then reused"
        assert seen.get("folder_id")

    @pytest.mark.asyncio
    async def test_explicit_folder_id_wins(self, monkeypatch):
        """Caller đã chỉ định X-Folder-ID → bridge không ghi đè."""
        conn = WorkflowFakeConn()
        _patch_conn(monkeypatch, conn)
        _patch_org(monkeypatch)
        seen = _patch_land(monkeypatch)

        await ing.ingest_file(
            run_id=str(uuid.uuid4()), enterprise_id=ENT, uploaded_by=USR,
            db_pool=None, kafka_producer=FakeKafka(),
            workflow_step_id=NODE, folder_id=FOLDER,
            content=CSV, filename="bao_cao_t6.csv")
        await asyncio.sleep(0)

        assert seen.get("folder_id") == FOLDER
        assert conn.folder_inserts == []

    @pytest.mark.asyncio
    async def test_existing_folder_named_after_workflow_is_reused(self, monkeypatch):
        """Kho đã có folder TRÙNG TÊN workflow (user tạo tay theo nghiệp vụ,
        ở bất kỳ đâu trong cây) → lưu thẳng vào đó, KHÔNG tạo folder mới."""
        existing = uuid.uuid4()
        conn = WorkflowFakeConn(name_match={"folder_id": existing, "path": "kinh_doanh/thu_mua"})
        _patch_conn(monkeypatch, conn)
        _patch_org(monkeypatch)
        seen = _patch_land(monkeypatch)

        await ing.ingest_file(
            run_id=str(uuid.uuid4()), enterprise_id=ENT, uploaded_by=USR,
            db_pool=None, kafka_producer=FakeKafka(),
            workflow_step_id=NODE, content=CSV, filename="bao_cao_t6.csv")
        await asyncio.sleep(0)

        assert seen.get("folder_id") == str(existing)
        assert conn.folder_inserts == [], "folder trùng tên đã có — không được tạo mới"

    @pytest.mark.asyncio
    async def test_repo_filing_skip_suppresses_autofiling(self, monkeypatch):
        """User chọn 'Chỉ tải lên' trên dialog nộp file → header
        X-Repo-Filing: skip → không auto-resolve folder Kho."""
        conn = WorkflowFakeConn()
        _patch_conn(monkeypatch, conn)
        _patch_org(monkeypatch)
        seen = _patch_land(monkeypatch)

        await ing.ingest_file(
            run_id=str(uuid.uuid4()), enterprise_id=ENT, uploaded_by=USR,
            db_pool=None, kafka_producer=FakeKafka(),
            workflow_step_id=NODE, repo_filing="skip",
            content=CSV, filename="bao_cao_t6.csv")
        await asyncio.sleep(0)

        assert seen.get("folder_id") is None
        assert conn.folder_inserts == []

    @pytest.mark.asyncio
    async def test_folder_failure_does_not_block_upload(self, monkeypatch):
        """Lỗi khi ensure folder → upload vẫn thành công, folder_id None
        (fail-soft: auto-filing là phụ, ingest là chính)."""
        conn = BrokenFolderConn()
        _patch_conn(monkeypatch, conn)
        _patch_org(monkeypatch)
        seen = _patch_land(monkeypatch)

        out = await ing.ingest_file(
            run_id=str(uuid.uuid4()), enterprise_id=ENT, uploaded_by=USR,
            db_pool=None, kafka_producer=FakeKafka(),
            workflow_step_id=NODE, content=CSV, filename="bao_cao_t6.csv")
        await asyncio.sleep(0)

        assert out["status"] == "uploading"
        assert seen.get("folder_id") is None
