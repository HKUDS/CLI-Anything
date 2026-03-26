param(
    [Parameter(Mandatory = $false)]
    [string]$RepoRoot = $env:CLI_ANYTHING_REPO
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir

if (-not $RepoRoot -or [string]::IsNullOrWhiteSpace($RepoRoot)) {
    throw "Provide -RepoRoot or set CLI_ANYTHING_REPO."
}

$RepoRoot = (Resolve-Path $RepoRoot).Path

$sources = @{
    "HARNESS"       = Join-Path $RepoRoot "cli-anything-plugin\\HARNESS.md"
    "REPL"          = Join-Path $RepoRoot "cli-anything-plugin\\repl_skin.py"
    "GENERATOR"     = Join-Path $RepoRoot "cli-anything-plugin\\skill_generator.py"
    "TEMPLATE"      = Join-Path $RepoRoot "cli-anything-plugin\\templates\\SKILL.md.template"
    "OPENAI_YAML"   = Join-Path $RepoRoot "codex-skill\\agents\\openai.yaml"
    "INSTALL_PS1"   = Join-Path $RepoRoot "codex-skill\\scripts\\install.ps1"
    "INSTALL_SH"    = Join-Path $RepoRoot "codex-skill\\scripts\\install.sh"
}

foreach ($entry in $sources.GetEnumerator()) {
    if (-not (Test-Path $entry.Value)) {
        throw "Missing required source file for $($entry.Key): $($entry.Value)"
    }
}

$targets = @{
    $sources["HARNESS"]     = Join-Path $skillDir "references\\HARNESS.md"
    $sources["REPL"]        = Join-Path $skillDir "assets\\cli_anything_plugin\\repl_skin.py"
    $sources["GENERATOR"]   = Join-Path $skillDir "assets\\cli_anything_plugin\\skill_generator.py"
    $sources["TEMPLATE"]    = Join-Path $skillDir "assets\\cli_anything_plugin\\templates\\SKILL.md.template"
    $sources["OPENAI_YAML"] = Join-Path $skillDir "agents\\openai.yaml"
    $sources["INSTALL_PS1"] = Join-Path $skillDir "scripts\\install.ps1"
    $sources["INSTALL_SH"]  = Join-Path $skillDir "scripts\\install.sh"
}

foreach ($target in $targets.Values) {
    $parent = Split-Path -Parent $target
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
}

foreach ($pair in $targets.GetEnumerator()) {
    Copy-Item $pair.Key $pair.Value -Force
    Write-Host ("Synced: {0}" -f $pair.Value)
}

Write-Host "Sync complete."
