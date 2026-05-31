$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir

$hermesHome = if ($env:HERMES_HOME) {
    $env:HERMES_HOME
} elseif ($env:USERPROFILE) {
    Join-Path $env:USERPROFILE ".hermes"
} else {
    throw "HERMES_HOME is not set and USERPROFILE is unavailable."
}

$destRoot = Join-Path $hermesHome "skills"
$destDir = Join-Path $destRoot "cli-anything-hermes"

New-Item -ItemType Directory -Path $destRoot -Force | Out-Null

if (Test-Path $destDir) {
    Write-Error "Refusing to overwrite existing skill: $destDir`nRemove it manually if you want to reinstall."
}

Copy-Item -Path $skillDir -Destination $destDir -Recurse

Write-Host "Installed Hermes skill to: $destDir"
Write-Host "Restart Hermes Agent to pick up the new skill."
