$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot 'python'
$localDependencies = Join-Path $projectRoot '.tools\pydeps'
$env:PYTHONPATH = "$pythonPath;$localDependencies"

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    & $pythonCommand.Source -m lumolift
    exit $LASTEXITCODE
}

$bundledPython = 'C:\Users\vince\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $bundledPython) {
    & $bundledPython -m lumolift
    exit $LASTEXITCODE
}

throw 'Python was not found. Install Python 3.12, then run: python -m pip install -r python\requirements.txt'
