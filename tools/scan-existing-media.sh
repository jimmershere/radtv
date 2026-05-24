#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/media}"
REPORT="${2:-media-scan-report.tsv}"

if ! command -v mediainfo >/dev/null 2>&1; then
  echo "mediainfo is required" >&2
  exit 1
fi

printf "file\twidth\theight\tvcodec\taudio_codec\tcontainer\tstatus\n" > "$REPORT"

find "$ROOT" -type f \( -iname '*.mkv' -o -iname '*.mp4' -o -iname '*.avi' -o -iname '*.m4v' \) -print0 |
while IFS= read -r -d '' file; do
  width=$(mediainfo --Inform='Video;%Width%' "$file" 2>/dev/null | head -n1)
  height=$(mediainfo --Inform='Video;%Height%' "$file" 2>/dev/null | head -n1)
  vcodec=$(mediainfo --Inform='Video;%Format%' "$file" 2>/dev/null | head -n1)
  acodec=$(mediainfo --Inform='Audio;%Format%' "$file" 2>/dev/null | head -n1)
  container=$(mediainfo --Inform='General;%Format%' "$file" 2>/dev/null | head -n1)

  status="watchable"
  if [[ -z "$height" ]]; then
    status="inspect"
  elif (( height < 720 )); then
    status="reencode_or_replace"
  elif [[ "$vcodec" =~ MPEG-4\ Visual|XviD|DivX ]]; then
    status="consider_upgrade"
  fi

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$file" "${width:-unknown}" "${height:-unknown}" "${vcodec:-unknown}" "${acodec:-unknown}" "${container:-unknown}" "$status" >> "$REPORT"
done

echo "Wrote report to $REPORT"
