# Kaori AI — Pilot Localhost Runner

> Audience: anh (founder, solo dev) — soft launch internal pilot trên laptop  cá nhân.
> Spec yêu cầu tối thiểu: RAM 16 GB · Disk 30 GB free · Docker Desktop · CPU bất kỳ (Intel i9 / AMD Ryzen 7 trở lên đề nghị)
> Tested trên: Windows 11 + Docker Desktop 4.x + i9-13900H + 16 GB RAM

---

## 0. Trước khi chạy lần đầu — checklist (~10 phút)

| Step | Command | Note |
|---|---|---|
| 0.1 | Cài **Docker Desktop** for Windows | https://www.docker.com/products/docker-desktop/ — bật WSL2 backend |
| 0.2 | Cài **Git for Windows** (đã có Git Bash) | Cần để chạy 2 file `.sh` ở step 0.4 + 0.5 |
| 0.3 | `copy .env.example .env` | Tạo file env từ template |
| 0.4 | Mở Git Bash → chạy `./scripts/generate-jwt-keys.sh` | Tự sửa `.env` cho JWT_PRIVATE_KEY + JWT_PUBLIC_KEY |
| 0.5 | Mở Git Bash → chạy `./scripts/generate-mfa-key.sh` | Tự sửa `.env` cho KAORI_MFA_KEY (32 byte AES-256) |
| 0.6 | Sửa `POSTGRES_PASSWORD` trong `.env` | Đặt 1 password mạnh, tối thiểu 16 ký tự |
| 0.7 | Sửa `SMTP_USER` + `SMTP_PASSWORD` trong `.env` (optional) | Để gửi email password-reset / invite. Skip nếu pilot internal không cần email |

Sau khi xong 0.1 → 0.7, anh đã sẵn sàng chạy stack.

---

## 1. Daily workflow — 4 lệnh

| Việc | Lệnh | Thời gian |
|---|---|---|
| **Bật stack** | Double-click `kaori-start.bat` | Lần đầu ~15-20 phút (pull images + Qwen 7B). Lần sau ~2-3 phút |
| **Tắt stack** | Double-click `kaori-stop.bat` | ~5 giây |
| **Xem trạng thái** | Double-click `kaori-status.bat` | Tức thì |
| **Seed admin (CHỈ LẦN ĐẦU)** | Double-click `kaori-seed-admin.bat` | ~3 giây — chạy 1 lần sau first up |

---

## 2. First-time setup chi tiết

```
┌─ Day 0 ──────────────────────────────────────────────┐
│  1. Mo Docker Desktop                                │
│  2. Double-click kaori-start.bat                     │
│     → đợi ~15-20 phút, browser tự mở localhost:3000 │
│                                                      │
│  3. Double-click kaori-seed-admin.bat                │
│     → tạo SUPER_ADMIN platform                       │
│                                                      │
│  4. Login:                                           │
│     Enterprise:  http://localhost:3000/login         │
│       admin@kaori.local / Admin@kaori1               │
│     Platform:    http://localhost:3000/platform/login│
│       superadmin@kaori.local / Kaori@Admin1          │
│                                                      │
│  5. Đổi password ngay 2 account trên                 │
│  6. Bật MFA cho SUPER_ADMIN platform                 │
└──────────────────────────────────────────────────────┘
```

Tài khoản **default admin**:

| Portal | URL login | Email | Password (đổi ngay) |
|---|---|---|---|
| **P2 Enterprise** | `/login` | `admin@kaori.local` | `Admin@kaori1` |
| **P1 Platform** | `/platform/login` | `superadmin@kaori.local` | `Kaori@Admin1` |

> Cả 2 default này đều seed kèm flag `is_active=true` nên login được ngay. **Đổi password lần đầu** qua reset-password flow trong product.

---

## 3. Đổi LLM model (sau pilot, vd: 7B → 14B hoặc đổi sang Qwen 3 / Llama 3)

```bash
# 1. Sửa file .env, dòng OLLAMA_MODEL
OLLAMA_MODEL=qwen2.5:14b      # Hoặc: qwen3:7b, llama3.1:8b, mistral:7b...

# 2. Pull model mới (qua Git Bash hoặc cmd)
docker compose exec ollama ollama pull qwen2.5:14b

# 3. Restart 2 service đọc env này
docker compose restart ai-orchestrator llm-gateway

# 4. Verify
kaori-status.bat        # Xem model đã list trong Ollama chưa
```

