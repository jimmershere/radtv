#!/usr/bin/env bash
set -euo pipefail

REPORT="${1:-media-scan-report.tsv}"

if [[ ! -f "$REPORT" ]]; then
  echo "Report not found: $REPORT" >&2
  exit 1
fi

awk -F'\t' '
NR==1 { next }
{
  total++
  counts[$7]++
}
END {
  printf "Total files: %d\n", total
  for (k in counts) {
    printf "%s: %d\n", k, counts[k]
  }
}
' "$REPORT"
