#!/usr/bin/env bash
# Open R&Dtv HTML docs on THIS machine — no cloud VM required.
#
#   ./open-docs.sh           # open ARCHITECTURE.html via file:// (no server)
#   ./open-docs.sh --serve   # start http://127.0.0.1:8765/ locally

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

if [[ "${1:-}" == "--serve" ]]; then
  shift
  exec python3 "$HERE/bootstrap.py" docs "$@"
fi

exec python3 "$HERE/bootstrap.py" docs --open "$@"
