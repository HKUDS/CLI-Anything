# Regression tests for the Google Antigravity plugin installer (Windows PowerShell).
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pluginSrc = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $pluginSrc
$canonicalPlugin = Join-Path $repoRoot "cli-anything-plugin"
$previewProtocol = Join-Path $repoRoot "docs\PREVIEW_PROTOCOL.md"

$tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("cli-anything-antigravity-test-" + [System.Guid]::NewGuid().ToString("N"))
$userHome = Join-Path $tmpDir "home"
$pluginsHome = Join-Path $tmpDir "plugins"
$installedDir = Join-Path $pluginsHome "cli-anything"
$staleStaging = Join-Path $pluginsHome ".cli-anything.tmp.stale"
$discoveryPointer = Join-Path $userHome ".gemini\cli-anything-generator.root"
$workspaceDir = Join-Path $tmpDir "sample-workspace"
$wsInstalledDir = Join-Path $workspaceDir ".agents\plugins\cli-anything"

function Fail([string]$Message) { throw "FAIL: $Message" }
function Assert-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Fail "expected file: $Path" }
}
function Assert-SameFile([string]$Left, [string]$Right) {
    if ((Get-FileHash -LiteralPath $Left -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $Right -Algorithm SHA256).Hash) {
        Fail "files differ: $Left $Right"
    }
}

$oldUserProfile = $env:USERPROFILE
$oldPluginsHome = $env:ANTIGRAVITY_PLUGINS_HOME

