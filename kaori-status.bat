@echo off
REM ============================================================
REM  Kaori AI - Pilot stack status (Windows)
REM ============================================================
REM  Hien thi:
REM    1. Service nao dang chay + healthcheck status
REM    2. RAM/CPU dang dung boi tung container
REM    3. Disk usage cua Docker volumes
REM    4. URL truy cap
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   Kaori AI Pilot Stack - Status
echo ============================================================

docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo [INFO] Docker Desktop chua chay.
    echo Mo Docker Desktop roi chay 'kaori-start.bat' de bat stack.
    echo.
    pause
    exit /b 0
)

echo.
echo --- 1. Services dang chay ---
docker compose ps

echo.
echo --- 2. RAM / CPU consumption ---
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>nul

echo.
echo --- 3. Disk usage ---
docker system df

echo.
echo --- 4. URLs (neu stack dang chay) ---
echo   Frontend:        http://localhost:3000
echo   API Gateway:     http://localhost:8080
echo   Swagger UI:      http://localhost:8082
echo   Kafka UI:        http://localhost:8085
echo   Grafana:         http://localhost:3001
echo   Ollama:          http://localhost:11434
echo.

REM Check Qwen model nao dang co
docker compose exec -T ollama ollama list 2>nul
if errorlevel 1 (
    echo [INFO] Ollama chua chay - khong list duoc model.
)

echo.
endlocal
