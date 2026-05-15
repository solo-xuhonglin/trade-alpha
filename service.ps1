param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart")]
    [string]$Action = "restart"
)

$ROOT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND_DIR = Join-Path $ROOT_DIR "backend"
$FRONTEND_DIR = Join-Path $ROOT_DIR "frontend"
$PYTHON_EXE = Join-Path $BACKEND_DIR ".venv\Scripts\python.exe"

function Stop-Services {
    Write-Host "  Stopping services..."
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "  Done"
}

function Start-Services {
    Write-Host "  Starting backend..."
    Start-Process -WindowStyle Hidden -FilePath $PYTHON_EXE `
        -ArgumentList "-m fastapi run -e trade_alpha.api.main:app --port 8000" `
        -WorkingDirectory $BACKEND_DIR

    Write-Host "  Starting frontend..."
    Start-Process -WindowStyle Hidden -FilePath "$env:ComSpec" `
        -ArgumentList "/c npm run dev" `
        -WorkingDirectory $FRONTEND_DIR

    Write-Host "  Done"
}

Write-Host ""
Write-Host "trade-alpha Service Manager"
Write-Host "Action: $Action"
Write-Host ""

switch ($Action) {
    "stop" { Stop-Services }
    "start" { Start-Services }
    "restart" {
        Stop-Services
        Start-Services
    }
}
