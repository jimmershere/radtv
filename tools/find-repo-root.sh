#!/usr/bin/env bash
# Locate the R&Dtv repo root (directory containing bootstrap.py).
# Prints one absolute path on success; exits 1 if not found.
set -euo pipefail

try_root() {
  local d="$1"
  [[ -n "$d" && -f "$d/bootstrap.py" ]] || return 1
  (cd "$d" && pwd -P)
}

# 1. Directory containing this script's repo (tools/ -> parent)
_script="${BASH_SOURCE[0]}"
if [[ "$_script" != /* ]]; then
  _script="$(pwd -P)/$_script"
fi
_tools_dir="$(cd "$(dirname "$_script")" && pwd -P)"
try_root "$(dirname "$_tools_dir")" && exit 0

# 2. Explicit override
if [[ -n "${RADTV_ROOT:-}" ]]; then
  try_root "$RADTV_ROOT" && exit 0
fi

# 3. Walk upward from cwd (max 6 levels)
_here="$(pwd -P)"
_d="$_here"
for _ in 1 2 3 4 5 6; do
  try_root "$_d" && exit 0
  [[ "$_d" == "/" ]] && break
  _d="$(dirname "$_d")"
done

# 4. Common install paths (TheClawFirm / quasimodo layouts)
for _cand in \
  "/app/radtv" \
  "/app/radtv/radtv" \
  "$HOME/radtv" \
  "$HOME/src/radtv" \
  "/app/warp/R&Dtv" \
  "/app/warp/radtv"
do
  try_root "$_cand" && exit 0
done

# 5. One-level nested clone: ./radtv/bootstrap.py from cwd
try_root "$_here/radtv" && exit 0
try_root "$_here/radtv/radtv" && exit 0

echo "radtv: cannot find bootstrap.py" >&2
exit 1
