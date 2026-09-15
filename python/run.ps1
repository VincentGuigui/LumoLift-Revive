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

$p = &{python -V} 2>&1
# check if an ErrorRecord was returned
$version = if($p -is [System.Management.Automation.ErrorRecord])
{
	& python -m lumolift
    exit $LASTEXITCODE
}

throw 'Python was not found. Install Python 3.12, then run: python -m pip install -r python\requirements.txt'
