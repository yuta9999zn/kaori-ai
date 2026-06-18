"""
Phase 2.5 — OCR client wrapping POST /v1/ocr in llm-gateway.

Why this lives in `silver/` (not bronze/)
-----------------------------------------
Same reason `docsage_extract.py` lives here: OCR is a parsed-and-typed
view of Bronze bytes. Bronze keeps the raw image; Silver carries the
queryable text (`docsage_text` populated with the OCR output, identical
contract to native-text PDFs).

K-rules
-------
K-3: All LLM dispatch via llm-gateway (em do NOT call Ollama directly
     from data-pipeline).
K-4: OCR is local-only per llm-gateway's enforced invariant. Em pass
     no consent_external flag — endpoint refuses it anyway.
K-5: Image bytes contain PII that em can't strip pre-call. They never
     leave the Kaori boundary because llm-gateway routes to local Qwen
     2.5-VL only. K-4 + K-5 combined: OCR is safe-by-default.

Side_effect_class
-----------------
write_idempotent w.r.t. (image bytes, model version) — same image +
same Qwen2.5-VL revision always returns the same text up to sampler
noise. We pin temperature=0 in providers.ocr_image, so retries are
deterministic at the gateway layer too.

Caller pattern
--------------
The ingestor calls `ocr_image_to_text(content, ent_id, mime)` AFTER
`docsage_extract` returns `status='unsupported_today'`. On OCR success
the caller upgrades the file row to `silver_complete` + populates
`docsage_text` with the result. On OCR failure (network, model not
pulled, gateway down) the file stays in `unstructured_pending` — the
existing manual queue handles it.
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

log = structlog.get_logger()


LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8095")

# OCR is heavier than embed — 180s upstream timeout; em add a small
# buffer for network jitter.
OCR_CLIENT_TIMEOUT_S = float(os.getenv("OCR_CLIENT_TIMEOUT_S", "200"))

# Hard cap on input image size — Pydantic in models.OcrRequest caps at
# ~15 MB base64; raw bytes around 11 MB. Larger files are rejected
# before em even reach llm-gateway so the call doesn't 413 over the wire.
MAX_OCR_BYTES = 11 * 1024 * 1024


# Images Qwen2.5-VL accepts. JPEG / PNG / WebP are the safe set across
# Ollama vision models; GIF / BMP / TIFF coverage varies.
SUPPORTED_IMAGE_MIMES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp",
}

SUPPORTED_IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp",
}


@dataclass(frozen=True)
class OcrResult:
    """Outcome of an OCR attempt. Mirrors ExtractResult.status enum so
    the ingestor can stitch into the same downgrade ladder:

      'ok'                — text extracted, char_count > 0
      'empty_image'       — model returned empty string (blank scan)
      'unsupported_today' — image type Qwen2.5-VL can't handle yet
      'failed'            — gateway / network error; caller keeps file
                            in unstructured_pending for retry
    """
    text:          str
    status:        str
    char_count:    int = 0
    model_used:    str = ""
    latency_ms:    int = 0
    error_message: Optional[str] = None


def is_ocr_candidate(*, mime_type: str, ext: str) -> bool:
    """Cheap pre-check before calling the gateway. Caller uses this to
    decide whether to try OCR or short-circuit to unsupported_today."""
    mt = (mime_type or "").lower()
    e = (ext or "").lower()
    if not e.startswith(".") and e:
        e = "." + e
    return mt in SUPPORTED_IMAGE_MIMES or e in SUPPORTED_IMAGE_EXTS


async def ocr_image_to_text(
    *,
    content:       bytes,
    enterprise_id: str,
    mime_type:     str = "",
    ext:           str = "",
    prompt:        str = "",
    max_tokens:    int = 2000,
) -> OcrResult:
    """Thin async wrapper around POST /v1/ocr.

    Pre-flight:
      - Empty content → 'empty_image' immediately (don't burn a gateway call)
      - Oversize (> MAX_OCR_BYTES) → 'unsupported_today' with hint
      - Non-image mime/ext → 'unsupported_today'
    """
    if not content:
        return OcrResult(text="", status="empty_image",
                          error_message="Ảnh rỗng — không có gì để OCR.")

    if len(content) > MAX_OCR_BYTES:
        return OcrResult(
            text="", status="unsupported_today",
            error_message=(
                f"Ảnh {len(content) // 1024 // 1024} MB vượt giới hạn "
                f"{MAX_OCR_BYTES // 1024 // 1024} MB — giảm độ phân giải "
                "trước khi upload."
            ),
        )

    if not is_ocr_candidate(mime_type=mime_type, ext=ext):
        return OcrResult(
            text="", status="unsupported_today",
            error_message=(
                f"Định dạng ảnh chưa hỗ trợ OCR (mime={mime_type!r} "
                f"ext={ext!r}). Hỗ trợ: JPG / PNG / WebP."
            ),
        )

    image_b64 = base64.b64encode(content).decode("ascii")

    body = {
        "image_b64":     image_b64,
        "enterprise_id": enterprise_id,
        "prompt":        prompt,
        "max_tokens":    max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=OCR_CLIENT_TIMEOUT_S) as client:
            resp = await client.post(
                f"{LLM_GATEWAY_URL}/v1/ocr",
                json=body,
            )
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        log.warning("ocr_client.gateway_call_failed",
                    enterprise_id=enterprise_id, error=str(exc))
        return OcrResult(
            text="", status="failed",
            error_message=f"OCR upstream lỗi: {type(exc).__name__}",
        )
    except Exception as exc:   # noqa: BLE001
        log.warning("ocr_client.unexpected",
                    enterprise_id=enterprise_id, error=str(exc))
        return OcrResult(
            text="", status="failed",
            error_message=f"OCR ngoại lệ: {type(exc).__name__}",
        )

    text = str(payload.get("text") or "")
    char_count = int(payload.get("char_count", len(text)))
    model_used = str(payload.get("model_used") or "")
    latency_ms = int(payload.get("latency_ms", 0))

    if not text.strip():
        return OcrResult(
            text="", status="empty_image",
            char_count=0, model_used=model_used, latency_ms=latency_ms,
            error_message=(
                "Ảnh trắng hoặc không nhận dạng được chữ — "
                "thử ảnh độ phân giải cao hơn."
            ),
        )

    return OcrResult(
        text=text, status="ok",
        char_count=char_count, model_used=model_used, latency_ms=latency_ms,
    )
