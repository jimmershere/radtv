#!/usr/bin/env bash
# B@Dtv Samba setup for floor2 (or whichever NAS you point it at).
# Reads config from config/badtv.conf with config/badtv.conf.example as
# defaults. Run as root on the NAS box.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/../config/load.sh"

SMB_CONF="/etc/samba/smb.conf"

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "Run as root." >&2
    exit 1
  fi
}

ensure_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

append_share() {
  local name="$1"
  local path="$2"
  if grep -Fq "[$name]" "$SMB_CONF" 2>/dev/null; then
    echo "Share [$name] already present"
    return
  fi
  cat >> "$SMB_CONF" <<SHARE

[$name]
   path = $path
   browseable = yes
   read only = no
   guest ok = no
   create mask = 0664
   directory mask = 0775
SHARE
  echo "Added SMB share [$name] -> $path"
}

main() {
  require_root
  ensure_cmd zfs
  ensure_cmd testparm

  if ! zfs list "$FLOOR2_ZFS_DATASET" >/dev/null 2>&1; then
    zfs create "$FLOOR2_ZFS_DATASET"
  fi

  zfs set mountpoint="$FLOOR2_MOUNTPOINT" "$FLOOR2_ZFS_DATASET"

  local dirs=()
  for sub in "${FLOOR2_SUBDIRS[@]}"; do
    dirs+=("$FLOOR2_MOUNTPOINT/$sub")
  done
  install -d -m 0775 "${dirs[@]}"

  touch "$SMB_CONF"
  append_share "media" "$FLOOR2_MOUNTPOINT"
  for sub in "${FLOOR2_SUBDIRS[@]}"; do
    append_share "$(echo "$sub" | tr '[:upper:]' '[:lower:]')" "$FLOOR2_MOUNTPOINT/$sub"
  done

  testparm -s >/dev/null

  cat <<MSG
SMB sharing configured for $FLOOR2_HOST.
Kodi can browse via:
  smb://$FLOOR2_HOST/media/
MSG
  for sub in "${FLOOR2_SUBDIRS[@]}"; do
    echo "  smb://$FLOOR2_HOST/$(echo "$sub" | tr '[:upper:]' '[:lower:]')/"
  done
  echo "Restart smbd/nmbd manually if your distro does not auto-reload."
}

main "$@"
