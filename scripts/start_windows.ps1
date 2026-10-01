param(
    [string]$EnvFile,
    [int]$Port = 8765,
    [string[]]$SourceRoot
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) { throw 'Run scripts/setup_windows.ps1 first.' }
$pandocJson = & $venvPython -c 'import json,pathlib,pypandoc; p=pathlib.Path(pypandoc.get_pandoc_path()); print(json.dumps(str(p if p.is_file() else p.with_suffix(".exe"))))'
if ($LASTEXITCODE -ne 0) { throw 'Pandoc is unavailable. Run scripts/setup_windows.ps1 again.' }
$env:PYPANDOC_PANDOC = $pandocJson | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $env:PYPANDOC_PANDOC -PathType Leaf)) { throw 'The installed Pandoc executable is missing. Run scripts/setup_windows.ps1 again.' }
$env:PYTHONUTF8 = '1'
$arguments = @('-m', 'paper_factory.cli')
if ($EnvFile) { $arguments += @('--env-file', $EnvFile) }
$arguments += @('serve', '--port', $Port)
foreach ($root in $SourceRoot) { $arguments += @('--source-root', $root) }
& $venvPython @arguments
exit $LASTEXITCODE
