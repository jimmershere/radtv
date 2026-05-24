#!/usr/bin/env bash
# Configure systemd-resolved to use DNS-over-TLS against Cloudflare 1.1.1.1
# and Quad9 9.9.9.9 with DNSSEC validation. Optional: skip if your VPN
# already pushes its own DNS (most privacy-focused providers do).
#
# Usage:
#   sudo bash tools/network/setup-dns.sh
#   sudo bash tools/network/setup-dns.sh --revert     # restore distro defaults
#   sudo bash tools/network/setup-dns.sh --dry-run

set -euo pipefail

DRY_RUN=0
ACTION="apply"

note() { printf '\033[33m>>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32mok\033[0m %s\n' "$*"; }
warn() { printf '\033[31m!!\033[0m %s\n' "$*" >&2; }
run()  { if (( DRY_RUN )); then echo "  (dry) $*"; else eval "$*"; fi; }

for arg in "$@"; do
  case "$arg" in
    --dry-run|-n) DRY_RUN=1 ;;
    --revert)     ACTION="revert" ;;
    --help|-h)    sed -n '2,/^$/p' "$0"; exit 0 ;;
    *)            warn "unknown flag: $arg"; exit 1 ;;
  esac
done

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    warn "Run as root (sudo)."
    exit 1
  fi
}

ensure_resolved() {
  if ! command -v resolvectl >/dev/null 2>&1; then
    warn "systemd-resolved not found. This helper only handles systemd-based distros."
    exit 1
  fi
  if ! systemctl is-enabled --quiet systemd-resolved 2>/dev/null; then
    note "enabling systemd-resolved"
    run "systemctl enable --now systemd-resolved"
  fi
}

apply() {
  require_root
  ensure_resolved

  local conf="/etc/systemd/resolved.conf.d/badtv-dns.conf"
  note "writing $conf"
  run "mkdir -p \"$(dirname "$conf")\""
  if (( ! DRY_RUN )); then
    cat > "$conf" <<'EOF'
# B@Dtv DNS-over-TLS overlay. Remove this file (or run setup-dns.sh --revert)
# to fall back to your distribution's defaults.
[Resolve]
DNS=1.1.1.1#cloudflare-dns.com 9.9.9.9#dns.quad9.net
FallbackDNS=1.0.0.1#cloudflare-dns.com 149.112.112.112#dns.quad9.net
DNSOverTLS=yes
DNSSEC=allow-downgrade
Cache=yes
DNSStubListener=yes
EOF
  fi

  # symlink /etc/resolv.conf to the systemd stub if it isn't already
  if [[ ! -L /etc/resolv.conf || "$(readlink /etc/resolv.conf)" != *systemd* ]]; then
    note "linking /etc/resolv.conf to systemd-resolved stub"
    run "ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf"
  fi

  run "systemctl restart systemd-resolved"
  sleep 1
  ok "DNS-over-TLS active. Current state:"
  resolvectl status | sed -n '/Global/,/Link/p' | head -20 || true
}

revert() {
  require_root
  local conf="/etc/systemd/resolved.conf.d/badtv-dns.conf"
  if [[ -f "$conf" ]]; then
    note "removing $conf"
    run "rm -f \"$conf\""
    run "systemctl restart systemd-resolved"
    ok "reverted to distribution-default DNS"
  else
    ok "no B@Dtv DNS overlay present; nothing to revert"
  fi
}

case "$ACTION" in
  apply)  apply ;;
  revert) revert ;;
esac
