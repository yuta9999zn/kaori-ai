"""
Prompt templates for T-Cube transformation.

Each prompt asks the LLM to compress raw thinking traces into ONE of the
three retrieval forms. Paper §3.2 used Gemini-2-Flash-Lite for distillation;
Kaori uses Qwen 2.5 14B local (K-4 default).

All prompts return Markdown-free plain text bounded by length so the
output is embedding-ready (BGE-M3 has 8192 token limit; we target ~500
tokens per form).
"""
from __future__ import annotations

PROMPT_STRUCT = """\
Bạn là chuyên gia tóm tắt quy trình. Phía dưới là chuỗi suy nghĩ THÔ của \
một AI giải bài toán doanh nghiệp. Nhiệm vụ của bạn: chuẩn hóa thành \
quy trình 5 BƯỚC sạch, mỗi bước 1 câu.

QUY TẮC:
- Đánh số bước 1-5 (không hơn không kém).
- Mỗi bước = 1 câu ngắn, KHÔNG giải thích dài.
- Tiếng Việt nếu input tiếng Việt, English nếu input English.
- BỎ HẾT mô tả cảm xúc, sự do dự, dấu chấm hỏi.
- Output CHỈ chứa 5 dòng đánh số, không header, không lời mở.

BÀI TOÁN:
{problem_context}

CHUỖI SUY NGHĨ THÔ:
{raw_trace}

5 BƯỚC SẠCH:
"""

PROMPT_SEMANTIC = """\
Bạn là chuyên gia chưng cất kiến thức. Phía dưới là chuỗi suy nghĩ \
THÔ của một AI giải bài toán doanh nghiệp. Nhiệm vụ: rút ra INSIGHT \
CỐT LÕI (kiến thức tổng quát có thể áp dụng cho bài toán tương tự khác).

QUY TẮC:
- Output là 2-3 câu DUY NHẤT.
- KHÔNG nhắc đến chi tiết cụ thể của bài này (số liệu, tên khách, ngày).
- TẬP TRUNG vào pattern/quy luật/heuristic chung.
- Phải có dạng "Khi [tình huống], làm [hành động] để [đạt mục tiêu]".

BÀI TOÁN:
{problem_context}

CHUỖI SUY NGHĨ THÔ:
{raw_trace}

INSIGHT CỐT LÕI (2-3 câu):
"""

PROMPT_REFLECT = """\
Bạn là chuyên gia phản tư (post-mortem). Phía dưới là chuỗi suy nghĩ \
THÔ của một AI giải bài toán doanh nghiệp. Nhiệm vụ: liệt kê 3-5 BẪY \
hoặc LỖI thường gặp + CÁCH TRÁNH.

QUY TẮC:
- Output là 3-5 mục đánh dấu "-" dòng đầu.
- Mỗi mục có dạng "- BẪY: ... | TRÁNH: ...".
- Tránh nói chung chung. Bẫy phải CỤ THỂ (kiểu "quên check NULL trong \
JOIN", không phải "cần cẩn thận").
- Nếu chuỗi không có bẫy rõ → output "- Không có bẫy nào nổi bật. \
Theo dõi step X cẩn thận nếu chạy lại."

BÀI TOÁN:
{problem_context}

CHUỖI SUY NGHĨ THÔ:
{raw_trace}

BẪY + CÁCH TRÁNH (3-5 mục):
"""


def render(template: str, *, problem_context: str, raw_trace: str) -> str:
    """Render a prompt with truncation guard — keeps raw_trace under
    8000 chars (BGE-M3 8192 token ≈ 30K chars VN; we cap upstream to
    be safe with prompt envelope)."""
    if len(raw_trace) > 8000:
        raw_trace = raw_trace[:8000] + "\n[... truncated ...]"
    if len(problem_context) > 1000:
        problem_context = problem_context[:1000] + "\n[... truncated ...]"
    return template.format(problem_context=problem_context, raw_trace=raw_trace)


# ─── Fact extraction (mem0-inspired, T-Cube extension) ──────────────


PROMPT_EXTRACT_FACTS = """\
Bạn là chuyên gia trích xuất sự kiện (facts). Phía dưới là một đoạn \
văn bản (chat turn, document chunk, hoặc quyết định) trong ngữ cảnh \
doanh nghiệp. Nhiệm vụ: trích 0-5 SỰ KIỆN có thể tái sử dụng cho các \
truy vấn về sau.

QUY TẮC:
- Mỗi sự kiện = 1 JSON object trong array, dạng:
  {{"subject": "...", "predicate": "...", "object": "...", "confidence": 0.0-1.0}}
- subject: tên thực thể (khách hàng, sản phẩm, nhân viên, dự án).
- predicate: quan hệ ngắn (vd: "thích", "phụ trách", "có doanh thu", "không hài lòng vì").
- object: giá trị / thực thể khác / mô tả.
- confidence: 1.0 nếu rõ trong text; 0.5 nếu suy luận; <0.5 thì BỎ.
- KHÔNG trích sự kiện về Kaori AI, hệ thống, hoặc nội dung mơ hồ.
- KHÔNG trích PII trực tiếp (email/phone/CCCD). Nếu thấy → bỏ hoặc mask.
- Output CHỈ là JSON array. Nếu không có sự kiện đáng giá → `[]`.

NGỮ CẢNH:
{problem_context}

VĂN BẢN:
{raw_trace}

JSON ARRAY:
"""
