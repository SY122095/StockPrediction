# dev.ps1 - バックエンド(FastAPI)とフロントエンド(Vite)を1つのウィンドウで起動する
#
# start.ps1 -Command all は別ウィンドウを2つ立ち上げる方式のため、
# 環境によってはウィンドウが見えない/すぐ閉じるなどで起動確認しづらいことがある。
# このスクリプトはバックエンドをバックグラウンドでログファイルに出力しつつ起動し、
# フロントエンドはこのウィンドウ内でそのまま動かす (Ctrl+C で両方停止)。
#
# 使い方: このウィンドウで直接実行してください (ダブルクリック不可、PowerShellから実行)
#   .\dev.ps1

$ErrorActionPreference = "Stop"
$Root     = $PSScriptRoot
$Backend  = Join-Path $Root "Application\backend"
$Frontend = Join-Path $Root "Application\frontend"
$PyExe    = Join-Path $Root ".venv\Scripts\python.exe"
$BackendLog    = Join-Path $Root "backend_dev.log"
$BackendErrLog = Join-Path $Root "backend_dev.err.log"

function Stop-Tree {
    param([int]$ProcId)
    # Stop-Process は子プロセス(ソケットハンドルを継承した multiprocessing 等)を
    # 道連れにしないため、プロセスツリーごと止める taskkill /T を使う。
    taskkill /F /T /PID $ProcId 2>$null | Out-Null
}

function Write-Step { param($msg) Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Err  { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Write-OK   { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }

# ---- 前提チェック ----
if (-not (Test-Path $PyExe)) {
    Write-Err "venv が見つかりません: $PyExe"
    Write-Host "先に実行してください: .\start.ps1 -Command setup"
    exit 1
}
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Step "node_modules が無いため npm install を実行します"
    Push-Location $Frontend
    npm install
    Pop-Location
}

# ---- ポート使用中チェック (前回の残プロセス、または別プロジェクトとの衝突を検出) ----
foreach ($port in 8000, 3000) {
    $inUse = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($inUse) {
        Write-Err "ポート $port は既に使用中です"
        foreach ($procId in ($inUse.OwningProcess | Select-Object -Unique)) {
            $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue).CommandLine
            Write-Host "  PID $procId : $cmdline"
        }
        Write-Host "`n  上記が本プロジェクト(StockPrediction)のものでない場合、"
        Write-Host "  別プロジェクトのサーバーがこのポートを使用中の可能性があります。"
        Write-Host "  そちらを停止するか、空いているポートを使ってください。"
        Write-Host "  本プロジェクトの残プロセスであれば (子プロセスも含めて停止):"
        foreach ($procId in ($inUse.OwningProcess | Select-Object -Unique)) {
            Write-Host "    taskkill /F /T /PID $procId"
        }
        exit 1
    }
}

# ---- バックエンド起動 (バックグラウンド, ログファイルへ出力) ----
Write-Step "バックエンド起動中... (ログ: $BackendLog)"
$backendProc = Start-Process -FilePath $PyExe `
    -ArgumentList "-m", "uvicorn", "main:app", "--port", "8000" `
    -WorkingDirectory $Backend `
    -RedirectStandardOutput $BackendLog `
    -RedirectStandardError $BackendErrLog `
    -WindowStyle Hidden `
    -PassThru

Write-Host "  PID: $($backendProc.Id)"

# ---- ヘルスチェック待機 (最大30秒) ----
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2
        $healthy = $true
        break
    } catch {
        if ($backendProc.HasExited) {
            Write-Err "バックエンドが起動直後に終了しました。ログを確認してください:"
            Write-Host "--- stdout ($BackendLog) ---"; Get-Content $BackendLog -ErrorAction SilentlyContinue -Tail 30
            Write-Host "--- stderr ($BackendErrLog) ---"; Get-Content $BackendErrLog -ErrorAction SilentlyContinue -Tail 30
            exit 1
        }
    }
}

if (-not $healthy) {
    Write-Err "バックエンドが30秒以内に起動しませんでした。ログを確認してください:"
    Write-Host "--- stdout ($BackendLog) ---"; Get-Content $BackendLog -ErrorAction SilentlyContinue -Tail 30
    Write-Host "--- stderr ($BackendErrLog) ---"; Get-Content $BackendErrLog -ErrorAction SilentlyContinue -Tail 30
    Stop-Tree $backendProc.Id
    exit 1
}

Write-OK "バックエンド起動完了: http://localhost:8000  (Swagger UI: http://localhost:8000/docs)"

# ---- 終了時にバックエンドも止める (子プロセスごと) ----
Register-EngineEvent PowerShell.Exiting -Action {
    Stop-Tree $backendProc.Id
} | Out-Null

Write-Step "フロントエンド起動中... (このウィンドウで直接実行, Ctrl+C で両方停止)"
Write-Host "  起動完了後、ブラウザで http://localhost:3000 を開いてください`n" -ForegroundColor Yellow

try {
    Push-Location $Frontend
    npm run dev
} finally {
    Pop-Location
    Write-Step "終了処理: バックエンド (PID $($backendProc.Id), 子プロセス含む) を停止します"
    Stop-Tree $backendProc.Id
}
