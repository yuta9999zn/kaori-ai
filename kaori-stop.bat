@echo off
REM ============================================================
REM  Kaori AI - Pilot stack stopper (Windows)
REM ============================================================
REM  Tat tat ca services sach se. Data van duoc giu nguyen
REM  trong Docker volumes, lan sau bat lai chay tiep.
REM
REM  Usage: double-click hoac:
REM    kaori-stop.bat
REM
REM  De XOA SACH data (factory reset), chay:
REM    docker compose down -v
REM  (Khong khuyen tru khi anh muon test lai tu dau)
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   Kaori AI Pilot Stack - Stopping
echo ============================================================
echo.

docker info >nul 2>&1
if errorlevel 1 (
    echo [INFO] Docker Desktop khong chay - stack da tat.
    pause
    exit /b 0
)

echo Tat tat ca services...
docker compose down

if errorlevel 1 (
    echo.
    echo [LOI] docker compose down bi loi. Xem log o tren.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Stack DA TAT
echo ============================================================
echo.
echo   - RAM/CPU da tra ve 0.
echo   - Data van con (Postgres rows, files upload, Qwen model).
echo   - Lan sau chay 'kaori-start.bat' de bat lai - data nguyen.
echo.
echo   Disk dang chiem:
docker system df 2>nul | findstr /B "Volumes"
echo.

endlocal
