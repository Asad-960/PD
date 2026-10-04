param([int]$FrontendPort = 3000, [int]$BackendPort = 8001)
$ErrorActionPreference = 'Stop'
$pdttRoot = Split-Path -Parent $PSScriptRoot
$pdttLogs = Join-Path $pdttRoot 'artifacts\rebuild'
New-Item -ItemType Directory -Force -Path $pdttLogs | Out-Null
$pdttPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $pdttPython)) { $pdttPython = (Get-Command python).Source }
$pdttNode = (Get-Command node).Source
foreach ($pdttPort in @($BackendPort, $FrontendPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $pdttPort -ErrorAction SilentlyContinue) {
        throw "Port $pdttPort is occupied. Choose another port; no existing server was stopped."
    }
}
$pdttBackend = Start-Process -FilePath $pdttPython -ArgumentList @('scripts/run_api.py', '--port', "$BackendPort") -WorkingDirectory $pdttRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $pdttLogs 'api.stdout.log') -RedirectStandardError (Join-Path $pdttLogs 'api.stderr.log') -PassThru
$env:PDTT_API_ORIGIN = "http://127.0.0.1:$BackendPort"
$pdttFrontend = Start-Process -FilePath $pdttNode -ArgumentList @('node_modules/next/dist/bin/next', 'dev', '--port', "$FrontendPort", '--hostname', '127.0.0.1') -WorkingDirectory (Join-Path $pdttRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $pdttLogs 'frontend.stdout.log') -RedirectStandardError (Join-Path $pdttLogs 'frontend.stderr.log') -PassThru
Write-Output "PDTT: http://localhost:$FrontendPort | API: http://127.0.0.1:$BackendPort | Processes: $($pdttFrontend.Id), $($pdttBackend.Id)"
