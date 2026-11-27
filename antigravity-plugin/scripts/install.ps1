# Install the CLI-Anything Google Antigravity plugin with vendored methodology resources.
param(
    [switch]$Force,
    [switch]$DryRun,
    [string]$Workspace,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Usage: .\install.ps1 [-Force] [-DryRun] [-Workspace <path>]"
    Write-Host "Install the CLI-Anything Google Antigravity plugin with vendored methodology resources."
    Write-Host "Global destination:    `$env:ANTIGRAVITY_PLUGINS_HOME\cli-anything (default: %USERPROFILE%\.gemini\config\plugins\cli-anything)"
    Write-Host "Workspace destination: <workspace>\.agents\plugins\cli-anything"
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "lib.ps1")

$pluginSrc = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $pluginSrc
$canonicalPlugin = Join-Path $repoRoot "cli-anything-plugin"
$previewProtocol = Join-Path $repoRoot "docs\PREVIEW_PROTOCOL.md"

if (-not (Test-Path -LiteralPath (Join-Path $canonicalPlugin "HARNESS.md"))) {
    throw "Cannot find canonical CLI-Anything resources at: $canonicalPlugin`nRun this installer from a full CLI-Anything repository checkout."
}

if (-not (Test-Path -LiteralPath $previewProtocol)) {
    throw "Cannot find preview protocol at: $previewProtocol`nRun this installer from a full CLI-Anything repository checkout."
}

if (-not (Test-Path -LiteralPath (Join-Path $pluginSrc "plugin.json"))) {
    throw "Cannot find Antigravity plugin manifest at: $(Join-Path $pluginSrc 'plugin.json')"
}

$isGlobal = $true
if (-not [string]::IsNullOrWhiteSpace($Workspace)) {
    $isGlobal = $false
    $wsRoot = Resolve-CliAnythingWorkspaceRoot -Raw $Workspace
    $pluginsHome = Join-Path $wsRoot ".agents\plugins"
    if (-not $DryRun) {
        New-Item -ItemType Directory -Path $pluginsHome -Force | Out-Null
    }
} else {
    $createSwitch = -not $DryRun
    if ($env:ANTIGRAVITY_PLUGINS_HOME) {
        $pluginsHome = Resolve-CliAnythingPluginsHome -Raw $env:ANTIGRAVITY_PLUGINS_HOME -Create:$createSwitch
    } elseif ($env:USERPROFILE) {
        $pluginsHome = Resolve-CliAnythingPluginsHome -Raw (Join-Path $env:USERPROFILE ".gemini\config\plugins") -Create:$createSwitch
    } elseif ($env:HOME) {
        $pluginsHome = Resolve-CliAnythingPluginsHome -Raw (Join-Path $env:HOME ".gemini\config\plugins") -Create:$createSwitch
    } else {
        throw "ANTIGRAVITY_PLUGINS_HOME is not set and USERPROFILE/HOME is unavailable."
    }
}

$discoveryPointer = Get-CliAnythingDiscoveryPointerPath
$destDir = Join-Path $pluginsHome "cli-anything"

if ($DryRun) {
    Write-Host "[dry-run] Source adapter:     $pluginSrc"
    Write-Host "[dry-run] Canonical plugin:   $canonicalPlugin"
    Write-Host "[dry-run] Preview protocol:   $previewProtocol"
    Write-Host "[dry-run] Destination:        $destDir"
    if ($isGlobal) {
        Write-Host "[dry-run] Discovery pointer:  $discoveryPointer"
    } else {
        Write-Host "[dry-run] Discovery pointer:  (unchanged for workspace install)"
    }
    if ((Test-Path -LiteralPath $destDir) -and (-not $Force)) {
        Write-Host "[dry-run] Note: destination exists; real run would require -Force."
    }
    exit 0
}

