#!/usr/bin/env bash
# Bring up a user-supplied WireGuard configuration as the `badtv-wg`
# interface, with an nftables kill-switch that prevents traffic egress when
# the tunnel is down.
#
# Usage:
#   sudo bash tools/network/setup-wireguard.sh /path/to/provider.conf
#   sudo bash tools/network/setup-wireguard.sh /path/to/provider.conf --dry-run
#   sudo bash tools/network/setup-wireguard.sh --down       # take it down
#   sudo bash tools/network/setup-wireguard.sh --status     # show state
#
# B@Dtv does not provide WireGuard configs. Get one from your VPN provider
# (Mullvad, ProtonVPN, IVPN all have a "Generate WireGuard config" page).
#
# This script DOES NOT verify or vouch for your provider's configuration.
# It installs the tooling, copies the file with secure permissions, brings
# the interface up, and optionally adds a firewall rule that drops non-WG
# egress so a tunnel drop doesn't transparently re-expose your real IP.

set -euo pipefail

IFACE="badtv-wg"
CONF_DST="/etc/wireguard/${IFACE}.conf"
DRY_RUN=0
ACTION="up"

note() { printf '\033[33m>>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32mok\033[0m %s\n' "$*"; }
warn() { printf '\033[31m!!\033[0m %s\n' "$*" >&2; }
run()  { if (( DRY_RUN )); then echo "  (dry) $*"; else eval "$*"; fi; }

usage() {
  sed -n '2,/^$/p' "$0"
  exit "${1:-0}"
}

# --- parse args ------------------------------------------------------------
CONF_SRC=""
for arg in "$@"; do
  case "$arg" in
    --dry-run|-n) DRY_RUN=1 ;;
    --down)       ACTION="down" ;;
    --status)     ACTION="status" ;;
    --help|-h)    usage 0 ;;
    --*)          warn "unknown flag: $arg"; usage 1 ;;
    *)            CONF_SRC="$arg" ;;
  esac
done

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    warn "Run as root (sudo)."
    exit 1
  fi
}

ensure_cmd() {
  command -v "$1" >/dev/null 2>&1 || return 1
}

install_wg_tools() {
  if ensure_cmd wg-quick && ensure_cmd wg; then
    ok "wireguard-tools already installed"
    return
  fi
  note "installing wireguard-tools"
  if ensure_cmd apt-get; then
    run "apt-get update -qq && apt-get install -y wireguard-tools nftables iproute2"
  elif ensure_cmd dnf; then
    run "dnf install -y wireguard-tools nftables iproute"
  elif ensure_cmd pacman; then
    run "pacman -Sy --noconfirm wireguard-tools nftables iproute2"
  else
    warn "Unknown package manager. Install wireguard-tools + nftables + iproute2 by hand and re-run."
    exit 1
  fi
}

apply_kill_switch() {
  # nftables table: drop all egress except: (a) traffic on the WG interface,
  # (b) traffic TO the WG peer endpoint (so the tunnel can establish), and
  # (c) local-loopback. Inbound is left to whatever your existing policy is.
  note "installing nftables kill-switch (table 'badtv-killswitch')"
  local peer_endpoint
  peer_endpoint="$(awk -F' *= *' '/^[[:space:]]*Endpoint/ {gsub(":.*","",$2); print $2; exit}' "$CONF_DST" || true)"
  if [[ -z "$peer_endpoint" ]]; then
    warn "Could not parse Endpoint from $CONF_DST -- kill-switch skipped."
    return
  fi
  cat > /etc/nftables.d/badtv-killswitch.nft <<EOF
table inet badtv-killswitch {
    chain output {
        type filter hook output priority -100; policy accept;
        oifname "lo" accept
        oifname "${IFACE}" accept
        ip daddr ${peer_endpoint} accept
        meta skuid root accept comment "let root resolve DNS to bring tunnel up"
        ct state established,related accept
        # Drop everything else if the WG iface is not up.
        oifname != "${IFACE}" log prefix "[badtv-killswitch drop] " level info
        oifname != "${IFACE}" drop
    }
}
EOF
  run "mkdir -p /etc/nftables.d"
  run "nft -f /etc/nftables.d/badtv-killswitch.nft"
  ok "kill-switch active for endpoint $peer_endpoint"
}

drop_kill_switch() {
  if [[ -f /etc/nftables.d/badtv-killswitch.nft ]]; then
    note "removing kill-switch"
    run "nft delete table inet badtv-killswitch 2>/dev/null || true"
    run "rm -f /etc/nftables.d/badtv-killswitch.nft"
    ok "kill-switch removed"
  fi
}

bring_up() {
  require_root
  if [[ -z "$CONF_SRC" ]]; then
    warn "provide the path to your WireGuard .conf as the first argument"
    usage 1
  fi
  if [[ ! -f "$CONF_SRC" ]]; then
    warn "config not found: $CONF_SRC"
    exit 1
  fi
  install_wg_tools

  note "copying $CONF_SRC -> $CONF_DST (mode 600)"
  run "install -d -m 0700 /etc/wireguard"
  run "install -m 0600 \"$CONF_SRC\" \"$CONF_DST\""

  if ip link show "$IFACE" >/dev/null 2>&1; then
    note "interface $IFACE already up -- bouncing it"
    run "wg-quick down $IFACE || true"
  fi
  run "wg-quick up $IFACE"
  run "systemctl enable wg-quick@${IFACE} 2>/dev/null || true"
  ok "WireGuard tunnel $IFACE is up"

  apply_kill_switch

  echo
  note "verifying public IP via tools/network/vpn-status.sh"
  bash "$(dirname "$0")/vpn-status.sh" || true
}

bring_down() {
  require_root
  if ip link show "$IFACE" >/dev/null 2>&1; then
    run "wg-quick down $IFACE"
    run "systemctl disable wg-quick@${IFACE} 2>/dev/null || true"
  fi
  drop_kill_switch
  ok "WireGuard tunnel $IFACE is down"
}

show_status() {
  if ip link show "$IFACE" >/dev/null 2>&1; then
    echo "interface: up"
    wg show "$IFACE" 2>/dev/null || true
  else
    echo "interface: down"
  fi
  if [[ -f /etc/nftables.d/badtv-killswitch.nft ]]; then
    echo "kill-switch: installed"
  else
    echo "kill-switch: not installed"
  fi
  bash "$(dirname "$0")/vpn-status.sh" --quiet 2>/dev/null | sed 's/^/public-ip: /'
}

case "$ACTION" in
  up)     bring_up ;;
  down)   bring_down ;;
  status) show_status ;;
esac
