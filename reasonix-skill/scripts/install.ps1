$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir

$reasonixHome = if ($env:USERPROFILE) {
    Join-Path $env:USERPROFILE ".reasonix"
} else {
    throw "USERPROFILE is unavailable."
}

$destRoot = Join-Path $reasonixHome "skills"
$destDir = Join-Path $destRoot "cli-anything"

New-Item -ItemType Directory -Path $destRoot -Force | Out-Null

if (Test-Path $destDir) {
    Write-Error "Refusing to overwrite existing skill: $destDir`nRemove it manually if you want to reinstall."
}

Copy-Item -Path $skillDir -Destination $destDir -Recurse

Write-Host "Installed Reasonix skill to: $destDir"
Write-Host "Restart Reasonix to pick up the new skill."
