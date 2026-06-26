#!/usr/bin/env bash
# Headless ProtonVPN for qBittorrent — NO protonvpn CLI signin required.
#
# Gluetun (Docker) uses a WireGuard private key from your Proton account.
# The host `protonvpn signin` command needs GNOME keyring + dbus and fails on
# headless NAS boxes like floor2. You do not need it for torrents.
#
# Run ON floor2 (as user floor2, docker group):
#   cd /app/radtv
#   bash tools/floor2-import-wireguard.sh
#   bash tools/floor2-import-wireguard.sh /tmp/us-free.conf
#
# Or from quasimodo:
#   scp ~/Downloads/us-free.conf floor2:/tmp/
#   ssh floor2 'cd /app/radtv && bash tools/floor2-import-wireguard.sh /tmp/us-free.conf'
#
# Get a config: https://account.proton.me/vpn/WireGuard → Create → Download

set -euo pipefail

log() { printf '>> %s\n' "$*"; }
warn() { printf '!! %s\n' "$*" >&2; }
die() { warn "$*"; exit 1; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WG_CONF="${1:-${PROTON_WG_CONF:-}}"

find_wg_conf() {
  local f
  for f in /tmp/*.conf /tmp/*proton* /tmp/*wg* /tmp/*radtv*; do
    [[ -f "$f" ]] || continue
    grep -qi 'PrivateKey' "$f" 2>/dev/null || continue
    echo "$f"
    return 0
  done
  return 1
}

if [[ -z "$WG_CONF" ]]; then
  WG_CONF="$(find_wg_conf)" || true
fi

if [[ -z "$WG_CONF" || ! -f "$WG_CONF" ]]; then
  cat >&2 <<'EOF'
!! No WireGuard config found.

1. Open https://account.proton.me/vpn/WireGuard
2. Create a config (pick a P2P / port-forward friendly server if you can)
3. Download the .conf file
4. Copy it to floor2:
     scp ~/Downloads/us-free.conf floor2:/tmp/
5. Re-run:
     bash tools/floor2-import-wireguard.sh /tmp/us-free.conf

You do NOT need `protonvpn signin` on floor2 — that CLI does not work headless.
EOF
  exit 1
fi

log "WireGuard config: $WG_CONF"
export PROTON_WG_CONF="$WG_CONF"
export FLOOR2_STACK="${FLOOR2_STACK:-/datapool/preserved/badtv-arr}"

GLUETUN_PY="$REPO_ROOT/tools/floor2-set-gluetun-proton.py"
[[ -f "$GLUETUN_PY" ]] || die "missing $GLUETUN_PY — git pull in $REPO_ROOT"

log "configuring Gluetun (ProtonVPN + WireGuard) in $FLOOR2_STACK"
python3 "$GLUETUN_PY"

FIX_PY="$REPO_ROOT/tools/floor2-fix-compose.py"
if [[ -f "$FIX_PY" ]]; then
  log "fixing docker-compose interpolation"
  FLOOR2_STACK="$FLOOR2_STACK" python3 "$FIX_PY"
fi

STACK="$FLOOR2_STACK"
log "checking containers..."
if [[ -d "$STACK" ]]; then
  (cd "$STACK" && docker compose ps gluetun qbittorrent 2>/dev/null) || true
  log "recent Gluetun logs:"
  (cd "$STACK" && docker compose logs --tail=20 gluetun 2>/dev/null) || true
fi

cat <<EOF

================================================================================
 Headless VPN ready (Gluetun + WireGuard — no protonvpn CLI)
================================================================================

  qBittorrent Web UI:  http://floor2:8091  (or http://192.168.1.206:8091)
  Gluetun status:      cd $STACK && docker compose ps gluetun

  protonvpn signin is NOT required and will fail on this headless NAS.
  Torrent traffic goes through Docker Gluetun only.

================================================================================
EOF
