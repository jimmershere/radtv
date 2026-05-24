#!/usr/bin/env bash
# B@Dtv NFS setup for floor2 (or whichever NAS you point it at).
# Reads config from config/badtv.conf with config/badtv.conf.example as
# defaults. Run as root on the NAS box.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/../config/load.sh"

EXPORTS_FILE="/etc/exports"

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

append_export() {
  local path="$1"
  local line="$path $FLOOR2_NFS_CLIENT_SPEC"
  if ! grep -Fqx "$line" "$EXPORTS_FILE" 2>/dev/null; then
    echo "$line" >> "$EXPORTS_FILE"
    echo "Added export: $line"
  else
    echo "Export already present: $line"
  fi
}

main() {
  require_root
  ensure_cmd zfs
  ensure_cmd exportfs

  if ! zfs list "$FLOOR2_ZFS_DATASET" >/dev/null 2>&1; then
    zfs create "$FLOOR2_ZFS_DATASET"
  fi

  zfs set mountpoint="$FLOOR2_MOUNTPOINT" "$FLOOR2_ZFS_DATASET"

  local dirs=()
  for sub in "${FLOOR2_SUBDIRS[@]}"; do
    dirs+=("$FLOOR2_MOUNTPOINT/$sub")
  done
  install -d -m 0775 "${dirs[@]}"

  touch "$EXPORTS_FILE"
  append_export "$FLOOR2_MOUNTPOINT"
  for sub in "${FLOOR2_SUBDIRS[@]}"; do
    append_export "$FLOOR2_MOUNTPOINT/$sub"
  done

  exportfs -ra

  cat <<MSG
NFS sharing configured for $FLOOR2_HOST.
Kodi can browse via:
  nfs://$FLOOR2_HOST$FLOOR2_MOUNTPOINT/
MSG
  for sub in "${FLOOR2_SUBDIRS[@]}"; do
    echo "  nfs://$FLOOR2_HOST$FLOOR2_MOUNTPOINT/$sub/"
  done
}

main "$@"
