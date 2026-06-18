@echo off
REM ============================================================
REM  Kaori AI — Pilot stack starter (Windows)
REM ============================================================
REM  Bat tat ca services + doi healthcheck pass + auto-pull Qwen 7B
REM  neu chua co + mo browser toi localhost:3000.
REM
REM  Usage: chi can double-click hoac chay tu cmd:
REM    kaori-start.bat
REM
REM  Lan dau chay: ~15-20 phut (pull images + Qwen 7B model ~5 GB).
REM  Lan sau: ~2-3 phut.
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   Kaori AI Pilot Stack - Starting
echo ============================================================
echo.

REM --- Pre-flight: Docker dang chay khong ---
docker info >nul 2>&1
if errorlevel 1 (
    echo [LOI] Docker Desktop chua chay. Mo Docker Desktop roi thu lai.
    echo.
    pause
    exit /b 1
)

REM --- Pre-flight: .env file ton tai khong ---
if not exist ".env" (
    echo [LOI] File .env chua co. Chay lan dau:
    echo.
    echo   1. copy .env.example .env
    echo   2. .\scripts\generate-jwt-keys.sh
    echo   3. .\scripts\generate-mfa-key.sh
    echo   4. Sua POSTGRES_PASSWORD trong .env
    echo.
    echo Xem chi tiet trong docs\HOW_TO_RUN_PILOT.md
    pause
    exit /b 1
)

REM --- Buoc 1: Start tat ca services ---
echo [1/4] Khoi dong stack (postgres, redis, kafka, ollama, 5 app services, frontend)...
docker compose up -d
if errorlevel 1 (
    echo [LOI] docker compose up bi loi. Xem log o tren.
    pause
    exit /b 1
)

REM --- Buoc 2: Doi Ollama healthy ---
echo.
echo [2/4] Doi Ollama san sang (~30s)...
set /a "wait_count=0"
:wait_ollama
docker compose ps ollama --format json | findstr /C:"healthy" >nul 2>&1
if errorlevel 1 (
    set /a "wait_count+=1"
    if !wait_count! geq 30 (
        echo [CANH BAO] Ollama mat hon 5 phut de healthy. Xem log:
        echo   docker compose logs ollama
        goto skip_ollama_pull
    )
    timeout /t 10 /nobreak >nul
    goto wait_ollama
)
echo   Ollama healthy.

REM --- Buoc 3: Pull Qwen 7B model neu chua co ---
echo.
echo [3/4] Kiem tra Qwen 7B model...
docker compose exec -T ollama ollama list 2>nul | findstr "qwen2.5:7b" >nul
if errorlevel 1 (
    echo   Chua co qwen2.5:7b. Pulling (~5 GB, ~5-10 phut tuy mang)...
    docker compose exec -T ollama ollama pull qwen2.5:7b
    if errorlevel 1 (
        echo [CANH BAO] Pull Qwen that bai. Co the chay tay sau:
        echo   docker compose exec ollama ollama pull qwen2.5:7b
    ) else (
        echo   Qwen 7B ready.
    )
) else (
    echo   Qwen 7B da co san.
)
:skip_ollama_pull

REM --- Buoc 4: Doi auth-service healthy (Flyway migrations chay tu dong) ---
echo.
echo [4/4] Doi auth-service san sang (Flyway migrations + bootstrap)...
set /a "wait_count=0"
:wait_auth
curl -s -f -o nul http://localhost:8091/health 2>nul
if errorlevel 1 (
    set /a "wait_count+=1"
    if !wait_count! geq 18 (
        echo [CANH BAO] auth-service mat hon 3 phut. Xem log:
        echo   docker compose logs auth-service
        goto done
    )
    timeout /t 10 /nobreak >nul
    goto wait_auth
)
echo   auth-service healthy.

:done
echo.
echo ============================================================
echo   Stack DA SAN SANG
echo ============================================================
echo.
echo   Frontend:        http://localhost:3000
echo   API Gateway:     http://localhost:8080
echo   Swagger UI:      http://localhost:8082
echo   Kafka UI:        http://localhost:8085
echo   Grafana:         http://localhost:3001
echo.
echo   Default login (Enterprise P2):
echo     URL:           http://localhost:3000/login
echo     Email:         admin@kaori.local
echo     Password:      Admin@kaori1
echo.
echo   Platform admin (P1) chua co - chay 1 lan:
echo     kaori-seed-admin.bat
echo.
echo   Tat stack khi xong:
echo     kaori-stop.bat
echo.

REM Mo browser toi frontend
start "" http://localhost:3000

endlocal
