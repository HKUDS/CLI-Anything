# Install the CLI-Anything Cursor plugin with vendored methodology resources.
param(
    [switch]$Force,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Usage: .\install.ps1 [-Force]"
    Write-Host "Install the CLI-Anything Cursor plugin with vendored methodology resources."
    Write-Host "Destination: `$env:CURSOR_PLUGINS_HOME\local\cli-anything (default: %USERPROFILE%\.cursor\plugins\local\cli-anything)"
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "lib.ps1")

$pluginSrc = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $pluginSrc
$canonicalPlugin = Join-Path $repoRoot "cli-anything-plugin"
$previewProtocol = Join-Path $repoRoot "docs\PREVIEW_PROTOCOL.md"

if ($env:CURSOR_PLUGINS_HOME) {
    $pluginsHome = Resolve-CliAnythingPluginsHome -Raw $env:CURSOR_PLUGINS_HOME -Create
} elseif ($env:USERPROFILE) {
    $pluginsHome = Resolve-CliAnythingPluginsHome -Raw (Join-Path $env:USERPROFILE ".cursor\plugins") -Create
} else {
    throw "CURSOR_PLUGINS_HOME is not set and USERPROFILE is unavailable."
}

$discoveryPointer = Get-CliAnythingDiscoveryPointerPath
$userCursor = Split-Path -Parent $discoveryPointer
$destRoot = Join-Path $pluginsHome "local"
$destDir = Join-Path $destRoot "cli-anything"
$stagingDir = $null
$backupDir = $null

if (-not (Test-Path (Join-Path $canonicalPlugin "HARNESS.md"))) {
    throw "Cannot find canonical CLI-Anything resources at: $canonicalPlugin`nRun this installer from a full CLI-Anything repository checkout."
}

if (-not (Test-Path $previewProtocol)) {
    throw "Cannot find preview protocol at: $previewProtocol`nRun this installer from a full CLI-Anything repository checkout."
}

if (-not (Test-Path (Join-Path $pluginSrc ".cursor-plugin\plugin.json"))) {
    throw "Cannot find Cursor plugin manifest at: $(Join-Path $pluginSrc '.cursor-plugin\plugin.json')"
}

New-Item -ItemType Directory -Path $destRoot -Force | Out-Null
New-Item -ItemType Directory -Path $userCursor -Force | Out-Null

if (Test-Path $destDir) {
    if (-not $Force) {
        throw "Refusing to overwrite existing plugin: $destDir`nRe-run with -Force to upgrade, or remove it manually."
    }
}

try {
    $stagingDir = Join-Path $destRoot (".cli-anything.tmp." + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $stagingDir | Out-Null

    Get-ChildItem -LiteralPath $pluginSrc -Force | ForEach-Object {
        if ($_.Name -in @("tests", "references", ".git")) {
            return
        }
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $stagingDir $_.Name) -Recurse -Force
    }

    $referenceDir = Join-Path $stagingDir "references"
    $referenceCommands = Join-Path $referenceDir "commands"
    $referenceDocs = Join-Path $referenceDir "docs"
    $referenceGuides = Join-Path $referenceDir "guides"
    $resourceScripts = Join-Path $stagingDir "scripts"
    $scriptTemplates = Join-Path $resourceScripts "templates"

    New-Item -ItemType Directory -Path $referenceCommands, $referenceDocs, $referenceGuides, $scriptTemplates -Force | Out-Null

    Copy-Item -Path (Join-Path $canonicalPlugin "HARNESS.md") -Destination (Join-Path $referenceDir "HARNESS.md")
    Copy-Item -Path (Join-Path $canonicalPlugin "commands\*.md") -Destination $referenceCommands
    Copy-Item -Path (Join-Path $canonicalPlugin "guides\*.md") -Destination $referenceGuides
    Copy-Item -Path (Join-Path $canonicalPlugin "repl_skin.py") -Destination (Join-Path $resourceScripts "repl_skin.py")
    Copy-Item -Path (Join-Path $canonicalPlugin "preview_bundle.py") -Destination (Join-Path $resourceScripts "preview_bundle.py")
    Copy-Item -Path (Join-Path $canonicalPlugin "skill_generator.py") -Destination (Join-Path $resourceScripts "skill_generator.py")
    Copy-Item -Path (Join-Path $canonicalPlugin "templates\*") -Destination $scriptTemplates
    Copy-Item -Path $previewProtocol -Destination (Join-Path $referenceDocs "PREVIEW_PROTOCOL.md")

    # If interrupted after moving the old install aside, look for
    # $destRoot\.cli-anything.bak.* and restore it manually.
    if (Test-Path $destDir) {
        $backupDir = Join-Path $destRoot (".cli-anything.bak." + [System.Guid]::NewGuid().ToString("N"))
        Move-Item -LiteralPath $destDir -Destination $backupDir
        try {
            Move-Item -LiteralPath $stagingDir -Destination $destDir
            $stagingDir = $null
            Remove-Item -LiteralPath $backupDir -Recurse -Force
            $backupDir = $null
        } catch {
            if ($backupDir -and (Test-Path $backupDir)) {
                Move-Item -LiteralPath $backupDir -Destination $destDir -Force
            }
            throw
        }
    } else {
        Move-Item -LiteralPath $stagingDir -Destination $destDir
        $stagingDir = $null
    }
} finally {
    if ($stagingDir -and (Test-Path $stagingDir)) {
        Remove-Item -LiteralPath $stagingDir -Recurse -Force
    }
}

$pluginRoot = [System.IO.Path]::GetFullPath($destDir)
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Join-Path $pluginRoot "PLUGIN_ROOT.txt"), ($pluginRoot + [Environment]::NewLine), $utf8NoBom)
[System.IO.File]::WriteAllText($discoveryPointer, ($pluginRoot + [Environment]::NewLine), $utf8NoBom)

Write-Host "Installed Cursor plugin to: $pluginRoot"
Write-Host "Wrote PLUGIN_ROOT stamp and discovery pointer: $discoveryPointer"
Write-Host "Vendored CLI-Anything methodology resources into the installed plugin."
Write-Host "Reload the Cursor window (Developer: Reload Window) to pick up commands."
Write-Host "Consumer Hub/skills are separate: npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y"
