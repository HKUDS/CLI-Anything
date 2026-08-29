# Regression tests for the Cursor plugin installer (Windows).
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pluginSrc = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $pluginSrc
$canonicalPlugin = Join-Path $repoRoot "cli-anything-plugin"
$previewProtocol = Join-Path $repoRoot "docs\PREVIEW_PROTOCOL.md"

$tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("cli-anything-cursor-test-" + [System.Guid]::NewGuid().ToString("N"))
$userHome = Join-Path $tmpDir "home"
$pluginsHome = Join-Path $tmpDir "plugins"
$installedDir = Join-Path $pluginsHome "local\cli-anything"
$staleStaging = Join-Path $pluginsHome "local\.cli-anything.tmp.stale"
$discoveryPointer = Join-Path $userHome ".cursor\cli-anything-generator.root"

function Fail([string]$Message) {
    throw "FAIL: $Message"
}

function Assert-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Fail "expected file: $Path"
    }
}

function Assert-SameFile([string]$Left, [string]$Right) {
    $a = Get-FileHash -LiteralPath $Left -Algorithm SHA256
    $b = Get-FileHash -LiteralPath $Right -Algorithm SHA256
    if ($a.Hash -ne $b.Hash) {
        Fail "files differ: $Left $Right"
    }
}

$oldUserProfile = $env:USERPROFILE
$oldPluginsHome = $env:CURSOR_PLUGINS_HOME

