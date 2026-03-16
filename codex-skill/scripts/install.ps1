$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir

$codexHome = if ($env:CODEX_HOME) {
    $env:CODEX_HOME
} elseif ($env:USERPROFILE) {
    Join-Path $env:USERPROFILE ".codex"
} else {
    throw "CODEX_HOME is not set and USERPROFILE is unavailable."
}

$destRoot = Join-Path $codexHome "skills"
$destDir = Join-Path $destRoot "cli-anything"

New-Item -ItemType Directory -Path $destRoot -Force | Out-Null

if (Test-Path $destDir) {
    Write-Error "Refusing to overwrite existing skill: $destDir`nRemove it manually if you want to reinstall."
}

Copy-Item -Path $skillDir -Destination $destDir -Recurse

Write-Host "Installed Codex skill to: $destDir"
Write-Host "Restart Codex to pick up the new skill."
