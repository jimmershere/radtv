#!/usr/bin/env bash
# B@Dtv one-shot installer for Linux + macOS.
#
# What it does (idempotent):
#   1. Locate Kodi userdata (override with KODI_USERDATA env var or
#      config/badtv.conf).
#   2. Drop a sources.xml entry for the floor2 NAS (NFS) into the right
#      section of Kodi's sources.xml.
#   3. Drop a sane advancedsettings.xml that whitelists refresh rates and
#      makes addons behave during library scans.
#   4. Write PVR IPTV Simple Client settings.xml pointing at the bundled
#      B@Dtv playlist + EPG URLs.
#   5. Copy the B@Dtv repository zip to Kodi's addons/packages cache so the
#      next Kodi launch sees it as installable from "Install from zip".
#   6. Copy the active skin's color override into place if the skin is
#      already installed.
#
# Usage:
#   bash install.sh                    # apply defaults (prompts on disclaimer)
#   bash install.sh --dry-run          # show what would change, write nothing
#   bash install.sh --accept-disclaimer  # skip the prompt (also: BADTV_ACCEPT_DISCLAIMER=1)
#   KODI_USERDATA=/path bash install.sh
#
# Exit codes:
#   0 - success (including dry-run)
#   1 - usage / config error / disclaimer declined
#   2 - filesystem / write failure

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
DRY_RUN=0
ACCEPT_DISCLAIMER="${BADTV_ACCEPT_DISCLAIMER:-0}"

for arg in "$@"; do
  case "$arg" in
    --dry-run|-n)           DRY_RUN=1 ;;
    --accept-disclaimer)    ACCEPT_DISCLAIMER=1 ;;
    --help|-h)              sed -n '2,/^$/p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $arg"; exit 1 ;;
  esac
done

# Capture env-var overrides BEFORE sourcing config so they aren't stomped by
# the "" defaults in badtv.conf.example.
_env_kodi_userdata="${KODI_USERDATA:-}"

# shellcheck disable=SC1091
source "$REPO_ROOT/config/load.sh"

if [[ -n "$_env_kodi_userdata" ]]; then
  KODI_USERDATA="$_env_kodi_userdata"
fi

run() {
  if (( DRY_RUN )); then echo "  (dry) $*"; else eval "$*"; fi
}

note() { printf '\033[33m>>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32mok\033[0m %s\n' "$*"; }
warn() { printf '\033[31m!!\033[0m %s\n' "$*" >&2; }

# --- disclaimer gate --------------------------------------------------------
show_disclaimer() {
  cat <<'EOF'

================================================================================
 B@Dtv -- legal and privacy notice (read DISCLAIMER.md for the full text)
================================================================================

 - B@Dtv is GPL-3.0 packaging software. NO WARRANTY. Use at your own risk.
 - B@Dtv does NOT host, transmit, or mirror any audiovisual content. It
   configures Kodi, points it at publicly-listed free/ad-supported IPTV
   sources, and documents third-party scraper addons. You decide what to
   install and what to stream.
 - IPTV legality varies by jurisdiction. You are responsible for compliance
   with copyright, broadcast, and circumvention law where you live.
 - B@Dtv is NOT affiliated with NBCUniversal ("The Black Donnellys"), the
   XBMC Foundation (Kodi), Real-Debrid, Trakt, Plex, Tubi, Samsung, Sinclair,
   or any third-party scraper author. See NOTICE.md.
 - VPN / DNS helpers in tools/network/ are for privacy. Anonymization does
   NOT make otherwise-illegal activity legal. See docs/PRIVACY.md.

EOF
}

require_disclaimer() {
  if (( ACCEPT_DISCLAIMER )); then
    return
  fi
  show_disclaimer
  if [[ ! -t 0 ]]; then
    warn "stdin is not a TTY -- re-run with --accept-disclaimer or BADTV_ACCEPT_DISCLAIMER=1"
    exit 1
  fi
  local reply=""
  read -r -p "Type 'I AGREE' to proceed: " reply
  if [[ "$reply" != "I AGREE" ]]; then
    warn "disclaimer not accepted -- aborting."
    exit 1
  fi
  echo
}

require_disclaimer

# --- detect Kodi userdata ---------------------------------------------------
detect_userdata() {
  if [[ -n "${KODI_USERDATA:-}" && -d "$KODI_USERDATA" ]]; then
    echo "$KODI_USERDATA"
    return
  fi
  local candidates=(
    "$HOME/.kodi/userdata"
    "$HOME/Library/Application Support/Kodi/userdata"
    "$HOME/snap/kodi/common/.kodi/userdata"
    "/storage/.kodi/userdata"
  )
  for path in "${candidates[@]}"; do
    if [[ -d "$path" ]]; then
      echo "$path"
      return
    fi
  done
  return 1
}

if ! USERDATA="$(detect_userdata)"; then
  warn "Could not find Kodi userdata. Set KODI_USERDATA env var or run Kodi once first."
  exit 1
fi
ok "Kodi userdata: $USERDATA"

ADDONS_ROOT="$(dirname "$USERDATA")/addons"
PACKAGES_DIR="$USERDATA/addon_data/packages"

