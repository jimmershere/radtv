#!/usr/bin/env bash
# Wire up LAN SSH to floor2: ~/.ssh/config Host alias + optional /etc/hosts.
#
# After this, these all work from quasimodo:
#   ssh floor2
#   ssh floor2@floor2
#   ./radtv repair sonarr
#
# Usage:
#   bash tools/network/setup-floor2-ssh.sh
#   sudo ADD_HOSTS_ENTRY=1 bash tools/network/setup-floor2-ssh.sh
#   ./radtv repair floor2-ssh

set -euo pipefail

FLOOR2_IP="${FLOOR2_IP:-192.168.1.206}"
FLOOR2_USER="${FLOOR2_USER:-floor2}"
FLOOR2_NAME="${FLOOR2_NAME:-floor2}"
ADD_HOSTS_ENTRY="${ADD_HOSTS_ENTRY:-1}"

log() { printf '>> %s\n' "$*"; }
warn() { printf '!! %s\n' "$*" >&2; }

SSH_DIR="${HOME}/.ssh"
SSH_CONFIG="${SSH_DIR}/config"
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"
touch "$SSH_CONFIG"
chmod 600 "$SSH_CONFIG"

if grep -qE "^[Hh]ost[[:space:]]+${FLOOR2_NAME}([[:space:]]|$)" "$SSH_CONFIG"; then
  log "SSH config already has Host ${FLOOR2_NAME} — updating HostName/User block"
  # Replace existing Host floor2 stanza with fresh block
  awk -v name="$FLOOR2_NAME" '
    BEGIN { skip=0 }
    /^[Hh]ost[[:space:]]+/ {
      if ($2 == name) { skip=1; next }
      if (skip && /^[[:space:]]/) next
      skip=0
    }
    !skip { print }
  ' "$SSH_CONFIG" > "${SSH_CONFIG}.tmp"
  mv "${SSH_CONFIG}.tmp" "$SSH_CONFIG"
fi

cat >>"$SSH_CONFIG" <<EOF

# R&Dtv floor2 NAS — added by tools/network/setup-floor2-ssh.sh
Host ${FLOOR2_NAME}
  HostName ${FLOOR2_IP}
  User ${FLOOR2_USER}
  ServerAliveInterval 30
  ServerAliveCountMax 3
  StrictHostKeyChecking accept-new
EOF
chmod 600 "$SSH_CONFIG"
log "wrote Host ${FLOOR2_NAME} -> ${FLOOR2_USER}@${FLOOR2_IP} in ${SSH_CONFIG}"

if [[ "$ADD_HOSTS_ENTRY" == "1" ]]; then
  if grep -qE "[[:space:]]${FLOOR2_NAME}([[:space:]]|$)" /etc/hosts 2>/dev/null; then
    log "/etc/hosts already has ${FLOOR2_NAME}"
  else
    log "adding ${FLOOR2_IP} ${FLOOR2_NAME} to /etc/hosts (sudo)"
    echo "${FLOOR2_IP} ${FLOOR2_NAME}" | sudo tee -a /etc/hosts >/dev/null
  fi
fi

# Update radtv.conf if present
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CONF="${REPO_ROOT}/config/radtv.conf"
if [[ -f "$CONF" ]]; then
  if grep -q '^FLOOR2_HOST=' "$CONF"; then
    sed -i "s/^FLOOR2_HOST=.*/FLOOR2_HOST=\"${FLOOR2_NAME}\"/" "$CONF"
  else
    echo "FLOOR2_HOST=\"${FLOOR2_NAME}\"" >>"$CONF"
  fi
  log "set FLOOR2_HOST=${FLOOR2_NAME} in config/radtv.conf"
fi

log "testing ssh ${FLOOR2_NAME} ..."
if ssh -o BatchMode=yes -o ConnectTimeout=8 "${FLOOR2_NAME}" 'hostname && whoami'; then
  log "SSH OK — use: ssh ${FLOOR2_NAME}"
else
  warn "SSH test failed — ensure your public key is in ~${FLOOR2_USER}/.ssh/authorized_keys on floor2"
  warn "  ssh-copy-id ${FLOOR2_USER}@${FLOOR2_IP}"
  exit 1
fi