try {
    New-Item -ItemType Directory -Path $userHome, $workspaceDir -Force | Out-Null
    $env:USERPROFILE = $userHome

    # 1. Dry-run does not create directories or pointer
    $dryPlugins = Join-Path $tmpDir "dry-root\plugins"
    $env:ANTIGRAVITY_PLUGINS_HOME = $dryPlugins
    & (Join-Path $pluginSrc "scripts\install.ps1") -DryRun | Out-Null
    if (Test-Path -LiteralPath $dryPlugins) { Fail "-DryRun created plugins directory" }
    if (Test-Path -LiteralPath $discoveryPointer) { Fail "-DryRun created discovery pointer" }

    New-Item -ItemType Directory -Path $staleStaging -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $staleStaging "stale.txt") -Value "left over"

    # 2. Full global install
    $env:ANTIGRAVITY_PLUGINS_HOME = $pluginsHome
    & (Join-Path $pluginSrc "scripts\install.ps1")

    Assert-File (Join-Path $installedDir "plugin.json")
    Assert-File (Join-Path $installedDir "README.md")
    Assert-File (Join-Path $installedDir "PLUGIN_ROOT.txt")
    Assert-File (Join-Path $installedDir "assets\logo.svg")
    Assert-File (Join-Path $installedDir "hooks.json")
    Assert-File (Join-Path $installedDir "rules\cli-anything-generator.md")
    Assert-File (Join-Path $installedDir "agents\cli-anything-auditor.md")
    Assert-File $discoveryPointer
    foreach ($skill in @("cli-anything", "cli-anything-refine", "cli-anything-test", "cli-anything-validate", "cli-anything-list")) {
        Assert-File (Join-Path $installedDir "skills\$skill\SKILL.md")
        $skText = Get-Content -LiteralPath (Join-Path $installedDir "skills\$skill\SKILL.md") -Raw
        if ($skText -notmatch "(?m)^name:\s*$([regex]::Escape($skill))\s*$") {
            Fail "skill folder/frontmatter mismatch for $skill"
        }
    }
    Assert-File (Join-Path $installedDir "references\antigravity-tooling.md")
    Assert-File (Join-Path $installedDir "references\HARNESS.md")
    Assert-File (Join-Path $installedDir "references\docs\PREVIEW_PROTOCOL.md")
    Assert-File (Join-Path $installedDir "scripts\repl_skin.py")
    Assert-File (Join-Path $installedDir "scripts\preview_bundle.py")
    Assert-File (Join-Path $installedDir "scripts\skill_generator.py")
    Assert-File (Join-Path $installedDir "scripts\verify_harness.py")
    Assert-File (Join-Path $installedDir "scripts\list_harnesses.py")
    Assert-File (Join-Path $installedDir "scripts\pep420_guard.py")
    Assert-File (Join-Path $installedDir "scripts\templates\SKILL.md.template")

    if (Test-Path -LiteralPath (Join-Path $pluginsHome ".cli-anything.lock")) {
        Fail "stale lock remained after install"
    }

    $stamp = (Get-Content -LiteralPath (Join-Path $installedDir "PLUGIN_ROOT.txt") -Raw).Trim()
    $pointer = (Get-Content -LiteralPath $discoveryPointer -Raw).Trim()
    if ($stamp -ne $pointer) { Fail "discovery pointer mismatch: $pointer != $stamp" }
    if (-not (Test-Path -LiteralPath $staleStaging)) { Fail "touched stale staging directory" }
    if (Test-Path -LiteralPath (Join-Path $installedDir "tests")) { Fail "copied tests/ into installed plugin" }
    if (Test-Path -LiteralPath (Join-Path $installedDir "rules\AGENTS.md")) { Fail "must not ship always-on rules/AGENTS.md" }

    # 3. Byte-for-byte parity
    Assert-SameFile (Join-Path $canonicalPlugin "HARNESS.md") (Join-Path $installedDir "references\HARNESS.md")
    Assert-SameFile (Join-Path $canonicalPlugin "repl_skin.py") (Join-Path $installedDir "scripts\repl_skin.py")
    Assert-SameFile (Join-Path $canonicalPlugin "preview_bundle.py") (Join-Path $installedDir "scripts\preview_bundle.py")
    Assert-SameFile (Join-Path $canonicalPlugin "skill_generator.py") (Join-Path $installedDir "scripts\skill_generator.py")
    Assert-SameFile $previewProtocol (Join-Path $installedDir "references\docs\PREVIEW_PROTOCOL.md")
    Assert-SameFile (Join-Path $pluginSrc "references\antigravity-tooling.md") (Join-Path $installedDir "references\antigravity-tooling.md")
    foreach ($name in (Get-ChildItem (Join-Path $canonicalPlugin "commands\*.md")).Name) {
        Assert-SameFile (Join-Path $canonicalPlugin "commands\$name") (Join-Path $installedDir "references\commands\$name")
    }
    foreach ($name in (Get-ChildItem (Join-Path $canonicalPlugin "guides\*.md")).Name) {
        Assert-SameFile (Join-Path $canonicalPlugin "guides\$name") (Join-Path $installedDir "references\guides\$name")
    }
    foreach ($name in (Get-ChildItem (Join-Path $canonicalPlugin "templates\*")).Name) {
        Assert-SameFile (Join-Path $canonicalPlugin "templates\$name") (Join-Path $installedDir "scripts\templates\$name")
    }

    # 4. Schema validation
    $manifest = Get-Content -LiteralPath (Join-Path $installedDir "plugin.json") -Raw | ConvertFrom-Json
    $allowedKeys = @("`$schema", "name", "displayName", "version", "description", "author", "homepage", "repository", "logo", "suggestedPrompts", "disabled", "license", "keywords", "skills", "extensions")
    foreach ($prop in $manifest.PSObject.Properties) {
        if ($allowedKeys -notcontains $prop.Name) { Fail "unknown plugin.json field: $($prop.Name)" }
    }
    if ($manifest.name -ne "cli-anything") { Fail "plugin manifest name mismatch" }
    if ($manifest.'$schema' -ne "https://antigravity.google/schemas/v1/plugin.json") { Fail "missing official schema URL" }
    if ($manifest.license -ne "Apache-2.0") { Fail "missing Apache-2.0 license" }
    if (@($manifest.suggestedPrompts).Count -ne 3) { Fail "expected 3 suggestedPrompts" }
    Assert-File (Join-Path $installedDir $manifest.logo)

    $ruleText = Get-Content -LiteralPath (Join-Path $installedDir "rules\cli-anything-generator.md") -Raw
    if ($ruleText -notmatch "trigger:\s*glob") { Fail "rule must use trigger: glob" }
    if ($ruleText -notmatch '(?m)^globs:\s*"[^"]*agent-harness/\*\*') { Fail "rule globs must be comma-separated string" }

    $hooks = Get-Content -LiteralPath (Join-Path $installedDir "hooks.json") -Raw | ConvertFrom-Json
    if ($hooks.'pep420-namespace-guard'.enabled -ne $false) { Fail "pep420 hook must default to enabled=false" }

    # 5. Live execution check of installed scripts (without PLUGIN_ROOT.txt, simulating agy plugin install)
    Remove-Item -LiteralPath (Join-Path $installedDir "PLUGIN_ROOT.txt") -Force
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $py) { Fail "python not found" }
    & $py.Source -B -m py_compile `
        (Join-Path $installedDir "scripts\repl_skin.py") `
        (Join-Path $installedDir "scripts\preview_bundle.py") `
        (Join-Path $installedDir "scripts\skill_generator.py") `
        (Join-Path $installedDir "scripts\verify_harness.py") `
        (Join-Path $installedDir "scripts\list_harnesses.py") `
        (Join-Path $installedDir "scripts\pep420_guard.py")
    if ($LASTEXITCODE -ne 0) { Fail "py_compile failed" }
    if (Test-Path -LiteralPath (Join-Path $repoRoot "gimp\agent-harness")) {
        & $py.Source (Join-Path $installedDir "scripts\verify_harness.py") (Join-Path $repoRoot "gimp") --json | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail "installed verify_harness.py failed on gimp" }
    }
    & $py.Source (Join-Path $installedDir "scripts\list_harnesses.py") --path $repoRoot --depth 1 --json | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "installed list_harnesses.py failed" }

    # 6. Overwrite protection and -Force upgrade
    $refused = $false
    try { & (Join-Path $pluginSrc "scripts\install.ps1") } catch { $refused = $true }
    if (-not $refused) { Fail "overwrote existing plugin without -Force" }

    $marker = Join-Path $installedDir ".install-marker"
    Set-Content -LiteralPath $marker -Value "first"
    & (Join-Path $pluginSrc "scripts\install.ps1") -Force
    if (Test-Path -LiteralPath $marker) { Fail "-Force did not replace previous install" }

    # 7. Workspace install preserves global pointer
    & (Join-Path $pluginSrc "scripts\install.ps1") -Workspace $workspaceDir
    Assert-File (Join-Path $wsInstalledDir "references\HARNESS.md")
    Assert-File (Join-Path $wsInstalledDir "scripts\verify_harness.py")
    if (((Get-Content -LiteralPath $discoveryPointer -Raw).Trim()) -ne $stamp) { Fail "workspace install clobbered global pointer" }
    & (Join-Path $pluginSrc "scripts\uninstall.ps1") -Workspace $workspaceDir
    if (Test-Path -LiteralPath $wsInstalledDir) { Fail "workspace uninstall left dir" }
    Assert-File $discoveryPointer

    # 8. Detached and invalid root rejection
    $detachedRoot = Join-Path $tmpDir "detached"
    New-Item -ItemType Directory -Path $detachedRoot -Force | Out-Null
    Copy-Item -LiteralPath $pluginSrc -Destination (Join-Path $detachedRoot "antigravity-plugin") -Recurse -Force
    $detachedFailed = $false
    try {
        $env:ANTIGRAVITY_PLUGINS_HOME = Join-Path $tmpDir "detached-plugins\plugins"
        & (Join-Path $detachedRoot "antigravity-plugin\scripts\install.ps1") 2>&1 | Out-Null
    } catch { $detachedFailed = $true }
    if (-not $detachedFailed) { Fail "accepted detached plugin" }

    $badHomePath = Join-Path $tmpDir "not-plugins-dir"
    $badFailed = $false
    try {
        $env:ANTIGRAVITY_PLUGINS_HOME = $badHomePath
        & (Join-Path $pluginSrc "scripts\install.ps1") 2>&1 | Out-Null
    } catch { $badFailed = $true }
    if (-not $badFailed -or (Test-Path -LiteralPath $badHomePath)) { Fail "invalid plugins home check failed" }

    # 9. Uninstall & foreign pointer protection
    $env:ANTIGRAVITY_PLUGINS_HOME = $pluginsHome
    & (Join-Path $pluginSrc "scripts\uninstall.ps1")
    if (Test-Path -LiteralPath $installedDir) { Fail "uninstall left dir" }
    if (Test-Path -LiteralPath $discoveryPointer) { Fail "uninstall left pointer" }

    & (Join-Path $pluginSrc "scripts\install.ps1")
    $foreignRoot = Join-Path $tmpDir "some-other-plugin-root"
    Set-Content -LiteralPath $discoveryPointer -Value $foreignRoot
    & (Join-Path $pluginSrc "scripts\uninstall.ps1")
    if (((Get-Content -LiteralPath $discoveryPointer -Raw).Trim()) -ne $foreignRoot) { Fail "foreign pointer changed" }

    . (Join-Path $pluginSrc "scripts\lib.ps1")
    if (-not (Test-CliAnythingInstallPath -Path "C:\Users\x\.gemini\config\plugins\cli-anything")) { Fail "rejected global path" }
    if (-not (Test-CliAnythingInstallPath -Path "D:\work\repo\.agents\plugins\cli-anything")) { Fail "rejected workspace path" }
    if (Test-CliAnythingInstallPath -Path "D:\repo\CLI-Anything\antigravity-plugin") { Fail "accepted repo source path" }

    Write-Host "PASS: Antigravity plugin installer, components, and scripts verified."
} finally {
    if (Test-Path -LiteralPath $tmpDir) { Remove-Item -LiteralPath $tmpDir -Recurse -Force }
    if ($null -ne $oldUserProfile) { $env:USERPROFILE = $oldUserProfile } else { Remove-Item Env:USERPROFILE -ErrorAction SilentlyContinue }
    if ($null -ne $oldPluginsHome) { $env:ANTIGRAVITY_PLUGINS_HOME = $oldPluginsHome } else { Remove-Item Env:ANTIGRAVITY_PLUGINS_HOME -ErrorAction SilentlyContinue }
}
