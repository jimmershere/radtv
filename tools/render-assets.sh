#!/usr/bin/env bash
# Rasterize assets/branding/*.svg into PNG/JPG and copy to addon dirs.
set -euo pipefail

cd "$(dirname "$0")/.."

SRC="assets/branding"
ADDON_WIZARD="build/wizard"
ADDON_REPO="build/repository"

if command -v rsvg-convert >/dev/null 2>&1; then
  RENDER="rsvg-convert"
elif command -v inkscape >/dev/null 2>&1; then
  RENDER="inkscape"
elif command -v convert >/dev/null 2>&1; then
  RENDER="convert"
else
  cat >&2 <<EOF
No SVG renderer found. Install one of:
  - rsvg-convert (Linux: apt install librsvg2-bin; macOS: brew install librsvg)
  - inkscape
  - ImageMagick (convert) -- lower quality fallback

Skipping rasterization. The SVG sources are still in $SRC and Kodi will
happily use them, but a few skins want PNG/JPG specifically.
EOF
  exit 0
fi

render_png() {
  local src="$1" dst="$2" width="$3"
  case "$RENDER" in
    rsvg-convert) rsvg-convert -w "$width" "$src" -o "$dst" ;;
    inkscape)     inkscape "$src" --export-type=png --export-width="$width" --export-filename="$dst" >/dev/null ;;
    convert)      convert -background none -density 300 -resize "${width}x" "$src" "$dst" ;;
  esac
  echo "  rendered $dst (${width}px)"
}

render_jpg() {
  local src="$1" dst="$2" width="$3"
  local tmp
  tmp="$(mktemp --suffix=.png)"
  render_png "$src" "$tmp" "$width"
  if command -v convert >/dev/null 2>&1; then
    convert "$tmp" -background "#0B0B0D" -alpha remove -quality 90 "$dst"
  elif python3 -c 'from PIL import Image' >/dev/null 2>&1; then
    python3 - "$tmp" "$dst" <<'PY'
import sys
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGBA")
bg = Image.new("RGB", im.size, (11, 11, 13))  # soot.black
bg.paste(im, mask=im.split()[-1])
bg.save(dst, "JPEG", quality=90, optimize=True)
PY
  else
    cp "$tmp" "${dst%.jpg}.png"
    echo "  (no 'convert' or Pillow for jpg conversion; left as ${dst%.jpg}.png)"
  fi
  rm -f "$tmp"
}

echo "Rasterizing with $RENDER..."

# icon: 256 + 512 PNG
render_png "$SRC/icon.svg" "$SRC/icon-256.png" 256
render_png "$SRC/icon.svg" "$SRC/icon-512.png" 512

# fanart: 1920 wide JPG
render_jpg "$SRC/fanart.svg" "$SRC/fanart.jpg" 1920

# splash: 1920 wide PNG (keep transparency)
render_png "$SRC/splash.svg" "$SRC/splash.png" 1920

# wide logo: 1200 wide PNG
render_png "$SRC/logo.svg" "$SRC/logo.png" 1200

echo "Copying addon-ready assets into build/..."
mkdir -p "$ADDON_WIZARD" "$ADDON_REPO"
cp "$SRC/icon-256.png" "$ADDON_WIZARD/icon.png"
cp "$SRC/icon-256.png" "$ADDON_REPO/icon.png"
cp "$SRC/fanart.jpg"   "$ADDON_WIZARD/fanart.jpg" 2>/dev/null || true
cp "$SRC/fanart.jpg"   "$ADDON_REPO/fanart.jpg"   2>/dev/null || true

echo "Done."
