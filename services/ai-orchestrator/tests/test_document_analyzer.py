"""Tests for the document analyzer (Option 1) — deterministic parts.

The risk scan + the no-LLM path are pure/offline; the Qwen summary path is
exercised only via the live stack (covered by the smoke check, not here).
"""
from __future__ import annotations

import pytest

from ai_orchestrator.reasoning import document_analyzer as da


def test_scan_risks_flags_high_keywords():
    text = "Hợp đồng có điều khoản trách nhiệm và phạt vi phạm, giải quyết bằng trọng tài."
    risks = da.scan_risks(text)
    kws = {r["keyword"] for r in risks}
    assert "trách nhiệm" in kws and "phạt vi phạm" in kws and "trọng tài" in kws
    assert all(r["severity"] in ("high", "medium") for r in risks)
    assert any(r["severity"] == "high" for r in risks)


def test_scan_risks_clean_text_no_flags():
    assert da.scan_risks("Hóa đơn bán hàng thông thường, số lượng 10 cái.") == []


def test_scan_risks_dedupes_repeated_keyword():
    text = "trọng tài ... trọng tài ... trọng tài"
    risks = [r for r in da.scan_risks(text) if r["keyword"] == "trọng tài"]
    assert len(risks) == 1


@pytest.mark.asyncio
async def test_analyze_without_llm_returns_risks_only():
    text = "Điều khoản bồi thường và chấm dứt hợp đồng."
    res = await da.analyze_document(text=text, filename="hd.pdf",
                                    enterprise_id="e", with_llm=False)
    assert res.model == "rules-only"
    assert {r["keyword"] for r in res.risks} >= {"bồi thường", "chấm dứt"}
    assert res.key_fields == []


@pytest.mark.asyncio
async def test_analyze_empty_text():
    res = await da.analyze_document(text="", filename="x.pdf", enterprise_id="e")
    assert res.risks == [] and "Không có nội dung" in res.summary
