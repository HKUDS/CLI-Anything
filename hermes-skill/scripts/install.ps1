# Install the CLI-Anything skill for Hermes Agent (Windows PowerShell).
#
# Vendors the canonical CLI-Anything resources into the installed skill so the
# installation is self-contained.
#
# Usage:
#   .\hermes-skill\scripts\install.ps1 [-Force] [-DryRun] [-Profile NAME] [-SkillDir DIR]
#
# Environment:
#   HERMES_HOME   Hermes home directory (default: $HOME\.hermes)

[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$DryRun,
    [string]$Profile,
    [string]$SkillDir
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillSource = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $skillSource
$pluginDir = Join-Path $repoRoot "cli-anything-plugin"
$previewProtocol = Join-Path $repoRoot "docs/PREVIEW_PROTOCOL.md"
$verifyScript = Join-Path $scriptDir "verify_harness.py"

$hermesHome = if ($env:HERMES_HOME) {
    $env:HERMES_HOME
} elseif ($env:USERPROFILE) {
    Join-Path $env:USERPROFILE ".hermes"
} else {
    throw "HERMES_HOME is not set and USERPROFILE is unavailable."
}

$destRoot = if ($SkillDir) {
    $SkillDir
} elseif ($Profile) {
    Join-Path $hermesHome "profiles/$Profile/skills"
} else {
    Join-Path $hermesHome "skills"
}
$destDir = Join-Path $destRoot "cli-anything-hermes"

function Fail([string]$message) {
    Write-Error $message
    exit 1
}

if (-not (Test-Path (Join-Path $pluginDir "HARNESS.md"))) {
    Fail "Cannot find canonical CLI-Anything resources at: $pluginDir`nRun this installer from a full CLI-Anything repository checkout."
}
if (-not (Test-Path $previewProtocol)) {
    Fail "Cannot find the preview protocol at: $previewProtocol`nRun this installer from a full CLI-Anything repository checkout."
}
if (-not (Test-Path $verifyScript)) {
    Fail "Cannot find the harness verifier at: $verifyScript"
}
if ((Test-Path $destDir) -and (-not $Force)) {
    Fail "$destDir already exists.`nRe-run with -Force to replace it, or remove it manually."
}

if ($DryRun) {
    Write-Host "Dry run - nothing was written."
    Write-Host "  skill source : $skillSource"
    Write-Host "  destination  : $destDir"
    Write-Host "  vendored from: $pluginDir, $previewProtocol"
    exit 0
}

New-Item -ItemType Directory -Path $destRoot -Force | Out-Null
$stagingDir = Join-Path $destRoot (".cli-anything-hermes.tmp." + [System.Guid]::NewGuid().ToString("N"))

try {
    New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null
    Copy-Item -Path (Join-Path $skillSource "*") -Destination $stagingDir -Recurse -Force

    $referencesDir = Join-Path $stagingDir "references"
    $scriptsDir = Join-Path $stagingDir "scripts"
    New-Item -ItemType Directory -Path (Join-Path $referencesDir "commands") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $referencesDir "docs") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $referencesDir "guides") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $scriptsDir "templates") -Force | Out-Null

    Copy-Item (Join-Path $pluginDir "HARNESS.md") (Join-Path $referencesDir "HARNESS.md") -Force
    Copy-Item (Join-Path $pluginDir "commands/*.md") (Join-Path $referencesDir "commands") -Force
    Copy-Item (Join-Path $pluginDir "guides/*.md") (Join-Path $referencesDir "guides") -Force
    Copy-Item (Join-Path $pluginDir "repl_skin.py") (Join-Path $scriptsDir "repl_skin.py") -Force
    Copy-Item (Join-Path $pluginDir "preview_bundle.py") (Join-Path $scriptsDir "preview_bundle.py") -Force
    Copy-Item (Join-Path $pluginDir "skill_generator.py") (Join-Path $scriptsDir "skill_generator.py") -Force
    Copy-Item (Join-Path $pluginDir "templates/*") (Join-Path $scriptsDir "templates") -Force
    Copy-Item $previewProtocol (Join-Path $referencesDir "docs/PREVIEW_PROTOCOL.md") -Force

    if (-not (Test-Path (Join-Path $stagingDir "SKILL.md"))) {
        Fail "Staged skill is missing SKILL.md"
    }
    $canonicalHash = (Get-FileHash (Join-Path $pluginDir "HARNESS.md") -Algorithm SHA256).Hash
    $vendoredHash = (Get-FileHash (Join-Path $referencesDir "HARNESS.md") -Algorithm SHA256).Hash
    if ($canonicalHash -ne $vendoredHash) {
        Fail "Vendored HARNESS.md does not match the canonical copy"
    }

    if (Test-Path $destDir) {
        Remove-Item -Path $destDir -Recurse -Force
    }
    Move-Item -Path $stagingDir -Destination $destDir
    $stagingDir = $null
}
finally {
    if ($stagingDir -and (Test-Path $stagingDir)) {
        Remove-Item -Path $stagingDir -Recurse -Force
    }
}

Write-Host "Installed the CLI-Anything skill to: $destDir"
Write-Host "Vendored HARNESS.md, command specs, guides, templates and helper modules."
Write-Host "Next: start a new Hermes session (the skill index is built at session start)."
Write-Host "Check any harness with: python $destDir\scripts\verify_harness.py <software-dir>"