**Không ảnh hưởng:**
- ✅ Codebase — `llm_router.py` forward request lên `llm-gateway`, không hard-code model name
- ✅ DB schema — Bronze/Silver/Gold không chứa model info
- ✅ Data đã ingest/analyze cũ — vẫn còn nguyên
- ✅ Embedding (BGE-M3) — model riêng, độc lập

**Cần lưu ý:**
- ⚠️ RAM: 7B ~5GB · 14B ~10GB · 32B ~20GB. Anh đang 16GB RAM → 14B sẽ swap, chậm
- ⚠️ Quality threshold ở Rule 4 (CLAUDE.md §8) có thể cần re-tune nếu đổi sang model architecture khác hẳn (vd Qwen → Llama)

---

## 4. Truy cập từ xa cho pilot tester (optional)

Nếu pilot tester ở xa (không cùng wifi), wire **Cloudflare Tunnel** (free):

```bash
# Cài cloudflared (1 lần):
winget install --id Cloudflare.cloudflared

# Mở tunnel sau khi stack đã chạy:
cloudflared tunnel --url http://localhost:3000

# → Console in ra URL dạng https://kaori-pilot-xxx.trycloudflare.com
# Share URL này cho tester. HTTPS thật, không cần domain riêng.
```

⚠️ Tunnel chỉ live khi terminal mở. Đóng terminal = tunnel down. Tester sẽ mất kết nối.

---

## 5. Troubleshooting

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `kaori-start.bat` báo "Docker Desktop chua chay" | Docker chưa khởi động | Mở Docker Desktop, đợi ~30s, chạy lại |
| `kaori-start.bat` báo "File .env chua co" | Chưa làm step 0 | Quay lại §0 checklist |
| Pull Qwen 7B fail giữa chừng | Mạng yếu / timeout | Chạy lại `kaori-start.bat` — Ollama tự resume từ chỗ dừng |
| Auth-service không healthy sau 3 phút | Migration Flyway lỗi | `docker compose logs auth-service` — thường do Postgres password trong `.env` không khớp |
| Login fail "Invalid credentials" với default admin | `kaori-seed-admin.bat` chưa chạy / bị lỗi | Chạy lại `kaori-seed-admin.bat`, xem stdout |
| Browser load `/dashboard` chậm > 5s | Qwen đang trả lời analysis (CPU-only inference) | Bình thường trên máy không có GPU rời. Có thể đổi sang `qwen2.5:3b` (~2 GB) cho responsive hơn nhưng quality giảm |
| Laptop nóng / fan kêu lúc chạy analysis | Ollama đang full CPU | Bình thường. Nếu nặng quá → tắt 1 service không dùng (`docker compose stop kafka kafka-ui prometheus grafana`) để bớt ~2 GB RAM |
| `kaori-stop.bat` xong mà disk vẫn full | Volumes còn data | Bình thường (data persist). Nếu muốn factory reset → `docker compose down -v` (mất hết data) |

---

## 6. Danh sách URL nội bộ (sau khi stack chạy)

| Service | URL | Note |
|---|---|---|
| Frontend | http://localhost:3000 | UI chính |
| API Gateway | http://localhost:8080 | REST endpoint |
| Swagger UI | http://localhost:8082 | API docs |
| Kafka UI | http://localhost:8085 | Topic + lag monitor |
| Grafana | http://localhost:3001 | Default `admin/admin` (đổi sau) |
| Ollama | http://localhost:11434 | LLM server |
| Postgres | localhost:5432 | DB direct (user `kaori`, password trong `.env`) |

---

## 7. Sau pilot — cleanup

Khi pilot xong, muốn dọn sạch laptop:

```bash
# 1. Tắt stack
kaori-stop.bat

# 2. Xóa volumes (data + Qwen model + Docker images)
docker compose down -v --rmi all

# 3. (Optional) Xóa Docker network
docker network prune -f

# Disk được giải phóng ~25-30 GB.
```

---

## 8. Reference

- Pilot UAT script: [`docs/DEMO_RUNBOOK.md`](./DEMO_RUNBOOK.md)
- Architecture: [`CLAUDE.md`](../CLAUDE.md)
- Backlog: [`docs/BACKLOG.md`](./BACKLOG.md)
- MFA key rotation: [`CLAUDE.md` §15](../CLAUDE.md#15-mfa-key-management)
