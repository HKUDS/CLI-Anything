# Shared helpers for CLI-Anything Google Antigravity plugin install/uninstall (PowerShell).

function Normalize-CliAnythingPathKey {
    param([Parameter(Mandatory = $true)][string]$Path)
    return $Path.Replace("/", "\").TrimEnd("\").ToLowerInvariant()
}

function Expand-CliAnythingPath {
    param([Parameter(Mandatory = $true)][string]$Raw)
    if ($Raw.StartsWith("~")) {
        $homePath = if ($env:USERPROFILE) { $env:USERPROFILE } else { $env:HOME }
        $Raw = Join-Path $homePath $Raw.Substring(1).TrimStart("\", "/")
    }
    if (-not [System.IO.Path]::IsPathRooted($Raw)) {
        $Raw = Join-Path (Get-Location).Path $Raw
    }
    return [System.IO.Path]::GetFullPath($Raw)
}

function Resolve-CliAnythingPluginsHome {
    param(
        [Parameter(Mandatory = $true)][string]$Raw,
        [switch]$Create
    )

    if ([string]::IsNullOrWhiteSpace($Raw) -or $Raw -eq "." -or $Raw -eq "..") {
        throw "Invalid ANTIGRAVITY_PLUGINS_HOME: $Raw"
    }

    # GetFullPath collapses ".." without creating the directory.
    $full = Expand-CliAnythingPath -Raw $Raw
    $name = [System.IO.Path]::GetFileName($full.TrimEnd("\", "/"))
    if ($name -ne "plugins") {
        throw "ANTIGRAVITY_PLUGINS_HOME must resolve to a directory named 'plugins' (got: $full)`nExample: $env:USERPROFILE\.gemini\config\plugins"
    }

    if ($Create) {
        New-Item -ItemType Directory -Path $full -Force | Out-Null
    }
    return $full
}

function Resolve-CliAnythingWorkspaceRoot {
    param([Parameter(Mandatory = $true)][string]$Raw)

    if ([string]::IsNullOrWhiteSpace($Raw)) {
        throw "Workspace path must not be empty."
    }
    $full = Expand-CliAnythingPath -Raw $Raw
    if (-not (Test-Path -LiteralPath $full -PathType Container)) {
        throw "Workspace directory does not exist: $full"
    }
    return $full
}

function Acquire-CliAnythingInstallLock {
    param(
        [Parameter(Mandatory = $true)][string]$LockPath,
        [int]$MaxAttempts = 50
    )
    for ($i = 0; $i -lt $MaxAttempts; $i++) {
        try {
            $fs = [System.IO.File]::Open(
                $LockPath,
                [System.IO.FileMode]::CreateNew,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
            $bytes = [System.Text.Encoding]::UTF8.GetBytes("$PID`n")
            $fs.Write($bytes, 0, $bytes.Length)
            $fs.Flush()
            return $fs
        } catch [System.IO.IOException] {
            Start-Sleep -Milliseconds 100
        }
    }
    throw "Could not acquire install lock: $LockPath`nAnother install may be running. If a previous run was killed, remove $LockPath and retry."
}

function Release-CliAnythingInstallLock {
    param(
        $LockHandle,
        [string]$LockPath
    )
    if ($null -ne $LockHandle) {
        try { $LockHandle.Close() } catch {}
        try { $LockHandle.Dispose() } catch {}
    }
    if (-not [string]::IsNullOrWhiteSpace($LockPath) -and (Test-Path -LiteralPath $LockPath)) {
        Remove-Item -LiteralPath $LockPath -Force -ErrorAction SilentlyContinue
    }
}

function Test-CliAnythingInstallPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $key = Normalize-CliAnythingPathKey $Path
    if (-not $key.EndsWith("\plugins\cli-anything")) {
        return $false
    }
    return ([System.IO.Path]::GetFileName($key) -eq "cli-anything")
}

function Test-CliAnythingVerifiedSelfInstallDir {
    param([Parameter(Mandatory = $true)][string]$Dir)
    $full = [System.IO.Path]::GetFullPath($Dir)
    if ([System.IO.Path]::GetFileName($full.TrimEnd("\", "/")) -ne "cli-anything") {
        return $false
    }
    $stampFile = Join-Path $full "PLUGIN_ROOT.txt"
    $manifestFile = Join-Path $full "plugin.json"
    if (-not ((Test-Path -LiteralPath $stampFile) -and (Test-Path -LiteralPath $manifestFile))) {
        return $false
    }
    $manifestText = Get-Content -LiteralPath $manifestFile -Raw
    if ($manifestText -notmatch '"name"\s*:\s*"cli-anything"') {
        return $false
    }
    $stamped = (Get-Content -LiteralPath $stampFile -Raw).Trim()
    if ([string]::IsNullOrWhiteSpace($stamped)) {
        return $false
    }
    $stampNorm = Normalize-CliAnythingPathKey $stamped
    $fullNorm = Normalize-CliAnythingPathKey $full
    if ($stampNorm -eq $fullNorm) {
        return $true
    }
    try {
        $resolvedTarget = (Get-Item -LiteralPath $full).Target
        if ($resolvedTarget) {
            return ($stampNorm -eq (Normalize-CliAnythingPathKey ([System.IO.Path]::GetFullPath($resolvedTarget))))
        }
    } catch {}
    return $false
}

function Get-CliAnythingDiscoveryPointerPath {
    $userGemini = if ($env:USERPROFILE) {
        Join-Path $env:USERPROFILE ".gemini"
    } elseif ($env:HOME) {
        Join-Path $env:HOME ".gemini"
    } else {
        throw "USERPROFILE/HOME unavailable."
    }
    return (Join-Path $userGemini "cli-anything-generator.root")
}
