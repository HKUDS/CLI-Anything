$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $skillDir
$pluginDir = Join-Path $repoRoot "cli-anything-plugin"
$previewProtocol = Join-Path $repoRoot "docs/PREVIEW_PROTOCOL.md"

$codexHome = if ($env:CODEX_HOME) {
    $env:CODEX_HOME
} elseif ($env:USERPROFILE) {
    Join-Path $env:USERPROFILE ".codex"
} else {
    throw "CODEX_HOME is not set and USERPROFILE is unavailable."
}

$destRoot = Join-Path $codexHome "skills"
$destDir = Join-Path $destRoot "cli-anything"
$stagingDir = $null

if (-not (Test-Path (Join-Path $pluginDir "HARNESS.md"))) {
    throw "Cannot find canonical CLI-Anything resources at: $pluginDir`nRun this installer from a full CLI-Anything repository checkout."
}

if (-not (Test-Path $previewProtocol)) {
    throw "Cannot find preview protocol at: $previewProtocol`nRun this installer from a full CLI-Anything repository checkout."
}

New-Item -ItemType Directory -Path $destRoot -Force | Out-Null

if (Test-Path $destDir) {
    throw "Refusing to overwrite existing skill: $destDir`nRemove it manually if you want to reinstall."
}

try {
    $stagingDir = Join-Path $destRoot (".cli-anything.tmp." + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $stagingDir | Out-Null
    Get-ChildItem -LiteralPath $skillDir -Force | Copy-Item -Destination $stagingDir -Recurse -Force

    $referenceDir = Join-Path $stagingDir "references"
    $referenceCommands = Join-Path $referenceDir "commands"
    $referenceDocs = Join-Path $referenceDir "docs"
    $referenceGuides = Join-Path $referenceDir "guides"
    $resourceScripts = Join-Path $stagingDir "scripts"
    $scriptTemplates = Join-Path $resourceScripts "templates"

    New-Item -ItemType Directory -Path $referenceCommands, $referenceDocs, $referenceGuides, $scriptTemplates -Force | Out-Null

    Copy-Item -Path (Join-Path $pluginDir "HARNESS.md") -Destination (Join-Path $referenceDir "HARNESS.md")
    Copy-Item -Path (Join-Path $pluginDir "commands/*.md") -Destination $referenceCommands
    Copy-Item -Path (Join-Path $pluginDir "guides/*.md") -Destination $referenceGuides
    Copy-Item -Path (Join-Path $pluginDir "repl_skin.py") -Destination (Join-Path $resourceScripts "repl_skin.py")
    Copy-Item -Path (Join-Path $pluginDir "preview_bundle.py") -Destination (Join-Path $resourceScripts "preview_bundle.py")
    Copy-Item -Path (Join-Path $pluginDir "skill_generator.py") -Destination (Join-Path $resourceScripts "skill_generator.py")
    Copy-Item -Path (Join-Path $pluginDir "templates/*") -Destination $scriptTemplates
    Copy-Item -Path $previewProtocol -Destination (Join-Path $referenceDocs "PREVIEW_PROTOCOL.md")

    Move-Item -Path $stagingDir -Destination $destDir
} finally {
    if ($stagingDir -and (Test-Path $stagingDir)) {
        Remove-Item -Path $stagingDir -Recurse -Force
    }
}

Write-Host "Installed Codex skill to: $destDir"
Write-Host "Vendored CLI-Anything methodology resources into the installed skill."
Write-Host "Restart Codex to pick up the new skill."
