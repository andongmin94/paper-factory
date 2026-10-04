param([string]$Python)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$venvRoot = Join-Path $projectRoot '.venv'
$venvPython = Join-Path $venvRoot 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if ($Python) {
        & $Python -m venv $venvRoot
    } elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
        & py.exe -3 -m venv $venvRoot
    } elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
        & python.exe -m venv $venvRoot
    } else {
        throw 'Install Python 3.11 or later, or supply -Python <python.exe>.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create the Python environment. Supply a working Python 3.11+ executable.' }
}

& $venvPython -m pip install -e "${projectRoot}[dev,pdf,research,automation]" -r (Join-Path $projectRoot 'scripts/research-runtime-requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
    Write-Host 'Python experiments are available; install Node.js 24+ for Node experiments.'
}
& $venvPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Python dependencies are inconsistent.' }
Write-Host 'Development environment ready: .venv/Scripts/python.exe -m paper_factory.cloud --help'
Write-Host 'The distributable plugin uses its own runtime in host-provided PLUGIN_DATA. Build it with python scripts/build_plugin.py.'
