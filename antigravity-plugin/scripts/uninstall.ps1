# Uninstall the CLI-Anything Google Antigravity plugin and clear the matching discovery pointer.
param(
    [string]$Workspace,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Usage: .\uninstall.ps1 [-Workspace <path>]"
    Write-Host "Uninstall the CLI-Anything Google Antigravity plugin and clear the matching discovery pointer."
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "lib.ps1")

$pluginSrc = Split-Path -Parent $scriptDir
$discoveryPointer = Get-CliAnythingDiscoveryPointerPath

$stampFile = Join-Path $pluginSrc "PLUGIN_ROOT.txt"
$manifest = Join-Path $pluginSrc "plugin.json"

if (-not [string]::IsNullOrWhiteSpace($Workspace)) {
    $wsRoot = Resolve-CliAnythingWorkspaceRoot -Raw $Workspace
    $destDir = [System.IO.Path]::GetFullPath((Join-Path $wsRoot ".agents\plugins\cli-anything"))
} elseif ((Test-Path -LiteralPath $stampFile) -and (Test-Path -LiteralPath $manifest)) {
    $destDir = [System.IO.Path]::GetFullPath($pluginSrc)
} else {
    if ($env:ANTIGRAVITY_PLUGINS_HOME) {
        $pluginsHome = Resolve-CliAnythingPluginsHome -Raw $env:ANTIGRAVITY_PLUGINS_HOME
    } elseif ($env:USERPROFILE) {
        $pluginsHome = Resolve-CliAnythingPluginsHome -Raw (Join-Path $env:USERPROFILE ".gemini\config\plugins")
    } elseif ($env:HOME) {
        $pluginsHome = Resolve-CliAnythingPluginsHome -Raw (Join-Path $env:HOME ".gemini\config\plugins")
    } else {
        throw "ANTIGRAVITY_PLUGINS_HOME is not set and USERPROFILE/HOME is unavailable."
    }
    $destDir = [System.IO.Path]::GetFullPath((Join-Path $pluginsHome "cli-anything"))
}

if (-not (Test-CliAnythingInstallPath -Path $destDir)) {
    throw "Refusing to uninstall unexpected path: $destDir"
}

if (Test-Path -LiteralPath $destDir) {
    Remove-Item -LiteralPath $destDir -Recurse -Force
    Write-Host "Removed plugin directory: $destDir"
} else {
    Write-Host "Plugin directory not found (already removed): $destDir"
}

if (Test-Path -LiteralPath $discoveryPointer) {
    $pointer = (Get-Content -LiteralPath $discoveryPointer -Raw).Trim()
    $ptrNorm = Normalize-CliAnythingPathKey $pointer
    $destNorm = Normalize-CliAnythingPathKey $destDir
    if ($ptrNorm -eq $destNorm) {
        Remove-Item -LiteralPath $discoveryPointer -Force
        Write-Host "Removed discovery pointer: $discoveryPointer"
    } else {
        Write-Host "Left discovery pointer unchanged (points elsewhere): $pointer"
    }
} else {
    Write-Host "Discovery pointer not present: $discoveryPointer"
}

Write-Host "Uninstall complete."
