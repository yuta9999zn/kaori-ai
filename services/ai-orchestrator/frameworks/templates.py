"""
F-034 Frameworks — built-in template registry.

SWOT, 6W (who/what/when/where/why/how), 2H (how + how much), and
Fishbone (Ishikawa root cause). Each entry pairs:

  * a Vietnamese system_prompt with Jinja-style placeholders for
    ``{{question}}`` and ``{{source_ref}}`` — substituted at run time
    by the service layer
  * an output_schema (JSONSchema 2020-12) passed verbatim to
    llm-gateway as the Issue #3 ``output_schema`` field, so the
    structured-output validator + one-round repair from PR #112
    enforces the shape

Why Python instead of a DB seed
================================
SWOT means SWOT. The shape is universal across industries; making it
tenant-customisable would invite well-meaning edits ("we use 'Risks'
instead of 'Threats'") that drift from the documented playbook and
break downstream renderers in the FE. F-038 reports get DB-backed
templates because monthly-summary structure varies with company
maturity; frameworks don't.

Adding a new framework
======================
1. Add a new ``FRAMEWORK_*`` dict below with the same shape (code,
   name, description, system_prompt, output_schema).
2. Register it in ``REGISTRY``.
3. Extend the CHECK constraint on ``framework_runs.framework_code`` in
   a follow-up migration (additive — never remove a code).
4. Update ``ALLOWED_CODES`` below for fast service-layer validation.
"""
from __future__ import annotations

# ─── SWOT ────────────────────────────────────────────────────────

FRAMEWORK_SWOT = {
    "code": "swot",
    "name": "SWOT Analysis",
    "description": (
        "Strengths · Weaknesses · Opportunities · Threats — đánh giá "
        "vị thế cạnh tranh dựa trên dữ liệu thực."
    ),
    "system_prompt": (
        "Bạn là chuyên gia phân tích chiến lược. Dựa trên câu hỏi của "
        "người dùng và dữ liệu tham khảo, hãy điền 4 quadrant SWOT.\n\n"
        "Câu hỏi: {{question}}\n"
        "Nguồn dữ liệu: {{source_ref}}\n\n"
        "Yêu cầu:\n"
        "(1) Mỗi quadrant CÓ TỐI THIỂU 2 ý, mỗi ý có confidence 0.0–1.0 "
        "    phản ánh độ chắc chắn dựa trên dữ liệu (không bịa).\n"
        "(2) Strengths/Weaknesses là yếu tố NỘI BỘ doanh nghiệp; "
        "    Opportunities/Threats là yếu tố BÊN NGOÀI.\n"
        "(3) summary = 1-2 câu tổng kết hành động ưu tiên.\n"
        "(4) Trả về CHỈ JSON object hợp schema — không markdown, không giải thích."
    ),
    "output_schema": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["strengths", "weaknesses", "opportunities", "threats", "summary"],
        "properties": {
            "strengths":     {"$ref": "#/$defs/quadrant"},
            "weaknesses":    {"$ref": "#/$defs/quadrant"},
            "opportunities": {"$ref": "#/$defs/quadrant"},
            "threats":       {"$ref": "#/$defs/quadrant"},
            "summary":       {"type": "string", "minLength": 1},
        },
        "$defs": {
            "quadrant": {
                "type": "object",
                "additionalProperties": False,
                "required": ["items"],
                "properties": {
                    "items": {
                        "type": "array",
                        "minItems": 2,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["text", "confidence"],
                            "properties": {
                                "text":       {"type": "string", "minLength": 1},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            },
                        },
                    },
                },
            },
        },
    },
}


# ─── 6W (who / what / when / where / why / how) ──────────────────

FRAMEWORK_6W = {
    "code": "6w",
    "name": "6W Analysis",
    "description": (
        "Who · What · When · Where · Why · How — phân tích bối cảnh "
        "đầy đủ trước khi quyết định."
    ),
    "system_prompt": (
        "Bạn là phân tích viên. Trả lời 6 câu hỏi 6W cho tình huống "
        "người dùng đưa ra.\n\n"
        "Câu hỏi: {{question}}\n"
        "Nguồn dữ liệu: {{source_ref}}\n\n"
        "Yêu cầu:\n"
        "(1) Mỗi trong 6 W trả lời cụ thể, dẫn nguồn từ dữ liệu khi có thể.\n"
        "(2) Nếu thiếu dữ liệu, ghi rõ \"chưa rõ — cần dữ liệu X\" thay vì bịa.\n"
        "(3) summary = đề xuất bước tiếp theo cụ thể (không chung chung).\n"
        "(4) Trả về CHỈ JSON object hợp schema."
    ),
    "output_schema": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["who", "what", "when", "where", "why", "how", "summary"],
        "properties": {
            "who":     {"type": "string", "minLength": 1},
            "what":    {"type": "string", "minLength": 1},
            "when":    {"type": "string", "minLength": 1},
            "where":   {"type": "string", "minLength": 1},
            "why":     {"type": "string", "minLength": 1},
            "how":     {"type": "string", "minLength": 1},
            "summary": {"type": "string", "minLength": 1},
        },
    },
}


# ─── 2H (how / how much) ─────────────────────────────────────────

