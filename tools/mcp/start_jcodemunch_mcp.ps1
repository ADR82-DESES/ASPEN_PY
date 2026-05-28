$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot ".pixi\envs\default\python.exe"
$sourceRoot = Join-Path $repoRoot "third_party\jcodemunch-mcp\src"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Pixi Python interpreter not found at $python. Run 'pixi install' from the repo root first."
}

if (-not (Test-Path -LiteralPath $sourceRoot)) {
    throw "jCodeMunch source tree not found at $sourceRoot. Clone or restore third_party/jcodemunch-mcp first."
}

if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $sourceRoot
} else {
    $env:PYTHONPATH = "$sourceRoot;$($env:PYTHONPATH)"
}

if ([string]::IsNullOrWhiteSpace($env:CODE_INDEX_PATH)) {
    $env:CODE_INDEX_PATH = Join-Path $repoRoot ".jcodemunch-cache"
}

& $python -m jcodemunch_mcp.server
exit $LASTEXITCODE