# --- 1. sources.xml ---------------------------------------------------------
SOURCES_XML="$USERDATA/sources.xml"
note "Merging floor2 sources into $SOURCES_XML"
run "python3 \"$REPO_ROOT/tools/_apply_sources.py\" \"$SOURCES_XML\" \"$FLOOR2_HOST\""

# --- 2. advancedsettings.xml -----------------------------------------------
ADVANCED_XML="$USERDATA/advancedsettings.xml"
if [[ ! -f "$ADVANCED_XML" || $DRY_RUN -eq 1 ]]; then
  note "Writing $ADVANCED_XML"
  if (( ! DRY_RUN )); then
    cat > "$ADVANCED_XML" <<'XML'
<advancedsettings>
  <!-- B@Dtv defaults -->
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
  <loglevel hide="false">0</loglevel>
</advancedsettings>
XML
  fi
  ok "advancedsettings.xml installed"
else
  ok "advancedsettings.xml already present, leaving alone"
fi

# --- 3. PVR IPTV Simple Client ---------------------------------------------
PVR_DIR="$USERDATA/addon_data/pvr.iptvsimple"
PVR_XML="$PVR_DIR/settings.xml"
M3U_URL="${IPTV_M3U_URL_OVERRIDE:-$BADTV_REPO_RAW_URL/iptv/dist/badtv.m3u}"
EPG_URL="${IPTV_EPG_URL_OVERRIDE:-$BADTV_REPO_RAW_URL/iptv/dist/badtv.xml}"

note "Configuring PVR IPTV Simple Client"
note "  M3U: $M3U_URL"
note "  EPG: $EPG_URL"
run "mkdir -p \"$PVR_DIR\""
if (( ! DRY_RUN )); then
  python3 - "$PVR_XML" "$M3U_URL" "$EPG_URL" <<'PY'
import sys
from xml.etree import ElementTree as ET
import os

path, m3u, epg = sys.argv[1], sys.argv[2], sys.argv[3]
if os.path.isfile(path):
    tree = ET.parse(path)
    root = tree.getroot()
else:
    root = ET.Element("settings", version="2")
    tree = ET.ElementTree(root)

desired = {
    "m3uPathType": "1",
    "m3uUrl": m3u,
    "m3uCache": "true",
    "epgPathType": "1",
    "epgUrl": epg,
    "epgCache": "true",
    "startNum": "1",
    "logoPathType": "1",
    "catchupEnabled": "true",
}
existing = {s.get("id"): s for s in root.findall("setting")}
for k, v in desired.items():
    elem = existing.get(k) or ET.SubElement(root, "setting", id=k)
    elem.text = v
tree.write(path, encoding="UTF-8", xml_declaration=True)
print(f"  wrote {path}")
PY
fi
ok "PVR IPTV Simple Client configured"

# --- 4. Drop repository + wizard zips into Kodi's packages cache ----------
mkdir -p "$REPO_ROOT/dist"
REPO_ZIP="$REPO_ROOT/dist/repository.badtv-$BADTV_VERSION.zip"
if [[ -f "$REPO_ZIP" ]]; then
  note "Copying repository zip into Kodi packages cache"
  run "mkdir -p \"$PACKAGES_DIR\""
  run "cp \"$REPO_ZIP\" \"$PACKAGES_DIR/\""
  ok "repository.badtv zip staged at $PACKAGES_DIR"
else
  warn "$REPO_ZIP not found. Run 'make repo' first to build it."
fi

# --- 5. Skin override ------------------------------------------------------
SKIN_TARGET="${BADTV_SKIN_TARGET:-arctic-zephyr-reloaded}"
case "$SKIN_TARGET" in
  arctic-zephyr-reloaded) SKIN_ADDON="skin.arctic.zephyr.reloaded" ;;
  estuary-mod-v2)         SKIN_ADDON="skin.estuary.modv2" ;;
  estuary)                SKIN_ADDON="skin.estuary" ;;
  none)                   SKIN_ADDON="" ;;
  *) warn "Unknown BADTV_SKIN_TARGET=$SKIN_TARGET"; SKIN_ADDON="" ;;
esac
if [[ -n "$SKIN_ADDON" ]]; then
  SKIN_COLORS_DIR="$ADDONS_ROOT/$SKIN_ADDON/colors"
  SKIN_SRC="$REPO_ROOT/build/wizard/resources/skin/$SKIN_TARGET/colors/badtv.xml"
  if [[ -d "$SKIN_COLORS_DIR" ]]; then
    note "Copying B@Dtv color override into $SKIN_COLORS_DIR"
    run "cp \"$SKIN_SRC\" \"$SKIN_COLORS_DIR/badtv.xml\""
    ok "B@Dtv theme staged for $SKIN_ADDON (select via Settings > Skin > Colours > badtv)"
  else
    warn "$SKIN_ADDON not installed yet. Run Kodi, install the skin, then re-run install.sh."
  fi
fi

echo
ok "B@Dtv install complete."
echo "Next steps:"
echo "  1. (Re)start Kodi."
echo "  2. Install repository.badtv via 'Install from zip file'."
echo "  3. Launch B@Dtv Wizard from Programs to finish auth + install scrapers."
