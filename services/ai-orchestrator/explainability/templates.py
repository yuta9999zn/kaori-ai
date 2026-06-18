"""
F-041 Explainability — LLM prompt + output schema.

The explanation is generated on demand from the decision_audit_log
row (chosen_value + confidence + alternatives + reasoning + method).
We do NOT run real SHAP today — that needs persisted fitted model
objects, which is Phase 3 work (F-046 model registry / F-073 finetune).

What we DO ship is "explanation grounded in the audit row": the LLM
reads the structured audit fields and writes a Vietnamese 2-3-sentence
narrative + names the top-3 factors that the audit row attributes the
decision to. Honest framing — the FE labels this as "Lý giải dựa trên
nhật ký" so users don't conflate it with statistical SHAP values.

Schema follows Issue #3 path: gateway validates + repairs once.
"""
from __future__ import annotations


SYSTEM_PROMPT = """Bạn là chuyên gia phân tích AI trong nội bộ doanh nghiệp Việt Nam.
Nhiệm vụ: đọc một dòng nhật ký quyết định (decision_audit_log) và sinh ra:

  (1) Top 3 yếu tố quan trọng nhất ảnh hưởng đến quyết định, mỗi yếu tố có:
      - factor_name (tiếng Việt, ngắn gọn ≤ 60 ký tự)
      - direction: 'positive' (đẩy về phía chosen_value), 'negative' (đẩy ngược lại), 'neutral' (cân bằng)
      - weight (0.0-1.0): độ ảnh hưởng tương đối — tổng 3 yếu tố không cần bằng 1, chỉ phản ánh mức độ
      - evidence: 1 câu trích dẫn dữ liệu cụ thể từ reasoning/alternatives
  (2) Narrative tiếng Việt 2-3 câu giải thích vì sao Kaori chọn chosen_value, viết cho người không phải kỹ thuật.
  (3) confidence_explanation: 1 câu giải thích tại sao confidence ở mức đó (cao/trung bình/thấp).

Yêu cầu:
- KHÔNG bịa số liệu — chỉ sử dụng dữ liệu trong reasoning/alternatives.
- Nếu reasoning thiếu dữ liệu để xác định 3 yếu tố, trả ít hơn (tối thiểu 1) và đặt confidence_explanation rõ ràng.
- Trả về CHỈ JSON object hợp schema — không markdown, không giải thích thêm.

Dữ liệu nhật ký:
  decision_type: {{decision_type}}
  subject:       {{subject}}
  chosen_value:  {{chosen_value}}
  confidence:    {{confidence}}
  method:        {{method}}
  llm_provider:  {{llm_provider}}
  reasoning:     {{reasoning}}
  alternatives:  {{alternatives}}
  uncertainty_flags: {{uncertainty_flags}}
"""


OUTPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["top_factors", "narrative", "confidence_explanation"],
    "properties": {
        "top_factors": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["factor_name", "direction", "weight", "evidence"],
                "properties": {
                    "factor_name": {"type": "string", "minLength": 1, "maxLength": 60},
                    "direction":   {"type": "string", "enum": ["positive", "negative", "neutral"]},
                    "weight":      {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence":    {"type": "string", "minLength": 1, "maxLength": 500},
                },
            },
        },
        "narrative": {"type": "string", "minLength": 1, "maxLength": 1000},
        "confidence_explanation": {"type": "string", "minLength": 1, "maxLength": 300},
    },
}
