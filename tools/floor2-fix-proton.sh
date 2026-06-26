#!/usr/bin/env bash
# Repair apt on floor2 and configure ProtonVPN for qBittorrent via Gluetun (Docker).
#
# IMPORTANT: `protonvpn signin` does NOT work on headless NAS (no dbus/keyring).
# qBittorrent VPN uses Gluetun + a WireGuard .conf from your Proton account —
# you never need the host Proton CLI for torrents.
#
# Run ON floor2:
#   cd /app/radtv && git pull
#   bash tools/floor2-import-wireguard.sh /tmp/your-proton.conf   # preferred
#
# Full apt repair + optional CLI install:
#   sudo bash tools/floor2-fix-proton.sh
#
# Or from quasimodo:
#   ssh floor2 'bash -s' < tools/floor2-fix-proton.sh

set -euo pipefail

PROTON_REPO_DEB="${PROTON_REPO_DEB:-https://repo.protonvpn.com/debian/dists/stable/main/binary-all/protonvpn-stable-release_1.0.8_all.deb}"
PROTON_ACCOUNT="${PROTON_ACCOUNT:-jimmershere@proton.me}"
RADTV_ROOT="${RADTV_ROOT:-}"
# Headless NAS: skip heavy CLI install unless you have a desktop session
SKIP_PROTON_CLI="${SKIP_PROTON_CLI:-1}"

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

# --- 2. Optional: Proton VPN CLI (desktop / NetworkManager — not headless) ---
if [[ "$SKIP_PROTON_CLI" == "1" ]]; then
  log "SKIP_PROTON_CLI=1 — skipping proton-vpn-cli (does not work headless)"
  log "  use Gluetun + WireGuard instead: bash tools/floor2-import-wireguard.sh"
else
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

  if command -v protonvpn >/dev/null; then
    log "protonvpn installed: $(protonvpn --version 2>/dev/null || echo ok)"
    warn "signin needs a desktop dbus session — will fail over SSH on floor2"
    warn "  dbus-run-session -- protonvpn signin $PROTON_ACCOUNT   # may still fail"
  elif command -v protonvpn-cli >/dev/null; then
    log "protonvpn-cli installed (legacy wrapper)"
  else
    warn "protonvpn not in PATH after install"
  fi
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
  warn "no WireGuard config in /tmp — download one from account.proton.me/vpn/WireGuard"
fi

# --- 4. Wire Gluetun (Docker) for qBittorrent -------------------------------
if [[ -z "$RADTV_ROOT" ]]; then
  for d in /app/radtv /app/radtv/radtv "$HOME/radtv" /datapool/preserved/radtv-arr/..; do
    if [[ -f "$d/tools/floor2-import-wireguard.sh" ]]; then
      RADTV_ROOT="$d"
      break
    fi
  done
fi

IMPORT_SH=""
if [[ -n "$RADTV_ROOT" && -f "$RADTV_ROOT/tools/floor2-import-wireguard.sh" ]]; then
  IMPORT_SH="$RADTV_ROOT/tools/floor2-import-wireguard.sh"
elif [[ -f "$(dirname "$0")/floor2-import-wireguard.sh" ]]; then
  IMPORT_SH="$(dirname "$0")/floor2-import-wireguard.sh"
  RADTV_ROOT="$(dirname "$0")/.."
fi

if [[ -n "$IMPORT_SH" && -n "$WG_CONF" ]]; then
  log "configuring Gluetun via $IMPORT_SH"
  export FLOOR2_STACK="${FLOOR2_STACK:-/datapool/preserved/badtv-arr}"
  run_user="${SUDO_USER:-floor2}"
  if id "$run_user" &>/dev/null; then
    sudo -u "$run_user" -E bash "$IMPORT_SH" "$WG_CONF"
  else
    bash "$IMPORT_SH" "$WG_CONF"
  fi
  GLUETUN_CONFIGURED=1
elif [[ -n "$IMPORT_SH" ]]; then
  warn "skip Gluetun — no WireGuard .conf in /tmp yet"
  warn "  scp your Proton .conf to floor2:/tmp/ then:"
  warn "  bash $IMPORT_SH /tmp/your.conf"
else
  warn "radtv repo not found — skip Gluetun auto-config"
fi

# --- 5. Optional: host WireGuard (headless-friendly fallback) ---------------
if [[ -n "$WG_CONF" ]]; then
  log "installing host WireGuard config at /etc/wireguard/proton-radtv.conf (optional)"
  apt-get install -y wireguard-tools iproute2 2>/dev/null || true
  install -d -m 0700 /etc/wireguard
  cp "$WG_CONF" /etc/wireguard/proton-radtv.conf
  chmod 600 /etc/wireguard/proton-radtv.conf
  log "host WG (optional): sudo wg-quick up proton-radtv"
fi

# --- 6. Summary -------------------------------------------------------------
if [[ "${GLUETUN_CONFIGURED:-0}" == "1" ]]; then
  cat <<EOF

================================================================================
 Done — Gluetun configured from $WG_CONF
================================================================================

 qBittorrent VPN is ready. You do NOT need protonvpn or protonvpn-cli on floor2.

 Check:
   cd /datapool/preserved/badtv-arr && docker compose ps gluetun qbittorrent
   docker compose logs --tail=30 gluetun

 qBittorrent Web UI: http://192.168.1.206:8091  (user: jimmer)

 Ignore any old docs that say "protonvpn-cli login" — that command does not
 exist on current Proton packages (use \`protonvpn\` on desktops only) and
 signin fails on headless NAS anyway. Gluetun + WireGuard is the path.

================================================================================
EOF
  exit 0
fi

cat <<EOF

================================================================================
 floor2 VPN — headless path (no protonvpn signin)
================================================================================

 qBittorrent uses Docker Gluetun, NOT the host Proton CLI.

 1) Download WireGuard config (browser, any machine):
      https://account.proton.me/vpn/WireGuard

 2) Copy to floor2 and import:
      scp ~/Downloads/us-free.conf floor2:/tmp/
      ssh floor2 'cd /app/radtv && bash tools/floor2-import-wireguard.sh /tmp/us-free.conf'

    Or on floor2 directly:
      cd /app/radtv && bash tools/floor2-import-wireguard.sh /tmp/us-free.conf

 3) Check Gluetun + qBit:
      cd /datapool/preserved/badtv-arr && docker compose ps gluetun qbittorrent
      docker compose logs --tail=30 gluetun

 4) qBittorrent Web UI: http://192.168.1.206:8091  (user: jimmer)

 Why signin fails:
   protonvpn signin needs GNOME keyring + dbus (desktop session).
   floor2 is headless — Proton documents that CLI does not support headless.
   sudo protonvpn signin makes it worse (wrong user session).
   You do not need signin for Gluetun/qBittorrent.

 Optional host CLI (desktop only): SKIP_PROTON_CLI=0 bash tools/floor2-fix-proton.sh
   then on a machine WITH a display: dbus-run-session -- protonvpn signin $PROTON_ACCOUNT

================================================================================
EOF
