"""
Framework Decision Router — K-10: 1 question = 1 framework, never parallel.
5Why / SWOT / Fishbone / 5W1H / MoM — adapted from Kise AI FRAMEWORK_DECISION_TREE.md
"""
import re
from typing import Literal

FrameworkType = Literal["5why", "fishbone", "swot", "5w1h", "mom_compare"]

_KEYWORD_MAP: dict[FrameworkType, list[str]] = {
    "5why": ["tại sao", "why", "nguyên nhân", "root cause", "gốc rễ", "lý do"],
    "fishbone": ["nguyên nhân nào", "yếu tố nào", "factors", "những gì gây ra", "vấn đề"],
    "swot": ["swot", "điểm mạnh", "điểm yếu", "cơ hội", "thách thức",
             "strength", "weakness", "opportunity", "threat", "chiến lược"],
    "5w1h": ["ai", "cái gì", "ở đâu", "khi nào", "how", "who", "what", "where", "when", "how"],
    "mom_compare": ["so sánh", "tháng trước", "tuần trước", "mom", "wow", "compare", "thay đổi"],
}


def route_framework(question: str) -> FrameworkType:
    """
    Deterministic framework selection from question text.
    K-10: Returns exactly 1 framework. Never "apply all".

    Algorithm: **longest-keyword wins**. Tie-break order is
    ``5why > fishbone > swot > mom_compare > 5w1h``.

    Bug history: the previous implementation used a strict iteration order
    and returned on the first match. That meant the short keyword
    ``"nguyên nhân"`` (5why) always shadowed the more specific
    ``"nguyên nhân nào"`` (fishbone), so questions like "Nguyên nhân nào
    gây ra tình trạng này?" routed to 5why instead of fishbone. Tests
    test_fishbone_causes and test_priority_fishbone_over_swot caught it.

    Longest-match resolves the ambiguity without bespoke rules: the more
    specific phrase always beats a substring. Tie-break preserves the
    documented priority order.
    """
    q = question.lower()
    best_framework: FrameworkType = "5w1h"
    best_keyword_len = 0

    # Iteration order is the documented priority — used for tie-breaking when
    # two keywords have the same length.
    for framework in ("5why", "fishbone", "swot", "mom_compare", "5w1h"):
        for keyword in _KEYWORD_MAP[framework]:
            if keyword in q and len(keyword) > best_keyword_len:
                best_framework = framework
                best_keyword_len = len(keyword)

    return best_framework


FRAMEWORK_PROMPTS: dict[FrameworkType, str] = {
    "5why": """Phân tích vấn đề sau đây theo phương pháp 5 Whys:

Vấn đề: {question}
Dữ liệu liên quan: {data_context}

Hãy tìm nguyên nhân gốc rễ bằng cách hỏi "Tại sao?" 5 lần liên tiếp.
Format: Why 1 → Why 2 → Why 3 → Why 4 → Why 5 (Root Cause)
Đề xuất giải pháp cho nguyên nhân gốc rễ.
Trả lời bằng tiếng Việt, ngắn gọn và thực tế.""",

    "fishbone": """Phân tích vấn đề sau theo biểu đồ Fishbone (Ishikawa):

Vấn đề: {question}
Dữ liệu liên quan: {data_context}

Phân tích nguyên nhân theo 6 nhánh: Con người / Quy trình / Phương pháp / Vật liệu / Đo lường / Môi trường.
Mỗi nhánh: ≥2 nguyên nhân cụ thể từ dữ liệu.
Trả lời bằng tiếng Việt.""",

    "swot": """Phân tích SWOT cho tình huống sau:

Câu hỏi: {question}
Dữ liệu liên quan: {data_context}

Format:
## Điểm mạnh (Strengths): ≥3 điểm từ dữ liệu
## Điểm yếu (Weaknesses): ≥3 điểm từ dữ liệu
## Cơ hội (Opportunities): ≥3 điểm
## Thách thức (Threats): ≥3 điểm
Kết luận chiến lược 1-2 câu.
Trả lời bằng tiếng Việt.""",

    "5w1h": """Phân tích tình huống sau theo khung 5W1H:

Câu hỏi: {question}
Dữ liệu liên quan: {data_context}

Who (Ai), What (Cái gì), Where (Ở đâu), When (Khi nào), Why (Tại sao), How (Như thế nào).
Trả lời bằng tiếng Việt.""",

    "mom_compare": """So sánh kỳ này với kỳ trước:

Câu hỏi: {question}
Dữ liệu so sánh: {data_context}

Bảng so sánh chỉ số chính với % thay đổi.
Nhận xét xu hướng và đề xuất hành động.
Trả lời bằng tiếng Việt.""",
}
