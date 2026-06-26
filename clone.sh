#!/usr/bin/env bash
# Canonical clone — avoids the /app/radtv/radtv double-nesting trap.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/jimmershere/radtv/main/clone.sh | bash
#   bash clone.sh /app/radtv
#   bash clone.sh                    # defaults to ./radtv in cwd

set -euo pipefail

TARGET="${1:-$(pwd)/radtv}"
REPO_URL="${RADTV_REPO_URL:-https://github.com/jimmershere/radtv.git}"
BRANCH="${RADTV_BRANCH:-main}"

# Refuse to clone INTO an existing repo tree (causes radtv/radtv nesting).
if [[ -d "$TARGET/.git" ]]; then
  echo "Already a git repo: $TARGET" >&2
  echo "  cd $TARGET && git pull origin $BRANCH" >&2
  exit 1
fi
if [[ -d "$TARGET/radtv" && -f "$TARGET/radtv/bootstrap.py" ]]; then
  echo "Nested layout detected at $TARGET/radtv — flatten first:" >&2
  echo "  cd $TARGET && bash radtv/tools/fix-nested-clone.sh" >&2
  exit 1
fi

parent="$(dirname "$TARGET")"
base="$(basename "$TARGET")"
mkdir -p "$parent"

if [[ -e "$TARGET" ]]; then
  echo "Removing existing $TARGET"
  rm -rf "$TARGET"
fi

echo "Cloning $REPO_URL -> $TARGET (branch $BRANCH)"
git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$TARGET"

cd "$TARGET"
if [[ -f tools/fix-nested-clone.sh ]]; then
  bash tools/fix-nested-clone.sh || true
fi

echo ""
echo "Ready: cd $TARGET && ./radtv setup"
echo "       cd $TARGET && ./radtv repair sonarr"
