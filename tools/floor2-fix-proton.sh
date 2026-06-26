#!/usr/bin/env bash
# Fix apt on floor2, install official Proton VPN CLI, and wire Gluetun (Docker)
# from a WireGuard config in /tmp.
#
# Run ON floor2:
#   cd /app/radtv && git pull && sudo bash tools/floor2-fix-proton.sh
#
# Or from quasimodo:
#   ssh floor2@192.168.1.206 'bash -s' < tools/floor2-fix-proton.sh
#
# After this script:
#   protonvpn-cli login jimmershere@proton.me   # interactive — needs your Proton password
#   protonvpn-cli connect --fastest
#
# Note: qBittorrent VPN uses Gluetun (Docker), not the host CLI. Both can coexist
# if you only use CLI for manual tests; Gluetun owns qBit traffic.

set -euo pipefail

PROTON_REPO_DEB="${PROTON_REPO_DEB:-https://repo.protonvpn.com/debian/dists/stable/main/binary-all/protonvpn-stable-release_1.0.8_all.deb}"
PROTON_ACCOUNT="${PROTON_ACCOUNT:-jimmershere@proton.me}"
RADTV_ROOT="${RADTV_ROOT:-}"

log() { printf '>> %s\n' "$*"; }
warn() { printf '!! %s\n' "$*" >&2; }

if [[ "$(id -u)" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

# --- 1. Repair apt/dpkg -----------------------------------------------------
log "repairing apt/dpkg state"
rm -f /var/lib/apt/lists/lock /var/cache/apt/archives/lock /var/lib/dpkg/lock* 2>/dev/null || true
dpkg --configure -a || true
apt-get -f install -y || true

# Remove broken partial Proton installs from earlier attempts
for pkg in protonvpn-stable-release protonvpn-beta-release \
           proton-vpn-cli proton-vpn-gnome-desktop protonvpn-cli; do
  dpkg -l "$pkg" 2>/dev/null | grep -q '^..r' && apt-get remove --purge -y "$pkg" || true
done
apt-get autoremove -y || true

log "apt update (pre-repo)"
apt-get update -y || {
  warn "apt update failed — retrying with clean lists"
  rm -rf /var/lib/apt/lists/*
  apt-get clean
  apt-get update -y
}

# --- 2. Official Proton VPN apt repository ----------------------------------
log "installing Proton VPN apt repository"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
deb="$tmpdir/protonvpn-stable-release.deb"
if command -v wget >/dev/null; then
  wget -qO "$deb" "$PROTON_REPO_DEB"
elif command -v curl >/dev/null; then
  curl -fsSL -o "$deb" "$PROTON_REPO_DEB"
else
  apt-get install -y wget curl
  wget -qO "$deb" "$PROTON_REPO_DEB"
fi
dpkg -i "$deb"
apt-get update -y

log "installing proton-vpn-cli + dependencies"
apt-get install -y proton-vpn-cli gnome-keyring network-manager libnss3-tools || {
  warn "proton-vpn-cli install failed — see apt output above"
}

if command -v protonvpn-cli >/dev/null; then
  log "proton-vpn-cli installed: $(protonvpn-cli --version 2>/dev/null || protonvpn-cli version 2>/dev/null || echo ok)"
else
  warn "proton-vpn-cli not in PATH after install"
fi

# --- 3. Find WireGuard config in /tmp for Gluetun ---------------------------
find_wg_conf() {
  local f
  for f in /tmp/*.conf /tmp/*proton* /tmp/*wg* /tmp/*radtv*; do
    [[ -f "$f" ]] || continue
    if grep -qi 'PrivateKey' "$f" 2>/dev/null; then
      echo "$f"
      return 0
    fi
  done
  return 1
}

WG_CONF=""
if WG_CONF="$(find_wg_conf)"; then
  log "found WireGuard config: $WG_CONF"
else
  warn "no WireGuard config in /tmp — Gluetun step will need WIREGUARD_PRIVATE_KEY manually"
fi

# --- 4. Wire Gluetun (Docker) for qBittorrent -------------------------------
if [[ -z "$RADTV_ROOT" ]]; then
  for d in /app/radtv /app/radtv/radtv "$HOME/radtv" /datapool/preserved/radtv-arr/..; do
    if [[ -f "$d/tools/floor2-set-gluetun-proton.py" ]]; then
      RADTV_ROOT="$d"
      break
    fi
  done
fi

if [[ -n "$RADTV_ROOT" && -f "$RADTV_ROOT/tools/floor2-set-gluetun-proton.py" ]]; then
  log "configuring Gluetun via $RADTV_ROOT/tools/floor2-set-gluetun-proton.py"
  export FLOOR2_STACK="${FLOOR2_STACK:-/datapool/preserved/badtv-arr}"
  if [[ -n "$WG_CONF" ]]; then
    export PROTON_WG_CONF="$WG_CONF"
  fi
  # Run as floor2 user if we're root
  if [[ -n "${SUDO_USER:-}" ]]; then
    sudo -u "$SUDO_USER" -E python3 "$RADTV_ROOT/tools/floor2-set-gluetun-proton.py"
  else
    python3 "$RADTV_ROOT/tools/floor2-set-gluetun-proton.py"
  fi
else
  warn "radtv repo not found — skip Gluetun auto-config"
  warn "  run manually: PROTON_WG_CONF=/tmp/your.conf ./radtv repair gluetun"
fi

# --- 5. Optional: host WireGuard (headless-friendly fallback) ---------------
if [[ -n "$WG_CONF" ]]; then
  log "installing host WireGuard config at /etc/wireguard/proton-radtv.conf (optional fallback)"
  apt-get install -y wireguard-tools iproute2 2>/dev/null || true
  install -d -m 0700 /etc/wireguard
  cp "$WG_CONF" /etc/wireguard/proton-radtv.conf
  chmod 600 /etc/wireguard/proton-radtv.conf
  log "host WG config installed (not auto-started — use: sudo wg-quick up proton-radtv)"
fi

# --- 6. Summary -------------------------------------------------------------
cat <<EOF

================================================================================
 Proton setup on floor2 — next steps
================================================================================

1) Log in to Proton VPN CLI (interactive — needs your Proton password):
     protonvpn-cli login $PROTON_ACCOUNT

2) Connect (optional — for host egress tests):
     protonvpn-cli connect --fastest
     protonvpn-cli status

3) qBittorrent uses Docker Gluetun (port 8091), not the host CLI.
   Check Gluetun:
     cd /datapool/preserved/badtv-arr && docker compose ps gluetun qbittorrent
     docker compose logs --tail=30 gluetun

4) qBittorrent Web UI: http://192.168.1.206:8091  (user: jimmer)

Headless note: Proton CLI officially wants NetworkManager + keyring. If login
fails on this NAS, Gluetun + WireGuard in Docker is the supported path for
qBittorrent — that part was configured above from $WG_CONF.

================================================================================
EOF
