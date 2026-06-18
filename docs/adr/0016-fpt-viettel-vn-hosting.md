# ADR-0016 — Vietnam region hosting (FPT Cloud / Viettel IDC)

> **Status:** proposed
> **Date:** 2026-05-08
> **Deciders:** Nguyen Truong An
> **Related:** `docs/strategic/SAD_SKELETON_V2.md` Phần 5.1 (Compute) · Phần 40 (VN Region Hosting) · Phần 54 (ADR-007 master) · ADR-0009 (localhost-runner-pilot)

## Context

Pilot hiện chạy laptop 16 GB (Olist seed loaded). Phase 1 v4 đòi production cluster trên Kubernetes. Câu hỏi: hosting ở đâu?

Forces:

1. **Data residency (luật + customer trust).** Khách enterprise Vietnam (banking, retail, FMCG) ưu tiên data trong nước. Một số ngành (fintech) có yêu cầu pháp lý.
2. **Latency.** P95 < 200ms cho UI, P99 < 1s cho insight call. Hosting US-East = +200ms RTT; Singapore = +30-50ms; VN = <10ms.
3. **Cost.** AWS/GCP region SG = $$$ (gấp 2-3 FPT Cloud equivalent specs). FPT/Viettel có gói SME giá VND.
4. **Operational maturity.** AWS/GCP managed K8s (EKS/GKE) production-ready, ops dễ. FPT Cloud Kubernetes Service mới hơn, một số feature chưa đầy đủ. Viettel IDC còn raw VM nhiều hơn managed K8s.
5. **Vendor lock-in.** Quá nhiều managed service AWS = lock; FPT/Viettel ít managed nhưng cũng ít lock.

## Decision

Phase 1 + 1.5 chúng ta deploy **FPT Cloud (Hồ Chí Minh region) làm primary**, **Viettel IDC làm secondary (DR)** Phase 2+:

1. **Compute:** Kubernetes 1.28+ trên FPT Cloud Kubernetes Service (FKE) hoặc tự deploy K8s trên FPT VM (kubespray) nếu FKE chưa đủ feature. Phase 1.5 sprint P15-S9 deploy.
2. **Persistence:** Postgres + ClickHouse + MinIO + Redis + Vault chạy trong cluster (StatefulSet + persistent volume FPT Cloud SSD).
3. **CDN:** Bunny.net hoặc VN-based (BizFly) cho static asset.
4. **Region 2 (Phase 2+):** Hà Nội region (FPT Cloud HN) hoặc Viettel IDC active-active cho DR + latency miền Bắc.
5. **International expansion (Phase 2 Sprint P2-S23 SG pilot):** Singapore region trên AWS Singapore HOẶC partner regional cloud (cân nhắc Phase 2). KHÔNG mặc định AWS — quyết định riêng theo customer.
6. **LLM vendor traffic (Anthropic, OpenAI):** outbound từ VN → US/EU. Latency vendor-side ~500ms-2s đã chiếm phần lớn → hosting region không phải bottleneck.
7. **Pilot Olist (anh chạy laptop):** giữ docker-compose local (ADR-0009), không touch. Onboard FPT Cloud từ khách thứ 2-3 trở đi.

## Consequences

### Positive

- Data residency VN: customer enterprise OK, ngành regulated OK.
- Latency UI tốt cho khách VN.
- Cost ~30-50% rẻ hơn AWS Singapore (FPT Cloud SME pricing).
- Anh giữ pilot localhost không gián đoạn.
- VND billing → kế toán Việt Nam đơn giản.

### Negative / accepted trade-offs

- FPT Cloud Kubernetes Service ít managed feature (no managed Postgres-as-a-service tier 1, no managed ClickHouse) → tự vận hành StatefulSet.
- Less mature observability ecosystem (Datadog/New Relic agent có sẵn nhưng ít customer VN dùng).
- DR cross-region (VN HCM ↔ HN) latency ~30-50ms → eventual consistency cho replication.
- Recruit DevOps có kinh nghiệm FPT Cloud khó hơn AWS — Phase 1 chỉ 1 dev nên không phải vấn đề.
- International customer Phase 2 đòi region SG → multi-region complexity.

### Neutral / follow-ups

- Phase 1.5 evaluate FPT Cloud FKE managed offerings (có thể dùng nếu đã GA).
- Phase 2 ADR mới cho Singapore region khi có customer SG đầu tiên.
- Phase 2 SOC 2 Type 1 audit: FPT Cloud có SOC 2 attestation chưa? Nếu chưa → có thể cần migrate sang region có SOC 2 (vendor liability shift).
- Phase 3 đánh giá multi-region active-active strategy theo customer geography.

## Alternatives considered

- **AWS Singapore (EKS).** Rejected Phase 1: data residency VN, cost 2-3x. Reconsider Phase 2 cho international.
- **GCP Tokyo / Singapore.** Rejected: tương tự AWS, không gần VN bằng FPT.
- **Self-hosted on-premises (customer datacenter).** Phase 3 option (P3-S33 on-prem deployment) cho regulated customer; không khả thi Phase 1.
- **Azure Vietnam (gốc Microsoft Saigon).** Cân nhắc Phase 2; hiện Azure VN chỉ edge zone, chưa full region.

## References

- `docs/strategic/SAD_SKELETON_V2.md` Phần 5.1 + Phần 40 + Phần 54
- ADR-0009 (localhost runner pilot)
- Memory `project_pilot_deployment.md` (laptop pilot Option C)
- FPT Cloud pricing: ~30-50 triệu VND/tháng cho cluster 6-node ban đầu (estimate, cần xác nhận khi sign)
