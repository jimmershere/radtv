#!/usr/bin/env bash
# Show the current public IP as seen by multiple independent echo services.
# If they all agree on a non-ISP address, your VPN is working.
#
# No installation needed. Read-only. Hits public endpoints over HTTPS.
#
# Usage:
#   bash tools/network/vpn-status.sh
#   bash tools/network/vpn-status.sh --quiet     # one-line summary
#   bash tools/network/vpn-status.sh --json      # machine-readable

set -uo pipefail

MODE="default"
case "${1:-}" in
  --quiet|-q) MODE="quiet" ;;
  --json|-j)  MODE="json"  ;;
  --help|-h)
    sed -n '2,/^$/p' "$0"
    exit 0
    ;;
esac

ensure_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}
ensure_cmd curl

# Each entry: "label|url|jq-path-or-line"  where line is "raw" for plain text.
SERVICES=(
  "ipinfo.io|https://ipinfo.io/json|json"
  "ifconfig.io|https://ifconfig.io/all.json|json"
  "icanhazip|https://ipv4.icanhazip.com|raw"
)

TIMEOUT=8

fetch_ip() {
  local label="$1" url="$2" kind="$3"
  local raw ip="" country="" asn=""
  if ! raw="$(curl --silent --show-error --max-time "$TIMEOUT" --location "$url" 2>/dev/null)"; then
    echo "${label}|ERR||"
    return
  fi
  case "$kind" in
    raw)
      ip="$(echo "$raw" | tr -d '[:space:]')"
      ;;
    json)
      ip="$(echo "$raw"     | grep -oE '"ip"[[:space:]]*:[[:space:]]*"[^"]+"' | head -n1 | sed 's/.*"\([^"]\+\)"$/\1/')"
      country="$(echo "$raw" | grep -oE '"country(_iso)?"[[:space:]]*:[[:space:]]*"[^"]+"' | head -n1 | sed 's/.*"\([^"]\+\)"$/\1/')"
      asn="$(echo "$raw"     | grep -oE '"(org|asn|asn_org)"[[:space:]]*:[[:space:]]*"[^"]+"' | head -n1 | sed 's/.*"\([^"]\+\)"$/\1/')"
      ;;
  esac
  echo "${label}|${ip}|${country}|${asn}"
}

results=()
for spec in "${SERVICES[@]}"; do
  IFS='|' read -r label url kind <<< "$spec"
  results+=("$(fetch_ip "$label" "$url" "$kind")")
done

# Consistency check
ips=()
for r in "${results[@]}"; do
  IFS='|' read -r _ ip _ _ <<< "$r"
  [[ -n "$ip" && "$ip" != "ERR" ]] && ips+=("$ip")
done
agree="no"
if (( ${#ips[@]} >= 2 )); then
  uniq_count="$(printf '%s\n' "${ips[@]}" | sort -u | wc -l)"
  [[ "$uniq_count" == "1" ]] && agree="yes"
fi

case "$MODE" in
  json)
    printf '{\n'
    printf '  "consistent": %s,\n' "$([[ "$agree" == "yes" ]] && echo true || echo false)"
    printf '  "results": [\n'
    sep=""
    for r in "${results[@]}"; do
      IFS='|' read -r label ip country asn <<< "$r"
      printf '%s    {"service": "%s", "ip": "%s", "country": "%s", "asn": "%s"}' \
             "$sep" "$label" "$ip" "$country" "$asn"
      sep=$',\n'
    done
    printf '\n  ]\n}\n'
    ;;
  quiet)
    if [[ "$agree" == "yes" ]]; then
      echo "${ips[0]} (consistent across ${#ips[@]} services)"
    else
      echo "INCONSISTENT: ${ips[*]:-no responses}"
    fi
    ;;
  *)
    printf '\nPublic IP as seen by:\n'
    for r in "${results[@]}"; do
      IFS='|' read -r label ip country asn <<< "$r"
      printf '  %-12s  %-16s  %-4s  %s\n' "$label" "${ip:-?}" "${country:-?}" "${asn:-?}"
    done
    printf '\n'
    if [[ "$agree" == "yes" ]]; then
      printf '  -> All services agree: \033[1;32m%s\033[0m\n' "${ips[0]}"
      printf '  -> Compare with your ISP-assigned IP. If different, your VPN is working.\n'
    else
      printf '  -> Services disagree or some failed -- treat the result with suspicion.\n'
    fi
    ;;
esac
