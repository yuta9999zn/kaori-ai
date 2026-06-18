# ADR-0041 — EU AI Act control framework (trust-first, conformity-ready)

> **Status:** accepted
> **Date:** 2026-06-03
> **Deciders:** Nguyen Truong An (anh), Kaori
> **Related:** ADR-0005 (decision audit), ADR-0013 (RLS), ADR-0015 (Qwen-first / vendor opt-in), ADR-0037 (Tier-3 approvals), K-3/K-4/K-5/K-6/K-17/K-20; spec `D:\Tài liệu dự án\5.1_EU_AI_Act_Compliance_Framework.md`

## Context

Kaori là SaaS B2B chạy AI lên dữ liệu khách (churn risk, decision generation, document/contract reasoning). Phần lớn các tác vụ này — nếu bán vào EU — rơi vào nhóm **high-risk** của EU AI Act (Annex III: scoring ảnh hưởng cá nhân, xử lý hồ sơ, ra quyết định tự động). Luật đã có hiệu lực 8/2024, lệnh cấm + AI-literacy áp 2/2025, nghĩa vụ GPAI 8/2025, nghĩa vụ high-risk đầy đủ 8/2026. Mức phạt trần **35M EUR hoặc 7% doanh thu toàn cầu** — nặng hơn GDPR.

Hiện Kaori tập trung thị trường VN (pilot Đồng Xanh, giá VND), **chưa** bán EU. Nhưng nhiều nghĩa vụ của luật trùng với chất lượng kỹ thuật mình vốn theo đuổi: K-6 audit ≈ Art 12 record-keeping; K-4/K-5 ≈ Art 10 data governance; chaos tests + K-18 Vault ≈ Art 15 robustness/security. Mặt khác mình **thiếu** hẳn 4 thứ: phân loại rủi ro (Art 9), human oversight chính thức (Art 14), model card/technical doc (Art 11/Annex IV), post-market monitoring (Art 26/72).

Lực kéo trong tình thế: làm full conformity ngay (technical documentation Annex IV, conformity assessment, EU authorized rep, CE marking) là khối lượng legal lớn và **chưa cần** khi chưa vào EU — nhưng để rỗng thì khi vào EU phải retrofit toàn bộ harness, đắt và rủi ro. Cần một con đường ở giữa.

## Decision

Mình áp dụng EU AI Act như một **control framework "trust-first, conformity-ready"**: ngay bây giờ triển khai các control có giá trị kỹ thuật như **invariant enforce được**, và thiết kế sẵn điểm cắt-chuyển để nâng lên full conformity khi vào EU thật — không làm conformity assessment/CE/EU-rep ở đợt này.

Cụ thể, mình bổ sung 5 invariant nối tiếp K-21 và triển khai theo **3 lớp**:

- **K-22 Risk classification** — mọi AI-use/workflow đăng ký phải mang `risk_tier ∈ {prohibited, high, limited, minimal}`; `prohibited` bị chặn lúc build (nối K-17 `side_effect_class`).
- **K-23 Human oversight** — quyết định AI high-risk phải có chế độ approve / override / **stop** trước side-effect (nối approval chains ADR-0037 + confidence-based action policy).
- **K-24 Transparency disclosure** — output AI tới end-user phải mang AI-disclosure máy-đọc-được; chatbot tự xưng là AI (nối Art 50).
- **K-25 Model card / technical doc** — mỗi `model + version` trong registry K-20 phải có model card (Annex IV-lite).
- **K-26 Post-market monitoring** — theo dõi incident + drift liên tục; quy trình báo cáo serious-incident (nối `/admin/dlq` 5-source + schema-drift gate).

**Lớp 1 (đợt này, accepted):** chỉ governance — bộ map Điều khoản → control → mỏ neo Kaori + gap list + spec K-22..K-26, đóng băng trong spec `5.1` và ADR này. Chưa đụng code runtime.
**Lớp 2 (proposed, ship sau):** classification gate — bảng `ai_use_risk_register` (mig mới, K-21 `gen_uuid_v7()` PK / `gen_ulid()` external), endpoint đăng ký, chặn build `prohibited`, auto-bật control theo tier.
**Lớp 3 (proposed, ship sau):** runtime enforcement — wire K-23 human-oversight gate + K-24 disclosure vào decision path/`GuardrailEngine`, K-26 monitoring + serious-incident report.

