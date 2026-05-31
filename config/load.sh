#!/usr/bin/env bash
# Source this file from any R&Dtv shell script:
#
#   source "$(dirname "$0")/../config/load.sh"
#
# Loads config/radtv.conf if present, then config/radtv.conf.example as
# fallback for defaults. After loading, all RADTV_*/FLOOR2_*/IPTV_*/etc.
# variables are exported.

set -u

_load_sh_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Always load the example first so every variable has a default value.
# shellcheck source=./radtv.conf.example
source "${_load_sh_dir}/radtv.conf.example"

# Then layer the user's override file on top if it exists.
if [[ -f "${_load_sh_dir}/radtv.conf" ]]; then
  # shellcheck disable=SC1091
  source "${_load_sh_dir}/radtv.conf"
fi

# Export everything that looks like R&Dtv config so child processes inherit it.
while IFS= read -r _var; do
  export "${_var?}"
done < <(compgen -v | grep -E '^(RADTV_|FLOOR2_|IPTV_|KODI_|ENABLE_)')

unset _load_sh_dir _var
