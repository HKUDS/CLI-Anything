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
    if ($null -eq $LockHandle) {
        return
    }
    try { $LockHandle.Close() } catch {}
    try { $LockHandle.Dispose() } catch {}
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

function Resolve-CliAnythingRealPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $current = [System.IO.Path]::GetFullPath($Path)
    for ($hop = 0; $hop -lt 32; $hop++) {
        $root = [System.IO.Path]::GetPathRoot($current)
        if ([string]::IsNullOrEmpty($root)) {
            return $current
        }
        $rel = $current.Substring($root.Length).TrimStart("\", "/")
        if ([string]::IsNullOrEmpty($rel)) {
            return $current
        }
        $segments = $rel -split '[\\/]+'
        $built = $root
        $redirected = $false
        for ($i = 0; $i -lt $segments.Length; $i++) {
            $built = Join-Path $built $segments[$i]
            if (-not (Test-Path -LiteralPath $built)) {
                break
            }
            try {
                $item = Get-Item -LiteralPath $built -Force -ErrorAction Stop
            } catch {
                break
            }
            $linkTarget = $null
            if ($item.PSObject.Properties["LinkTarget"] -and -not [string]::IsNullOrWhiteSpace($item.LinkTarget)) {
                $linkTarget = [string]$item.LinkTarget
            } elseif ($item.PSObject.Properties["Target"] -and $null -ne $item.Target) {
                $rawTarget = $item.Target
                if ($rawTarget -is [System.Array]) {
                    if ($rawTarget.Length -gt 0) { $linkTarget = [string]$rawTarget[0] }
                } else {
                    $linkTarget = [string]$rawTarget
                }
            }
            if (-not [string]::IsNullOrWhiteSpace($linkTarget)) {
                if ($linkTarget.StartsWith("\\?\UNC\")) {
                    $linkTarget = "\\" + $linkTarget.Substring(8)
                } elseif ($linkTarget.StartsWith("\\?\")) {
                    $linkTarget = $linkTarget.Substring(4)
                } elseif ($linkTarget.StartsWith("\??\UNC\")) {
                    $linkTarget = "\\" + $linkTarget.Substring(8)
                } elseif ($linkTarget.StartsWith("\??\")) {
                    $linkTarget = $linkTarget.Substring(4)
                }
                if (-not [System.IO.Path]::IsPathRooted($linkTarget)) {
                    $parentDir = Split-Path -Parent $built
                    $linkTarget = Join-Path $parentDir $linkTarget
                }
                $resolvedPrefix = [System.IO.Path]::GetFullPath($linkTarget)
                if ($i + 1 -lt $segments.Length) {
                    $rest = ($segments[($i + 1)..($segments.Length - 1)]) -join "\"
                    $current = [System.IO.Path]::GetFullPath((Join-Path $resolvedPrefix $rest))
                } else {
                    $current = $resolvedPrefix
                }
                $redirected = $true
                break
            }
        }
        if (-not $redirected) {
            return $current
        }
    }
    return $current
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
    $stampRealNorm = Normalize-CliAnythingPathKey (Resolve-CliAnythingRealPath -Path $stamped)
    $fullRealNorm = Normalize-CliAnythingPathKey (Resolve-CliAnythingRealPath -Path $full)
    return ($stampRealNorm -eq $fullRealNorm) -or ($stampRealNorm -eq $fullNorm) -or ($stampNorm -eq $fullRealNorm)
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