## Consequences

### Positive

- Tận dụng mỏ neo sẵn có: K-6, K-4/K-5, chaos/Vault đã phủ ~3/10 nghĩa vụ ở mức "mạnh" — chỉ cần đặt tên control, không xây lại.
- Khi vào EU, không phải retrofit harness từ đầu: điểm cắt-chuyển full-conformity đã ghi sẵn trong spec `5.1`.
- 5 invariant mới đều có giá trị độc lập với EU (human oversight + transparency + model card + monitoring là chất lượng sản phẩm tốt cho mọi thị trường, kể cả VN).
- Là tín hiệu tin cậy cho khách enterprise + nền móng chung cho GDPR / SOC 2 / ISO 27001 đã có trong roadmap Phase 2-3.

### Negative / accepted trade-offs

- Lớp 1 chỉ là tài liệu — chưa có enforcement runtime; rủi ro doc trôi khỏi code nếu Lớp 2/3 bị hoãn lâu. Giảm thiểu bằng cách ghi rõ trạng thái "proposed" và gắn vào invariant ledger CLAUDE.md khi ship.
- Chưa làm conformity assessment / CE / EU authorized rep / technical documentation Annex IV đầy đủ → **chưa được phép** bán high-risk AI vào EU cho tới khi hoàn tất phần đó.
- Thêm 5 invariant = thêm bề mặt phải duy trì + test khi Lớp 2/3 ship.

### Neutral / follow-ups

- Cập nhật bảng invariant trong CLAUDE.md (K-22..K-26) khi Lớp 2 ship — chưa làm ở đợt này để tránh ghi invariant chưa enforce.
- Bias examination (Art 10) cần bổ sung vào Medallion Stage-4 quality gate — để Lớp 3.
- GPAI (Art 53-55) chủ yếu là nghĩa vụ model provider (Qwen/Anthropic/OpenAI); mình theo dõi phần copyright + technical-doc passthrough, không tự gánh.
- Trigger reconsider → full conformity: khi có hợp đồng/khách EU đầu tiên ký, hoặc khi mở pháp nhân EU.

## Alternatives considered

- **Full conformity ngay (Annex IV + assessment + CE + EU rep):** đúng luật nhất nếu bán EU, nhưng khối lượng legal lớn và lãng phí khi chưa vào EU; nguy cơ over-engineer trước nhu cầu. Bỏ vì YAGNI — đã giữ đường nâng cấp trong spec.
- **Chỉ làm tài liệu mapping, không thêm invariant:** rẻ nhất nhưng để gap hở (không human oversight / không model card) — đúng những thứ vừa là rủi ro pháp lý vừa là chất lượng sản phẩm. Bỏ vì bỏ lỡ giá trị độc-lập-với-EU.
- **Coi đây thuần GDPR-style data privacy:** trùng một phần (PII, data governance) nhưng bỏ sót cốt lõi AI Act (risk tiering, human oversight, transparency AI-generated). Bỏ vì không phủ đủ.

## References

- Spec đầy đủ: `D:\Tài liệu dự án\5.1_EU_AI_Act_Compliance_Framework.md`
- EU AI Act (Regulation (EU) 2024/1689): Art 5 (prohibited), Art 9-15 (high-risk obligations), Art 26 (deployer), Art 50 (transparency), Art 53-55 (GPAI), Art 72 (post-market monitoring), Annex III (high-risk list), Annex IV (technical documentation)
- Mỏ neo Kaori: K-3..K-6, K-17, K-20 (CLAUDE.md §4); `services/llm-gateway/guardrails/engine.py`; `ai_decision_audit` / `record_ai_call`; approval chains ADR-0037

---

**Editing note** — ADRs are append-only by convention. K-22..K-26 ở trạng thái framework-accepted nhưng enforcement Lớp 2/3 còn `proposed`; khi ship sẽ ghi PR + mig vào References, không rewrite quyết định này.
