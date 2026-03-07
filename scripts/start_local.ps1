param(
    [string]$Python = "python",
    [switch]$SkipInstall,
    [switch]$Reload,
    [switch]$KillPort,
    [switch]$ResetDb
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RootDir

$listeners = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
if ($listeners.Count -gt 0) {
    if ($KillPort) {
        foreach ($pid in $listeners) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "[precheck] Stopped process on :8000, pid=$pid"
        }
    } else {
        Write-Host "[precheck] Port 8000 is already in use by PID(s): $($listeners -join ', ')"
        Write-Host "[precheck] Re-run with -KillPort, or stop those processes manually."
        exit 1
    }
}

if (-not $SkipInstall) {
    Write-Host "[1/3] Installing dependencies..."
    & $Python -m pip install -r requirements.txt
}

if ($ResetDb) {
    Write-Host "[2/3] Rebuilding SQLite database (drop + sample)..."
    & $Python scripts/init_db.py --drop --sample
} else {
    Write-Host "[2/3] Ensuring database tables exist (keep existing data)..."
    & $Python scripts/init_db.py
}

if ($Reload) {
    Write-Host "[3/3] Starting app on http://0.0.0.0:8000 (reload mode)..."
    & $Python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
} else {
    Write-Host "[3/3] Starting app on http://0.0.0.0:8000 (stable mode)..."
    & $Python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
}