FRAMEWORK_2H = {
    "code": "2h",
    "name": "2H Analysis",
    "description": (
        "How · How much — đào sâu cách thực hiện và định lượng quy mô."
    ),
    "system_prompt": (
        "Bạn là chuyên gia định lượng. Phân tích 2H cho câu hỏi:\n\n"
        "Câu hỏi: {{question}}\n"
        "Nguồn dữ liệu: {{source_ref}}\n\n"
        "Yêu cầu:\n"
        "(1) `how`: cách tiếp cận + 3-5 bước cụ thể.\n"
        "(2) `how_much`: ước lượng quy mô CÓ ĐƠN VỊ (₫, người, %, ngày...) + confidence 0–1.\n"
        "(3) Nếu không đủ dữ liệu để định lượng, đặt confidence ≤ 0.3 và ghi giả định.\n"
        "(4) summary = câu kết: nên / không nên / điều kiện cần.\n"
        "(5) Trả về CHỈ JSON object hợp schema."
    ),
    "output_schema": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["how", "how_much", "summary"],
        "properties": {
            "how": {
                "type": "object",
                "additionalProperties": False,
                "required": ["approach", "steps"],
                "properties": {
                    "approach": {"type": "string", "minLength": 1},
                    "steps": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 7,
                        "items": {"type": "string", "minLength": 1},
                    },
                },
            },
            "how_much": {
                "type": "object",
                "additionalProperties": False,
                "required": ["estimate", "unit", "confidence", "assumptions"],
                "properties": {
                    "estimate":    {"type": "string", "minLength": 1},
                    "unit":        {"type": "string", "minLength": 1},
                    "confidence":  {"type": "number", "minimum": 0, "maximum": 1},
                    "assumptions": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                },
            },
            "summary": {"type": "string", "minLength": 1},
        },
    },
}


# ─── Fishbone (Ishikawa) ─────────────────────────────────────────

FRAMEWORK_FISHBONE = {
    "code": "fishbone",
    "name": "Fishbone (Ishikawa)",
    "description": (
        "Truy nguyên gốc rễ — nhóm nguyên nhân theo 4M (Man / Method / "
        "Machine / Material) hoặc tự đề xuất."
    ),
    "system_prompt": (
        "Bạn là chuyên gia phân tích nguyên nhân gốc. Lập biểu đồ Ishikawa "
        "(Fishbone) cho vấn đề người dùng nêu.\n\n"
        "Vấn đề: {{question}}\n"
        "Nguồn dữ liệu: {{source_ref}}\n\n"
        "Yêu cầu:\n"
        "(1) `problem` = mô tả ngắn gọn vấn đề (1 câu).\n"
        "(2) `categories` 3-6 nhóm nguyên nhân (mặc định 4M: Con người / "
        "    Quy trình / Công cụ / Dữ liệu — có thể đặt tên khác nếu phù hợp domain).\n"
        "(3) Mỗi `category` có 2-5 `causes`, mỗi cause có `text` + `depth` (1=triệu chứng, "
        "    2=nguyên nhân trực tiếp, 3=gốc rễ).\n"
        "(4) `root_cause_hypothesis` = giả thuyết gốc rễ ưu tiên cần verify (1-2 câu).\n"
        "(5) Trả về CHỈ JSON object hợp schema."
    ),
    "output_schema": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["problem", "categories", "root_cause_hypothesis"],
        "properties": {
            "problem": {"type": "string", "minLength": 1},
            "categories": {
                "type": "array",
                "minItems": 3,
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "causes"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "causes": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 5,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["text", "depth"],
                                "properties": {
                                    "text":  {"type": "string", "minLength": 1},
                                    "depth": {"type": "integer", "minimum": 1, "maximum": 3},
                                },
                            },
                        },
                    },
                },
            },
            "root_cause_hypothesis": {"type": "string", "minLength": 1},
        },
    },
}


# ─── Registry ────────────────────────────────────────────────────

REGISTRY: dict[str, dict] = {
    "swot":     FRAMEWORK_SWOT,
    "6w":       FRAMEWORK_6W,
    "2h":       FRAMEWORK_2H,
    "fishbone": FRAMEWORK_FISHBONE,
}

# Authoritative service-layer validation list. Must equal the CHECK
# constraint in migration 030 line ``framework_code IN (...)``.
ALLOWED_CODES: frozenset[str] = frozenset(REGISTRY.keys())


def get_template(code: str) -> dict | None:
    """Return the registry entry for ``code`` or None when unknown.
    The router converts None to a 400 (not 404) — the framework code
    is user-supplied input, not a resource path."""
    return REGISTRY.get(code)


def extract_narrative(framework_code: str, content: dict) -> str | None:
    """Pull a one-line preview from the structured payload to use as
    the FE list-row teaser. Each framework has its own "money line";
    falls back to None when the schema is degenerate.

    Kept here next to the schemas so adding a new framework's
    narrative extraction is one PR, not a hunt across the codebase.
    """
    if not isinstance(content, dict):
        return None

    if framework_code == "swot":
        s = content.get("summary")
        if isinstance(s, str) and s.strip():
            return s.strip()[:500]
        return None

    if framework_code == "6w":
        s = content.get("summary")
        if isinstance(s, str) and s.strip():
            return s.strip()[:500]
        return None

    if framework_code == "2h":
        # "how_much.estimate" is the most actionable money line.
        hm = content.get("how_much") or {}
        est = hm.get("estimate") if isinstance(hm, dict) else None
        unit = hm.get("unit") if isinstance(hm, dict) else None
        if est and unit:
            return f"{est} {unit}".strip()[:500]
        s = content.get("summary")
        if isinstance(s, str) and s.strip():
            return s.strip()[:500]
        return None

    if framework_code == "fishbone":
        rc = content.get("root_cause_hypothesis")
        if isinstance(rc, str) and rc.strip():
            return rc.strip()[:500]
        return None

    return None
