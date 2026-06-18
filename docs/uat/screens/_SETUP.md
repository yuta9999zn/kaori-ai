# UAT Setup (1 lần / session)

## 1. Stack docker + seed

```powershell
# Bật postgres + auth-service + ollama + ...
.\kaori-start.bat

# Seed admin platform (idempotent — chạy nhiều lần OK)
.\kaori-seed-admin.bat
# → superadmin@kaori.local / Kaori@Admin1 (SUPER_ADMIN, MFA off)
```

(Tuỳ chọn: chạy `python scripts/seed-pilot-olist.py` để có thêm:
- admin: `admin@kaori.platform` / `Admin@2026` (SUPER_ADMIN)
- enterprise manager: `cs@olist.local` / `Pilot@2026` (MANAGER) cho Olist workspace.)

## 2. Dừng docker frontend container (BẮT BUỘC)

```powershell
docker compose stop frontend
```

`docker-compose.yml` có service `frontend` map `3000:3000` chạy code cũ
từ lần build trước. Không dừng → `npm run dev` nhảy sang port khác →
browser test sai bản. Documented đầy đủ ở `MIGRATION_REPORT_P1.md` mục
"Dev-loop gotcha".

## 3. Dev server frontend

```powershell
cd frontend
npm run dev
```

Đợi banner:
```
▲ Next.js 16.2.4 (webpack)
- Local:         http://localhost:3000
✓ Ready in <ms>
```

**QUAN TRỌNG:** Phải là `(webpack)` không phải `(Turbopack)`. `package.json`
script `dev` mặc định `--webpack` (commit `282e8e7`). Nếu thấy Turbopack
→ `Ctrl+C` rồi `npm run dev` lại để pick up flag.

## 4. Browser

```
http://localhost:3000/platform/login    ← Platform admin
http://localhost:3000/login              ← Enterprise user
```

DevTools mở: Network tab + Application → Local Storage.

## 5. Cleanup giữa các test

Để reset session về login state:
```js
// browser console
localStorage.clear();
sessionStorage.clear();
location.reload();
```

## 6. Quick BE health check

```powershell
curl http://localhost:8091/actuator/health     # auth-service
curl http://localhost:8080/actuator/health     # api-gateway
```

Nếu BE down → mọi UAT test sẽ fail RFC 7807 banner. Restart `.\kaori-start.bat`.
