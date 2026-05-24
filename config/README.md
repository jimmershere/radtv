# `config/` — B@Dtv configuration

Single source of truth for paths, hosts, and feature flags. Everything else
in the repo reads from here.

## Files

- **`badtv.conf.example`** — checked-in defaults. Don't edit; copy first.
- **`badtv.conf`** — your local overrides. Gitignored. Optional — if absent,
  the example values are used unchanged.
- **`load.sh`** — sourced by shell scripts. Layers `badtv.conf` over
  `badtv.conf.example` and exports the result.

## Typical setup

```bash
cp config/badtv.conf.example config/badtv.conf
$EDITOR config/badtv.conf       # change FLOOR2_HOST, repo URL, etc.
```

Then any of the entry points (`install.sh`, `media-server/setup-nfs.sh`,
`make iptv`, etc.) pick up your overrides automatically.

## Why a single config file

The previous TerraKodi layout hardcoded `192.168.1.206`, `datapool`, and the
GitHub repo URL across half a dozen scripts and XML files. One file means one
edit when you move boxes or fork the repo.
