param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart")]
    [string]$Action = "restart",

    [switch]$KeepLogs
)

$ErrorActionPreference = "Stop"
$ROOT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND_DIR = Join-Path $ROOT_DIR "backend"
$FRONTEND_DIR = Join-Path $ROOT_DIR "frontend"
$LOG_FILE = Join-Path $ROOT_DIR "logs\trade_alpha.log"
$PYTHON_EXE = Join-Path $BACKEND_DIR ".venv\Scripts\python.exe"

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "--------------------------------------------------"
    Write-Host " $Text"
    Write-Host "--------------------------------------------------"
}

function Stop-Services {
    Write-Header "Stopping Services"

    $backendPids = @()
    $frontendPids = @()

    $connections = Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -eq 8000 -or $_.LocalPort -eq 3000 }
    foreach ($conn in $connections) {
        $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            $processName = $process.ProcessName
            $processId = $process.Id
            Write-Host "  Found process: $processName (PID: $processId) on port $($conn.LocalPort)"

            if ($conn.LocalPort -eq 8000) {
                $backendPids += $processId
            } elseif ($conn.LocalPort -eq 3000) {
                $frontendPids += $processId
            }
        }
    }

    if ($backendPids.Count -eq 0 -and $frontendPids.Count -eq 0) {
        Write-Host "  No services running"
        return
    }

    Write-Host ""
    Write-Host "  Stopping backend processes..."
    foreach ($p in $backendPids) {
        Write-Host "    Killing PID: $p"
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }

    Write-Host "  Stopping frontend processes..."
    foreach ($p in $frontendPids) {
        Write-Host "    Killing PID: $p"
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }

    Start-Sleep -Seconds 2
    Write-Host "  Done"
}

function Remove-Logs {
    if (Test-Path $LOG_FILE) {
        Write-Host "  Deleting log file: $LOG_FILE"
        Remove-Item $LOG_FILE -Force
    } else {
        Write-Host "  No log file to delete"
    }
}

function Start-Services {
    Write-Header "Starting Services"

    if (-not (Test-Path $PYTHON_EXE)) {
        Write-Host "  [ERROR] Python not found: $PYTHON_EXE"
        Write-Host "  Please create virtual environment first:"
        Write-Host "    cd backend && python -m venv .venv"
        exit 1
    }
    Write-Host "  Using Python: $PYTHON_EXE"

    if (-not (Test-Path (Join-Path $FRONTEND_DIR "node_modules"))) {
        Write-Host "  [ERROR] Frontend dependencies not installed"
        Write-Host "  Please run: cd frontend && npm install"
        exit 1
    }

    Write-Host ""
    Write-Host "  Starting backend service..."
    Start-Process -FilePath $PYTHON_EXE `
        -ArgumentList "-m uvicorn trade_alpha.api.main:app --reload --port 8000" `
        -WorkingDirectory $BACKEND_DIR `
        -WindowStyle Hidden
    Write-Host "    Backend started"

    Start-Sleep -Seconds 3

    Write-Host "  Starting frontend service..."
    Start-Process -FilePath "npm" `
        -ArgumentList "run dev" `
        -WorkingDirectory $FRONTEND_DIR `
        -WindowStyle Hidden
    Write-Host "    Frontend started"

    Write-Host "  Done"
}

function Show-Services {
    Write-Header "Service Status"

    $backendRunning = (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0
    $frontendRunning = (Get-NetTCPConnection -State Listen -LocalPort 3000 -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0

    Write-Host "  Backend (port 8000):  $(if ($backendRunning) { 'RUNNING' } else { 'STOPPED' })"
    Write-Host "  Frontend (port 3000): $(if ($frontendRunning) { 'RUNNING' } else { 'STOPPED' })"
}

Write-Host ""
Write-Host "trade-alpha Service Manager"
Write-Host "Action: $Action"

switch ($Action) {
    "stop" {
        Stop-Services
    }
    "start" {
        Start-Services
    }
    "restart" {
        Stop-Services
        if (-not $KeepLogs) {
            Remove-Logs
        }
        Start-Services
        Show-Services
    }
}
