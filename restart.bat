@echo off
title trade-alpha Service Restart

set ROOT_DIR=%~dp0
if "%ROOT_DIR:~-1%"=="\" set ROOT_DIR=%ROOT_DIR:~0,-1%
set BACKEND_DIR=%ROOT_DIR%\backend
set FRONTEND_DIR=%ROOT_DIR%\frontend

rem ---- Find Python ----
set PYTHON_EXE=
if exist "%BACKEND_DIR%\.venv\Scripts\python.exe" set PYTHON_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe
if not defined PYTHON_EXE if exist "%BACKEND_DIR%\venv\Scripts\python.exe" set PYTHON_EXE=%BACKEND_DIR%\venv\Scripts\python.exe
if not defined PYTHON_EXE if exist "%BACKEND_DIR%\env\Scripts\python.exe" set PYTHON_EXE=%BACKEND_DIR%\env\Scripts\python.exe
rem Skip Windows Store stub (WindowsApps), look for real Python in PATH
if not defined PYTHON_EXE for /f "delims=" %%a in ('where python 2^>nul ^| findstr /V /I "WindowsApps"') do set PYTHON_EXE=%%a
rem Try the Python launcher as last resort
if not defined PYTHON_EXE where py >nul 2>&1 && set PYTHON_EXE=py

echo --------------------------------------------------
echo  trade-alpha Service Restart
echo --------------------------------------------------
echo.

rem ---- Cleanup ----

echo [Cleanup] Stopping old processes...

for /f "tokens=6" %%a in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
    if not "%%a"=="0" (
        echo   [Backend] Killing PID: %%a
        taskkill /F /PID %%a >nul 2>&1
    )
)
for /f "tokens=6" %%a in ('netstat -ano ^| findstr /R /C:":3000 .*LISTENING"') do (
    if not "%%a"=="0" (
        echo   [Frontend] Killing PID: %%a
        taskkill /F /PID %%a >nul 2>&1
    )
)

taskkill /F /IM uvicorn.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo   Done
echo.

rem ---- Environment Check ----

if not defined PYTHON_EXE (
    echo [ERROR] Python not found. Please activate or create a virtual environment:
    echo   cd backend ^&^& python -m venv .venv
    pause
    exit /b 1
)
echo   Using Python: %PYTHON_EXE%

if not exist "%FRONTEND_DIR%\node_modules" (
    echo [ERROR] Frontend dependencies not installed
    echo   Run: cd frontend ^&^& npm install
    pause
    exit /b 1
)

rem ---- Start Services ----

echo [Start] Starting backend service...
wmic process call create "cmd /c \"%PYTHON_EXE%\" -m uvicorn trade_alpha.api.main:app --reload --port 8000", "%BACKEND_DIR%" >nul 2>&1
echo   Done
timeout /t 3 /nobreak >nul

echo [Start] Starting frontend service...
wmic process call create "cmd /c npm run dev", "%FRONTEND_DIR%" >nul 2>&1
echo   Done
timeout /t 3 /nobreak >nul

echo.
echo --------------------------------------------------
echo  Services started successfully!
echo    Backend API:  http://localhost:8000
echo    API Docs:     http://localhost:8000/docs
echo    Frontend:     http://localhost:3000
echo --------------------------------------------------
echo.
echo  All services are running in the background
echo  Press Ctrl+C to stop the script (services will continue running)
echo.
