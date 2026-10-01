param([string]$Python)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$venvRoot = Join-Path $projectRoot '.venv'
$venvPython = Join-Path $venvRoot 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if ($Python) {
        & $Python -m venv $venvRoot
    } elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
        & py.exe -3.12 -m venv $venvRoot
    } elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
        & python.exe -m venv $venvRoot
    } else {
        throw 'Install Python 3.12 or supply -Python <python.exe>.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create the Python environment. Supply a working Python 3.12 executable.' }
}

& $venvPython -m pip install -e "${projectRoot}[dev,pdf,research,automation]" pypandoc_binary -r (Join-Path $projectRoot 'scripts/research-runtime-requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) { throw 'Install Node.js 24 with npm before running Windows automatic research.' }
& $npm.Source install --prefix (Join-Path $venvRoot 'codex') --no-audit --no-fund '@openai/codex@0.159.3'
if ($LASTEXITCODE -ne 0) { throw 'The private official Codex CLI installation failed.' }
& $venvPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Python dependencies are inconsistent.' }
Write-Host 'Windows setup is ready. Run scripts/start_windows.ps1 to open the research workspace.'
