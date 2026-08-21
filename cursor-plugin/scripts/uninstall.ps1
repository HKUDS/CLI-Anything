# Uninstall the CLI-Anything Cursor local plugin and clear the discovery pointer.
param(
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Usage: .\uninstall.ps1"
    Write-Host "Uninstall the CLI-Anything Cursor local plugin and clear the discovery pointer."
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "lib.ps1")

$pluginSrc = Split-Path -Parent $scriptDir
$discoveryPointer = Get-CliAnythingDiscoveryPointerPath

$stampFile = Join-Path $pluginSrc "PLUGIN_ROOT.txt"
$manifest = Join-Path $pluginSrc ".cursor-plugin\plugin.json"

if ((Test-Path -LiteralPath $stampFile) -and (Test-Path -LiteralPath $manifest)) {
    $destDir = [System.IO.Path]::GetFullPath($pluginSrc)
} else {
    if ($env:CURSOR_PLUGINS_HOME) {
        $pluginsHome = Resolve-CliAnythingPluginsHome -Raw $env:CURSOR_PLUGINS_HOME
    } elseif ($env:USERPROFILE) {
        $pluginsHome = Resolve-CliAnythingPluginsHome -Raw (Join-Path $env:USERPROFILE ".cursor\plugins")
    } else {
        throw "CURSOR_PLUGINS_HOME is not set and USERPROFILE is unavailable."
    }
    $destDir = [System.IO.Path]::GetFullPath((Join-Path $pluginsHome "local\cli-anything"))
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

Write-Host "Uninstall complete. Reload the Cursor window if it is open."
