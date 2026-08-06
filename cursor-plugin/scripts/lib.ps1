# Shared helpers for CLI-Anything Cursor plugin install/uninstall (PowerShell).

function Normalize-CliAnythingPathKey {
    param([Parameter(Mandatory = $true)][string]$Path)
    return $Path.Replace("/", "\").TrimEnd("\").ToLowerInvariant()
}

function Resolve-CliAnythingPluginsHome {
    param(
        [Parameter(Mandatory = $true)][string]$Raw,
        [switch]$Create
    )

    if ([string]::IsNullOrWhiteSpace($Raw) -or $Raw -eq "." -or $Raw -eq "..") {
        throw "Invalid CURSOR_PLUGINS_HOME: $Raw"
    }

    if ($Raw.StartsWith("~")) {
        $homePath = if ($env:USERPROFILE) { $env:USERPROFILE } else { $env:HOME }
        $Raw = Join-Path $homePath $Raw.Substring(1).TrimStart("\", "/")
    }

    if (-not [System.IO.Path]::IsPathRooted($Raw)) {
        $Raw = Join-Path (Get-Location).Path $Raw
    }

    # GetFullPath collapses ".." without creating the directory.
    $full = [System.IO.Path]::GetFullPath($Raw)
    $name = [System.IO.Path]::GetFileName($full.TrimEnd("\", "/"))
    if ($name -ne "plugins") {
        throw "CURSOR_PLUGINS_HOME must resolve to a directory named 'plugins' (got: $full)`nExample: $env:USERPROFILE\.cursor\plugins"
    }

    if ($Create) {
        New-Item -ItemType Directory -Path $full -Force | Out-Null
    }
    return $full
}

function Test-CliAnythingInstallPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $key = Normalize-CliAnythingPathKey $Path
    if (-not $key.EndsWith("\local\cli-anything")) {
        return $false
    }
    return ([System.IO.Path]::GetFileName($key) -eq "cli-anything")
}

function Get-CliAnythingDiscoveryPointerPath {
    $userCursor = if ($env:USERPROFILE) {
        Join-Path $env:USERPROFILE ".cursor"
    } elseif ($env:HOME) {
        Join-Path $env:HOME ".cursor"
    } else {
        throw "USERPROFILE/HOME unavailable."
    }
    return (Join-Path $userCursor "cli-anything-generator.root")
}
