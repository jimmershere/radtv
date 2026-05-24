# B@Dtv one-shot installer for Windows (PowerShell 5+).
#
# Usage:
#   pwsh ./install.ps1                  # apply defaults
#   pwsh ./install.ps1 -DryRun
#   $env:KODI_USERDATA="C:\Kodi\userdata"; pwsh ./install.ps1
#
# Defaults come from config/badtv.conf.example; if you keep
# config/badtv.conf, edit it there. (PS reads the *.conf only as
# loose KEY=VAL lines for top-level scalars.)

[CmdletBinding()]
param(
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot

function Note([string]$msg) { Write-Host ">> $msg" -ForegroundColor Yellow }
function Ok([string]$msg)   { Write-Host "ok $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "!! $msg" -ForegroundColor Red }

function Load-Config {
    $cfg = @{
        BADTV_VERSION         = "2.0.0"
        BADTV_REPO_RAW_URL    = "https://raw.githubusercontent.com/jimmershere/badtv/main"
        FLOOR2_HOST           = "192.168.1.206"
        BADTV_SKIN_TARGET     = "arctic-zephyr-reloaded"
    }
    foreach ($name in @("badtv.conf.example", "badtv.conf")) {
        $path = Join-Path $repoRoot "config\$name"
        if (Test-Path $path) {
            Get-Content $path | ForEach-Object {
                if ($_ -match '^\s*([A-Z][A-Z0-9_]*)="?([^"#]*)"?\s*(#.*)?$') {
                    $cfg[$matches[1]] = $matches[2].Trim()
                }
            }
        }
    }
    return $cfg
}

function Detect-Userdata {
    if ($env:KODI_USERDATA -and (Test-Path $env:KODI_USERDATA)) {
        return $env:KODI_USERDATA
    }
    $candidates = @(
        "$env:APPDATA\Kodi\userdata",
        "$env:USERPROFILE\AppData\Roaming\Kodi\userdata"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    throw "Could not find Kodi userdata. Run Kodi once, or set `$env:KODI_USERDATA."
}

function Invoke-Step([string]$desc, [scriptblock]$action) {
    Note $desc
    if ($DryRun) {
        Write-Host "  (dry) skipping"
    } else {
        & $action
    }
}

$cfg = Load-Config
$userdata = Detect-Userdata
Ok "Kodi userdata: $userdata"
$addonsRoot = Split-Path $userdata -Parent | Join-Path -ChildPath "addons"
$packagesDir = Join-Path $userdata "addon_data\packages"

# --- 1. sources.xml ---------------------------------------------------------
$sourcesXml = Join-Path $userdata "sources.xml"
Invoke-Step "Merging floor2 sources into $sourcesXml" {
    & python3 "$repoRoot\tools\_apply_sources.py" "$sourcesXml" $cfg["FLOOR2_HOST"]
}

# --- 2. advancedsettings.xml -----------------------------------------------
$advancedXml = Join-Path $userdata "advancedsettings.xml"
if (-not (Test-Path $advancedXml)) {
    Invoke-Step "Writing $advancedXml" {
        @'
<advancedsettings>
  <network>
    <buffermode>1</buffermode>
    <readbufferfactor>4.0</readbufferfactor>
    <cachemembuffersize>157286400</cachemembuffersize>
  </network>
  <video>
    <ignoresecondsatstart>180</ignoresecondsatstart>
    <ignorepercentatend>8</ignorepercentatend>
  </video>
  <pvr>
    <minvideocachelevel>5</minvideocachelevel>
    <minaudiocachelevel>5</minaudiocachelevel>
  </pvr>
</advancedsettings>
'@ | Set-Content -Path $advancedXml -Encoding UTF8
    }
} else {
    Ok "advancedsettings.xml already present, leaving alone"
}

# --- 3. PVR IPTV Simple Client ---------------------------------------------
$pvrDir = Join-Path $userdata "addon_data\pvr.iptvsimple"
$pvrXml = Join-Path $pvrDir "settings.xml"
$m3u = "$($cfg.BADTV_REPO_RAW_URL)/iptv/dist/badtv.m3u"
$epg = "$($cfg.BADTV_REPO_RAW_URL)/iptv/dist/badtv.xml"
Invoke-Step "Configuring PVR IPTV Simple Client (M3U=$m3u, EPG=$epg)" {
    New-Item -ItemType Directory -Force -Path $pvrDir | Out-Null
    & python3 "$repoRoot\tools\_apply_pvr.py" "$pvrXml" "$m3u" "$epg"
}

# --- 4. Stage repository zip -----------------------------------------------
$repoZip = Join-Path $repoRoot "dist\repository.badtv-$($cfg.BADTV_VERSION).zip"
if (Test-Path $repoZip) {
    Invoke-Step "Copying repository zip into Kodi packages cache" {
        New-Item -ItemType Directory -Force -Path $packagesDir | Out-Null
        Copy-Item -Force $repoZip $packagesDir
    }
    Ok "repository.badtv zip staged at $packagesDir"
} else {
    Warn "$repoZip not found. Run 'make repo' first."
}

# --- 5. Skin override ------------------------------------------------------
$skinTarget = $cfg.BADTV_SKIN_TARGET
$skinAddon = switch ($skinTarget) {
    "arctic-zephyr-reloaded" { "skin.arctic.zephyr.reloaded" }
    "estuary-mod-v2"         { "skin.estuary.modv2" }
    "estuary"                { "skin.estuary" }
    default                  { $null }
}
if ($skinAddon) {
    $colorsDir = Join-Path $addonsRoot "$skinAddon\colors"
    $skinSrc = Join-Path $repoRoot "build\wizard\resources\skin\$skinTarget\colors\badtv.xml"
    if (Test-Path $colorsDir) {
        Invoke-Step "Copying B@Dtv color override into $colorsDir" {
            Copy-Item -Force $skinSrc (Join-Path $colorsDir "badtv.xml")
        }
        Ok "B@Dtv theme staged for $skinAddon"
    } else {
        Warn "$skinAddon not installed yet. Install the skin, then re-run install.ps1."
    }
}

Write-Host ""
Ok "B@Dtv install complete."
Write-Host "Next steps:"
Write-Host "  1. (Re)start Kodi."
Write-Host "  2. Install repository.badtv via 'Install from zip file'."
Write-Host "  3. Launch B@Dtv Wizard from Programs to finish setup."
