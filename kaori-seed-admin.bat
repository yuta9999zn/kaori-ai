@echo off
REM ============================================================
REM  Kaori AI - Seed default Platform SUPER_ADMIN (chay 1 LAN)
REM ============================================================
REM  Migration 011 tao bang platform_admins nhung khong seed.
REM  Script nay insert 1 SUPER_ADMIN mac dinh de anh login vao
REM  /platform lan dau. Sau do anh nen:
REM    1. Login -> doi password (qua /platform/admins/{id}/reset-password)
REM    2. Mo MFA (qua /platform/security/mfa)
REM    3. Tao thanh vien khac, deactivate default neu can
REM
REM  Default credentials (DOI NGAY SAU LOGIN LAN DAU):
REM    Email:    superadmin@kaori.local
REM    Password: Kaori@Admin1
REM    Role:     SUPER_ADMIN
REM
REM  Idempotent - chay nhieu lan khong tao trung (ON CONFLICT DO NOTHING).
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   Kaori AI - Seed Platform SUPER_ADMIN
echo ============================================================
echo.

docker info >nul 2>&1
if errorlevel 1 (
    echo [LOI] Docker Desktop chua chay. Bat 'kaori-start.bat' truoc.
    pause
    exit /b 1
)

REM Verify postgres dang chay
docker compose ps postgres --format json | findstr /C:"running" >nul 2>&1
if errorlevel 1 (
    echo [LOI] Postgres chua chay. Bat 'kaori-start.bat' truoc.
    pause
    exit /b 1
)

echo Inserting SUPER_ADMIN vao platform_admins...
echo.

REM Dung pgcrypto.crypt() + gen_salt('bf', 12) de gen BCrypt $2a$ hash
REM compatible voi Spring Security BCryptPasswordEncoder.
docker compose exec -T postgres psql -U kaori -d kaori -v ON_ERROR_STOP=1 -c "INSERT INTO platform_admins (email, password_hash, full_name, role, is_active, mfa_enabled, activated_at) VALUES ('superadmin@kaori.local', crypt('Kaori@Admin1', gen_salt('bf', 12)), 'Kaori Super Admin', 'SUPER_ADMIN', true, false, NOW()) ON CONFLICT (email) DO NOTHING RETURNING admin_id, email, role;"

if errorlevel 1 (
    echo.
    echo [LOI] Insert that bai. Co the:
    echo   - Postgres chua chay - kiem tra: docker compose ps postgres
    echo   - Migration 011 chua chay - xem log: docker compose logs auth-service
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   SEED THANH CONG
echo ============================================================
echo.
echo   Login P1 Platform:
echo     URL:       http://localhost:3000/platform/login
echo     Email:     superadmin@kaori.local
echo     Password:  Kaori@Admin1
echo.
echo   QUAN TRONG sau khi login lan dau:
echo     1. Doi password ngay (Settings hoac /platform/admins)
echo     2. Mo MFA (/platform/security/mfa) - bat buoc cho SUPER_ADMIN
echo     3. Neu da co admin khac -> deactivate default account nay
echo.
echo   Neu thay 'INSERT 0 0' o tren = admin da co tu truoc, OK.
echo.

endlocal
