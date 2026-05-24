#!/usr/bin/env bash
# Source this file from any B@Dtv shell script:
#
#   source "$(dirname "$0")/../config/load.sh"
#
# Loads config/badtv.conf if present, then config/badtv.conf.example as
# fallback for defaults. After loading, all BADTV_*/FLOOR2_*/IPTV_*/etc.
# variables are exported.

set -u

_load_sh_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Always load the example first so every variable has a default value.
# shellcheck source=./badtv.conf.example
source "${_load_sh_dir}/badtv.conf.example"

# Then layer the user's override file on top if it exists.
if [[ -f "${_load_sh_dir}/badtv.conf" ]]; then
  # shellcheck disable=SC1091
  source "${_load_sh_dir}/badtv.conf"
fi

# Export everything that looks like B@Dtv config so child processes inherit it.
while IFS= read -r _var; do
  export "${_var?}"
done < <(compgen -v | grep -E '^(BADTV_|FLOOR2_|IPTV_|KODI_|ENABLE_)')

unset _load_sh_dir _var