$srcKey = Normalize-CliAnythingPathKey (Resolve-CliAnythingRealPath -Path $pluginSrc)
$destCheckKey = Normalize-CliAnythingPathKey (Resolve-CliAnythingRealPath -Path $destDir)
if (($srcKey -eq $destCheckKey) -or $srcKey.StartsWith("$destCheckKey\")) {
    throw "Refusing to install into source directory or an ancestor of it: $destDir"
}

$lockPath = Join-Path $pluginsHome ".cli-anything.lock"
$lockHandle = $null
$stagingDir = $null
$backupDir = $null

function Assert-StagedSameFile([string]$Src, [string]$Dst) {
    $h1 = (Get-FileHash -LiteralPath $Src -Algorithm SHA256).Hash
    $h2 = (Get-FileHash -LiteralPath $Dst -Algorithm SHA256).Hash
    if ($h1 -ne $h2) {
        throw "Staged integrity check failed (hash mismatch): $Dst"
    }
}

try {
    $lockHandle = Acquire-CliAnythingInstallLock -LockPath $lockPath

    if ((Test-Path -LiteralPath $destDir) -and (-not $Force)) {
        throw "Refusing to overwrite existing plugin: $destDir`nRe-run with -Force to upgrade, or remove it manually."
    }

    $stagingDir = Join-Path $pluginsHome (".cli-anything.tmp." + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $stagingDir | Out-Null
    $pluginsHomeKey = Normalize-CliAnythingPathKey (Resolve-CliAnythingRealPath -Path $pluginsHome)
    $lockKey = Normalize-CliAnythingPathKey (Resolve-CliAnythingRealPath -Path $lockPath)
    $stagingKey = Normalize-CliAnythingPathKey (Resolve-CliAnythingRealPath -Path $stagingDir)
    $destKey = Normalize-CliAnythingPathKey (Resolve-CliAnythingRealPath -Path $destDir)

    function Copy-PluginTree {
        param(
            [Parameter(Mandatory = $true)][string]$SrcDir,
            [Parameter(Mandatory = $true)][string]$DstDir,
            [bool]$IsRoot = $false
        )
        New-Item -ItemType Directory -Path $DstDir -Force | Out-Null
        $excludedNames = if ($IsRoot) {
            @("tests", "references", ".git", ".agents", "__pycache__")
        } else {
            @(".git", ".agents", "__pycache__")
        }
        Get-ChildItem -LiteralPath $SrcDir -Force | ForEach-Object {
            if ($_.Name -in $excludedNames) {
                return
            }
            $entryKey = Normalize-CliAnythingPathKey (Resolve-CliAnythingRealPath -Path $_.FullName)
            if (
                ($entryKey -eq $pluginsHomeKey) -or
                ($entryKey -eq $stagingKey) -or
                ($entryKey -eq $destKey) -or
                ($entryKey -eq $lockKey)
            ) {
                return
            }
            $entryPrefix = "$entryKey\"
            if (
                $_.PSIsContainer -and (
                    $pluginsHomeKey.StartsWith($entryPrefix) -or
                    $stagingKey.StartsWith($entryPrefix) -or
                    $destKey.StartsWith($entryPrefix) -or
                    $lockKey.StartsWith($entryPrefix)
                )
            ) {
                Copy-PluginTree -SrcDir $_.FullName -DstDir (Join-Path $DstDir $_.Name) -IsRoot $false
                return
            }
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $DstDir $_.Name) -Recurse -Force
        }
    }

    Copy-PluginTree -SrcDir $pluginSrc -DstDir $stagingDir -IsRoot $true

    $referenceDir = Join-Path $stagingDir "references"
    $referenceCommands = Join-Path $referenceDir "commands"
    $referenceDocs = Join-Path $referenceDir "docs"
    $referenceGuides = Join-Path $referenceDir "guides"
    $resourceScripts = Join-Path $stagingDir "scripts"
    $scriptTemplates = Join-Path $resourceScripts "templates"

    New-Item -ItemType Directory -Path $referenceCommands, $referenceDocs, $referenceGuides, $scriptTemplates -Force | Out-Null

    $toolingSrc = Join-Path $pluginSrc "references\antigravity-tooling.md"
    if (Test-Path -LiteralPath $toolingSrc) {
        Copy-Item -LiteralPath $toolingSrc -Destination (Join-Path $referenceDir "antigravity-tooling.md")
    }

    Copy-Item -Path (Join-Path $canonicalPlugin "HARNESS.md") -Destination (Join-Path $referenceDir "HARNESS.md")
    Copy-Item -Path (Join-Path $canonicalPlugin "commands\*.md") -Destination $referenceCommands
    Copy-Item -Path (Join-Path $canonicalPlugin "guides\*.md") -Destination $referenceGuides
    Copy-Item -Path (Join-Path $canonicalPlugin "repl_skin.py") -Destination (Join-Path $resourceScripts "repl_skin.py")
    Copy-Item -Path (Join-Path $canonicalPlugin "preview_bundle.py") -Destination (Join-Path $resourceScripts "preview_bundle.py")
    Copy-Item -Path (Join-Path $canonicalPlugin "skill_generator.py") -Destination (Join-Path $resourceScripts "skill_generator.py")
    Copy-Item -Path (Join-Path $canonicalPlugin "templates\*") -Destination $scriptTemplates
    Copy-Item -Path $previewProtocol -Destination (Join-Path $referenceDocs "PREVIEW_PROTOCOL.md")

    # Pre-publish integrity check (required files + hash equality + Python bytecode compilation without writing __pycache__).
    $requiredStaged = @(
        "plugin.json",
        "hooks.json",
        "rules\cli-anything-generator.md",
        "agents\cli-anything-auditor.md",
        "skills\cli-anything\SKILL.md",
        "skills\cli-anything-refine\SKILL.md",
        "skills\cli-anything-test\SKILL.md",
        "skills\cli-anything-validate\SKILL.md",
        "skills\cli-anything-list\SKILL.md",
        "references\HARNESS.md",
        "references\docs\PREVIEW_PROTOCOL.md",
        "scripts\verify_harness.py",
        "scripts\list_harnesses.py",
        "scripts\pep420_guard.py",
        "scripts\_toml_fallback.py",
        "scripts\repl_skin.py",
        "scripts\preview_bundle.py",
        "scripts\skill_generator.py"
    )
    foreach ($reqStaged in $requiredStaged) {
        if (-not (Test-Path -LiteralPath (Join-Path $stagingDir $reqStaged) -PathType Leaf)) {
            throw "Staged plugin is missing required file: $reqStaged"
        }
    }
    Assert-StagedSameFile (Join-Path $canonicalPlugin "HARNESS.md") (Join-Path $referenceDir "HARNESS.md")
    Assert-StagedSameFile (Join-Path $canonicalPlugin "repl_skin.py") (Join-Path $resourceScripts "repl_skin.py")
    Assert-StagedSameFile (Join-Path $canonicalPlugin "preview_bundle.py") (Join-Path $resourceScripts "preview_bundle.py")
    Assert-StagedSameFile (Join-Path $canonicalPlugin "skill_generator.py") (Join-Path $resourceScripts "skill_generator.py")
    Assert-StagedSameFile $previewProtocol (Join-Path $referenceDocs "PREVIEW_PROTOCOL.md")

    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
    if ($py) {
        & $py.Source -B -m py_compile `
            (Join-Path $resourceScripts "repl_skin.py") `
            (Join-Path $resourceScripts "preview_bundle.py") `
            (Join-Path $resourceScripts "skill_generator.py") `
            (Join-Path $resourceScripts "_toml_fallback.py") `
            (Join-Path $resourceScripts "verify_harness.py") `
            (Join-Path $resourceScripts "list_harnesses.py") `
            (Join-Path $resourceScripts "pep420_guard.py")
        if ($LASTEXITCODE -ne 0) {
            throw "Pre-publish py_compile failed for staged plugin scripts."
        }
    }

    # Atomic replace when upgrading.
    if (Test-Path -LiteralPath $destDir) {
        $backupDir = Join-Path $pluginsHome (".cli-anything.bak." + [System.Guid]::NewGuid().ToString("N"))
        Move-Item -LiteralPath $destDir -Destination $backupDir
        try {
            Move-Item -LiteralPath $stagingDir -Destination $destDir
            $stagingDir = $null
            Remove-Item -LiteralPath $backupDir -Recurse -Force
            $backupDir = $null
        } catch {
            if ($backupDir -and (Test-Path -LiteralPath $backupDir)) {
                Move-Item -LiteralPath $backupDir -Destination $destDir -Force
            }
            throw
        }
    } else {
        Move-Item -LiteralPath $stagingDir -Destination $destDir
        $stagingDir = $null
    }

    $pluginRoot = [System.IO.Path]::GetFullPath($destDir)
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText((Join-Path $pluginRoot "PLUGIN_ROOT.txt"), ($pluginRoot + [Environment]::NewLine), $utf8NoBom)

    if ($isGlobal) {
        Write-CliAnythingDiscoveryPointer -PointerPath $discoveryPointer -Value $pluginRoot
    }
} finally {
    if ($stagingDir -and (Test-Path -LiteralPath $stagingDir)) {
        Remove-Item -LiteralPath $stagingDir -Recurse -Force
    }
    Release-CliAnythingInstallLock -LockHandle $lockHandle -LockPath $lockPath
}

Write-Host "Installed Antigravity plugin to: $pluginRoot"
if ($isGlobal) {
    Write-Host "Wrote PLUGIN_ROOT stamp and discovery pointer: $discoveryPointer"
} else {
    Write-Host "Wrote PLUGIN_ROOT stamp (workspace-scoped install; global discovery pointer unchanged)."
}
Write-Host "Vendored CLI-Anything methodology resources and verified staged scripts."
Write-Host "Slash commands ready on next turn: /cli-anything, /cli-anything-refine, /cli-anything-test, /cli-anything-validate, /cli-anything-list"
Write-Host "Consumer Hub/skills are separate: npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y"
