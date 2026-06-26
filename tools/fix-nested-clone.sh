#!/usr/bin/env bash
# Fix a double-nested git clone (e.g. /app/radtv/radtv/...).
#
# Run from anywhere inside the repo, or from the parent that holds the
# extra inner "radtv" directory.
#
#   bash tools/fix-nested-clone.sh
#
# Idempotent: no-op if layout is already flat.

set -euo pipefail

_script="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$_script/../bootstrap.py" ]]; then
  REPO_ROOT="$(cd "$_script/.." && pwd -P)"
else
  REPO_ROOT="$(pwd -P)"
fi

flatten_into() {
  local dest="$1"
  local nested="$2"
  [[ -f "$nested/bootstrap.py" ]] || return 1

  echo "Flattening $nested -> $dest"
  # Rename source aside so we can move files named "radtv" without clashing
  # with the source directory basename.
  local staging="${nested}.__flatten__"
  rm -rf "$staging"
  mv "$nested" "$staging"
  nested="$staging"

  cd "$dest"
  shopt -s dotglob nullglob
  for item in "$nested"/* "$nested"/.[!.]* "$nested"/..?*; do
    [[ -e "$item" ]] || continue
    base="$(basename "$item")"
    if [[ -e "$dest/$base" ]]; then
      echo "  skip (exists): $base"
    else
      mv "$item" "$dest/"
      echo "  moved: $base"
    fi
  done
  rm -rf "$nested"
  if [[ ! -x "$dest/radtv" ]]; then
    echo "  ERROR: radtv launcher missing after flatten — re-clone with: bash clone.sh $dest" >&2
    return 1
  fi
  echo "Done. Repo root: $dest"
  return 0
}

# Case A: dest/radtv/bootstrap.py  (classic double nest)
if [[ -f "$REPO_ROOT/radtv/bootstrap.py" ]]; then
  flatten_into "$REPO_ROOT" "$REPO_ROOT/radtv"
  exit 0
fi

# Case B: we ARE the inner radtv (parent has no bootstrap.py)
if [[ -f "$REPO_ROOT/bootstrap.py" && "$(basename "$REPO_ROOT")" == "radtv" ]]; then
  parent="$(dirname "$REPO_ROOT")"
  if [[ ! -f "$parent/bootstrap.py" ]]; then
    if flatten_into "$parent" "$REPO_ROOT"; then
      exit 0
    fi
  fi
fi

echo "Layout OK — no radtv/radtv nesting to fix ($(pwd))"
exit 0
