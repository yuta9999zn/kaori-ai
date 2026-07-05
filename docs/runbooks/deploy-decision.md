# Deploy Decision — chọn đường triển khai (chuẩn bị cho AABW day-10)

> **Mục đích:** chuẩn bị SẴN các đường deploy để ngày 10 (sau workshop) chọn cái tối ưu là chạy được trong ~1h. Chưa deploy — đây là bộ đồ nghề + khung quyết định.
> **Sản phẩm thi:** monorepo Kaori (`kaori-system` private, dev) → mirror sang `kaori-ai` public (link nộp bài). Cả hai build từ cùng image self-contained (sau fix **A1**).
> **Trạng thái:** A1 (image self-contained) đã test PASS trên private 2026-07-05 — 2 image Python chạy không cần mount. AWS/EKS chart đã hardened + validate (xem `aws-eks-readiness.md`).

## Nền chung cho MỌI đường: A1 — image self-contained
`data-pipeline` + `ai-orchestrator` giờ bake `config/etl/utils/kafka-schemas` vào image (không còn phụ thuộc mount repo-root). Nhờ đó cùng một artifact chạy được trên laptop, EC2, VPS, EKS — và bản public `kaori-ai` build được độc lập. Đây là lý do sửa A1 trước tiên: một chỗ, lợi mọi đường.

## 3 đường — so sánh

| Tiêu chí | **EC2 + compose** ⭐ | **EKS** | **VPS + compose** |
|---|---|---|---|
| Bản chất | 1 VM AWS chạy `docker-compose.prod` | Chart Helm (`values-aws-eks.yaml`) | VPS sẵn (Caddy TLS) chạy compose |
| Thời gian dựng | ~1h | nhiều giờ (VPC/RDS/IRSA/add-ons) | ~1h |
| Chi phí/tháng | ~$30–70 (1 VM t3.large + EBS) | ~$550+ (control plane+nodes+RDS+…) | ~$5–20 (VPS có sẵn) |
| "Trên AWS" (điểm với BGK) | ✅ có | ✅✅ (kể chuyện scale/production) | ❌ (ngoài AWS) |
| Rủi ro khi demo | thấp | cao (nhiều bộ phận động) | thấp |
| Khi nào chọn | **Demo thi mặc định** | Nếu muốn khoe production-readiness | Dự phòng nếu AWS trục trặc / siêu rẻ |

**Khuyến nghị:** demo thi nhắm **EC2 + compose** (vừa "trên AWS", vừa nhanh-rẻ-ổn). Giữ **EKS** làm câu chuyện production (chart đã sẵn, không phí công vì EC2-compose là tập con). **VPS** là phao dự phòng.

## Checklist ngày 10 — theo đường đã chọn

### Đường A — EC2 + compose (mặc định)
1. EC2 `t3.large` (2 vCPU/8GB) Ubuntu 22.04, security group mở 80/443 (+22 IP của anh). Nếu cần Qwen 14B → `g5.xlarge` GPU; nếu 7B → t3.large đủ.
2. `sudo apt install docker.io docker-compose-plugin -y`
3. `git clone https://github.com/yuta9999zn/kaori-ai.git && cd kaori-ai`  *(hoặc kaori-system nếu deploy bản private)*
4. `cp .env.production.example .env.production` → điền `CHANGE_ME` (JWT keypair, MFA key, DB pw, domain).
5. `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d <danh sách service>` (xem đầu `docker-compose.prod.yml`).
6. Migrations: auth-service chạy Flyway lúc boot (single host, không đua replica). Kéo model: `docker exec kaori-ollama-1 ollama pull qwen2.5:7b && ollama pull bge-m3`.
7. TLS: Caddy/nginx reverse-proxy 443 → api-gateway:8080 + frontend:3000; trỏ domain (hoặc dùng IP:port cho demo nhanh).
8. Smoke: đăng nhập, upload 1 file, chạy 1 workflow, mở 1 report → chụp làm Demo URL/Video.

### Đường B — EKS (production story)
Theo `docs/runbooks/aws-eks-readiness.md` §6 (provision RDS/ElastiCache/MSK/S3 + IRSA + add-ons → fill `<FILL_*>` trong `values-aws-eks.yaml` → `helm upgrade --install`). Cần build+push image lên ECR trước (A1 đã làm image self-contained).

### Đường C — VPS (dự phòng)
Giống đường A bước 2–8 nhưng trên VPS sẵn có (đã có Caddy). Rẻ nhất, không có "trên AWS".

## Việc còn lại trước ngày 10 (chuẩn bị, chưa deploy)
- [x] A1 — image self-contained (test PASS private).
- [x] `.env.production.example`, `docker-compose.prod.yml`, `values-aws-eks.yaml`, runbook AWS.
- [ ] Đồng bộ `kaori-ai` public đầy đủ (loại dữ liệu khách nhạy cảm — chờ anh chốt).
- [ ] (tuỳ chọn) CI build+push image lên registry theo git SHA.
- [ ] Chốt model LLM cho demo (7B non-GPU vs 14B GPU) — ảnh hưởng loại máy.

## Tham chiếu
- `docs/runbooks/aws-eks-readiness.md` — chi tiết EKS + premortem/red-team.
- `docker-compose.prod.yml`, `.env.production.example` — đường EC2/VPS.
- `infrastructure/k8s/helm-charts/kaori-services/` — chart + `values-aws-eks.yaml`.
