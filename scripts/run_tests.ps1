param([string]$PythonExecutable = '')
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
if (-not $PythonExecutable) {
    $projectPython = Join-Path $projectDirectory '.venv\Scripts\python.exe'
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $projectPython) { $PythonExecutable = $projectPython }
    elseif (Test-Path -LiteralPath $bundledPython) { $PythonExecutable = $bundledPython }
    else { throw 'Supply -PythonExecutable with a working Python interpreter.' }
}
Push-Location -LiteralPath $projectDirectory
try {
    $previousPythonPath = $env:PYTHONPATH
    $auditDeps = Join-Path $projectDirectory '.audit-deps'
    if (Test-Path -LiteralPath $auditDeps) { $env:PYTHONPATH = "$auditDeps;$previousPythonPath" }
    & $PythonExecutable -m pytest --basetemp=artifacts/implementation/local-tests-tmp --junitxml=artifacts/implementation/local-tests.xml
    $testExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
exit $testExitCode