try {
    New-Item -ItemType Directory -Path $userHome -Force | Out-Null
    New-Item -ItemType Directory -Path $staleStaging -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $staleStaging "stale.txt") -Value "left over from an interrupted install"

    $env:USERPROFILE = $userHome
    $env:CURSOR_PLUGINS_HOME = $pluginsHome
    & (Join-Path $pluginSrc "scripts\install.ps1")

    Assert-File (Join-Path $installedDir ".cursor-plugin\plugin.json")
    Assert-File (Join-Path $installedDir "PLUGIN_ROOT.txt")
    Assert-File $discoveryPointer
    Assert-File (Join-Path $installedDir "commands\cli-anything.md")
    Assert-File (Join-Path $installedDir "commands\cli-anything-refine.md")
    Assert-File (Join-Path $installedDir "commands\cli-anything-test.md")
    Assert-File (Join-Path $installedDir "commands\cli-anything-validate.md")
    Assert-File (Join-Path $installedDir "commands\cli-anything-list.md")
    Assert-File (Join-Path $installedDir "skills\cli-anything-generator\SKILL.md")
    Assert-File (Join-Path $installedDir "rules\cli-anything-generator.mdc")
    Assert-File (Join-Path $installedDir "references\HARNESS.md")
    Assert-File (Join-Path $installedDir "references\commands\cli-anything.md")
    Assert-File (Join-Path $installedDir "references\commands\refine.md")
    Assert-File (Join-Path $installedDir "references\commands\test.md")
    Assert-File (Join-Path $installedDir "references\commands\validate.md")
    Assert-File (Join-Path $installedDir "references\commands\list.md")
    Assert-File (Join-Path $installedDir "scripts\repl_skin.py")
    Assert-File (Join-Path $installedDir "scripts\preview_bundle.py")
    Assert-File (Join-Path $installedDir "scripts\skill_generator.py")
    Assert-File (Join-Path $installedDir "scripts\templates\SKILL.md.template")
    Assert-File (Join-Path $installedDir "references\docs\PREVIEW_PROTOCOL.md")

    $stamp = (Get-Content -LiteralPath (Join-Path $installedDir "PLUGIN_ROOT.txt") -Raw).Trim()
    $pointer = (Get-Content -LiteralPath $discoveryPointer -Raw).Trim()
    if (-not (Test-Path -LiteralPath (Join-Path $stamp "references\HARNESS.md"))) {
        Fail "stamped PLUGIN_ROOT missing HARNESS.md: $stamp"
    }
    if ($stamp -ne $pointer) {
        Fail "discovery pointer mismatch: $pointer != $stamp"
    }

    if (-not (Test-Path -LiteralPath $staleStaging)) {
        Fail "installer reused or removed the stale staging directory"
    }
    if (Test-Path -LiteralPath (Join-Path $installedDir "tests")) {
        Fail "installer copied tests/ into the installed plugin"
    }
    if (Test-Path -LiteralPath (Join-Path $installedDir "skills\cli-anything")) {
        Fail "old skills/cli-anything name should not be installed"
    }

    Assert-SameFile (Join-Path $canonicalPlugin "HARNESS.md") (Join-Path $installedDir "references\HARNESS.md")
    Assert-SameFile (Join-Path $canonicalPlugin "repl_skin.py") (Join-Path $installedDir "scripts\repl_skin.py")
    Assert-SameFile (Join-Path $canonicalPlugin "preview_bundle.py") (Join-Path $installedDir "scripts\preview_bundle.py")
    Assert-SameFile (Join-Path $canonicalPlugin "skill_generator.py") (Join-Path $installedDir "scripts\skill_generator.py")
    Assert-SameFile $previewProtocol (Join-Path $installedDir "references\docs\PREVIEW_PROTOCOL.md")

    foreach ($name in (Get-ChildItem (Join-Path $canonicalPlugin "commands\*.md")).Name) {
        Assert-SameFile (Join-Path $canonicalPlugin "commands\$name") (Join-Path $installedDir "references\commands\$name")
    }
    foreach ($name in (Get-ChildItem (Join-Path $canonicalPlugin "guides\*.md")).Name) {
        Assert-SameFile (Join-Path $canonicalPlugin "guides\$name") (Join-Path $installedDir "references\guides\$name")
    }
    foreach ($name in (Get-ChildItem (Join-Path $canonicalPlugin "templates\*")).Name) {
        Assert-SameFile (Join-Path $canonicalPlugin "templates\$name") (Join-Path $installedDir "scripts\templates\$name")
    }

    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
    if ($py) {
        & $py.Source -m py_compile `
            (Join-Path $installedDir "scripts\repl_skin.py") `
            (Join-Path $installedDir "scripts\preview_bundle.py") `
            (Join-Path $installedDir "scripts\skill_generator.py")
        if ($LASTEXITCODE -ne 0) {
            Fail "py_compile failed for vendored scripts"
        }
    } else {
        Fail "python/python3 not available for py_compile"
    }

    $refused = $false
    try {
        & (Join-Path $pluginSrc "scripts\install.ps1")
    } catch {
        $refused = $true
    }
    if (-not $refused) {
        Fail "installer overwrote an existing plugin without -Force"
    }

    $marker = Join-Path $installedDir ".install-marker"
    Set-Content -LiteralPath $marker -Value "first-install"
    & (Join-Path $pluginSrc "scripts\install.ps1") -Force
    if (Test-Path -LiteralPath $marker) {
        Fail "-Force upgrade did not replace the previous install"
    }
    Assert-File (Join-Path $installedDir "PLUGIN_ROOT.txt")
    Assert-File (Join-Path $installedDir "references\HARNESS.md")

    $cmdText = Get-Content -LiteralPath (Join-Path $installedDir "commands\cli-anything.md") -Raw
    if ($cmdText -notmatch "cli-anything-generator\.root") {
        Fail "installed command does not document discovery pointer"
    }
    if ($cmdText -notmatch "agent-harness/\.cli-anything-progress\.json") {
        Fail "installed command does not use agent-harness progress path"
    }

    $ruleText = Get-Content -LiteralPath (Join-Path $installedDir "rules\cli-anything-generator.mdc") -Raw
    if ($ruleText -notmatch "alwaysApply:\s*false") {
        Fail "generator rule must be alwaysApply false (avoid global context pollution)"
    }
    if ($ruleText -notmatch "agent-harness/\*\*") {
        Fail "generator rule must include agent-harness globs"
    }

    $skillText = Get-Content -LiteralPath (Join-Path $installedDir "skills\cli-anything-generator\SKILL.md") -Raw
    if ($skillText -notmatch "references/HARNESS.md") {
        Fail "installed skill does not point to vendored HARNESS.md"
    }
    if ($skillText -notmatch "cli-hub-meta-skill") {
        Fail "installed skill does not document consumer Hub path"
    }

    $manifest = Get-Content -LiteralPath (Join-Path $installedDir ".cursor-plugin\plugin.json") -Raw | ConvertFrom-Json
    if ($manifest.name -ne "cli-anything") {
        Fail "plugin manifest name mismatch"
    }

    $marketplacePath = Join-Path $repoRoot ".cursor-plugin\marketplace.json"
    Assert-File $marketplacePath
    $marketplace = Get-Content -LiteralPath $marketplacePath -Raw | ConvertFrom-Json
    $sources = @($marketplace.plugins | ForEach-Object { $_.source })
    if ($sources -notcontains "./cursor-plugin") {
        Fail "marketplace.json does not point at ./cursor-plugin"
    }

    $detachedRoot = Join-Path $tmpDir "detached"
    New-Item -ItemType Directory -Path $detachedRoot -Force | Out-Null
    Copy-Item -LiteralPath $pluginSrc -Destination (Join-Path $detachedRoot "cursor-plugin") -Recurse -Force
    $detachedFailed = $false
    try {
        $env:CURSOR_PLUGINS_HOME = Join-Path $tmpDir "detached-plugins\plugins"
        & (Join-Path $detachedRoot "cursor-plugin\scripts\install.ps1") 2>&1 | Out-Null
    } catch {
        $detachedFailed = $true
        if ($_.Exception.Message -notmatch "Cannot find canonical CLI-Anything resources") {
            Fail "detached install did not explain missing canonical resources"
        }
    }
    if (-not $detachedFailed) {
        Fail "installer accepted a detached plugin without canonical resources"
    }

    $badFailed = $false
    $badHomePath = Join-Path $tmpDir "not-plugins-dir"
    try {
        $env:CURSOR_PLUGINS_HOME = $badHomePath
        & (Join-Path $pluginSrc "scripts\install.ps1") 2>&1 | Out-Null
    } catch {
        $badFailed = $true
        if ($_.Exception.Message -notmatch "named 'plugins'") {
            Fail "installer did not reject non-plugins CURSOR_PLUGINS_HOME"
        }
    }
    if (-not $badFailed) {
        Fail "installer accepted CURSOR_PLUGINS_HOME whose basename is not plugins"
    }
    if (Test-Path -LiteralPath $badHomePath) {
        Fail "rejected CURSOR_PLUGINS_HOME should not create the target directory"
    }

    # Uninstall clears install dir + matching discovery pointer.
    $env:CURSOR_PLUGINS_HOME = $pluginsHome
    & (Join-Path $pluginSrc "scripts\uninstall.ps1")
    if (Test-Path -LiteralPath $installedDir) {
        Fail "uninstall left plugin directory behind"
    }
    if (Test-Path -LiteralPath $discoveryPointer) {
        Fail "uninstall left discovery pointer behind"
    }

    # Reinstall, then foreign pointer must be preserved across uninstall.
    & (Join-Path $pluginSrc "scripts\install.ps1")
    Assert-File (Join-Path $installedDir "references\HARNESS.md")
    $foreignRoot = Join-Path $tmpDir "some-other-plugin-root"
    Set-Content -LiteralPath $discoveryPointer -Value $foreignRoot
    & (Join-Path $pluginSrc "scripts\uninstall.ps1")
    if (Test-Path -LiteralPath $installedDir) {
        Fail "uninstall left plugin directory behind after foreign-pointer case"
    }
    if (-not (Test-Path -LiteralPath $discoveryPointer)) {
        Fail "uninstall removed a non-matching discovery pointer"
    }
    $leftPointer = (Get-Content -LiteralPath $discoveryPointer -Raw).Trim()
    if ($leftPointer -ne $foreignRoot) {
        Fail "foreign discovery pointer changed: $leftPointer"
    }

    . (Join-Path $pluginSrc "scripts\lib.ps1")
    if (-not (Test-CliAnythingInstallPath -Path "C:\Users\x\.cursor\plugins\local\cli-anything")) {
        Fail "Test-CliAnythingInstallPath should accept Windows local install path"
    }
    if (Test-CliAnythingInstallPath -Path "D:\repo\CLI-Anything\cursor-plugin") {
        Fail "Test-CliAnythingInstallPath must reject repo cursor-plugin path"
    }

    # Final reinstall for a clean installed tree at end of test.
    & (Join-Path $pluginSrc "scripts\install.ps1")
    Assert-File (Join-Path $installedDir "references\HARNESS.md")
    Assert-File $discoveryPointer
    Assert-File (Join-Path $installedDir "scripts\lib.ps1")
    Assert-File (Join-Path $installedDir "scripts\lib.sh")

    Write-Host "PASS: Cursor plugin installer vendors the complete CLI-Anything resource set."
} finally {
    if (Test-Path -LiteralPath $tmpDir) {
        Remove-Item -LiteralPath $tmpDir -Recurse -Force
    }
    if ($null -ne $oldUserProfile) {
        $env:USERPROFILE = $oldUserProfile
    } else {
        Remove-Item Env:USERPROFILE -ErrorAction SilentlyContinue
    }
    if ($null -ne $oldPluginsHome) {
        $env:CURSOR_PLUGINS_HOME = $oldPluginsHome
    } else {
        Remove-Item Env:CURSOR_PLUGINS_HOME -ErrorAction SilentlyContinue
    }
}
