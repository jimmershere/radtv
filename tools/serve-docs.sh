#!/usr/bin/env bash
# Serve R&Dtv documentation over HTTP so HTML guides open in a browser.
#
# Usage:
#   bash tools/serve-docs.sh              # default port 8765
#   DOCS_PORT=9000 bash tools/serve-docs.sh
#
# Then open:
#   http://127.0.0.1:8765/                # docs index
#   http://127.0.0.1:8765/ARCHITECTURE.html
#
# In Cursor: check the Ports panel for a forwarded URL after starting.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCS_DIR="$REPO_ROOT/docs"
DOCS_PORT="${DOCS_PORT:-8765}"
HOST="${DOCS_HOST:-0.0.0.0}"

if [[ ! -f "$DOCS_DIR/index.html" ]]; then
  echo "docs/index.html not found under $DOCS_DIR" >&2
  exit 1
fi

echo "R&Dtv docs server"
echo "  Directory: $DOCS_DIR"
echo "  URL:       http://${HOST}:${PORT}/"
echo "  Tutorial:  http://${HOST}:${PORT}/ARCHITECTURE.html"
echo ""
echo "Press Ctrl+C to stop."

cd "$DOCS_DIR"
exec python3 -m http.server "$PORT" --bind "$HOST"
