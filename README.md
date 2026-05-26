# B@Dtv

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-6B1A1F.svg)](LICENSE)
![Kodi](https://img.shields.io/badge/Kodi-19%2B%20(Matrix%2FNexus%2FOmega)-D4A24C)
![Theme](https://img.shields.io/badge/Theme-Black%20Donnellys-0E3B2E)
![floor2](https://img.shields.io/badge/optional-floor2%20NAS-A89E84)

> **You are on the `fork/v2-torbox-usenet` branch (v3.0.0-fork).** This fork
> adds TorBox + Usenet as parallel backends, swaps FlareSolverr → Byparr,
> prunes zombie addons (The Crew, Crackle), and scaffolds optional Jellyfin.
> Driven by the May 2026 Real-Debrid filter event. See `CHANGELOG.md` for
> the full diff and `docs/grey-area-streaming-2026.pdf` for the why.

> **Read first**: [`DISCLAIMER.md`](DISCLAIMER.md) · [`NOTICE.md`](NOTICE.md) ·
> [`docs/PRIVACY.md`](docs/PRIVACY.md). B@Dtv is GPL-3.0 packaging software
> with no warranty. You decide what to install and what to stream;
> anonymization is not a license to infringe.

> Hell's Kitchen-grade Kodi build. Brick walls, whiskey amber, deep emerald,
> a back-bar full of streaming sources, and a wizard that actually does the
> work instead of waving at you.

**B@Dtv** (née *TerraKodi*) is TheClawFirm's pre-configured Kodi distribution
with a **Black Donnellys**-inspired UI — the brilliant, brief NBC drama about
four brothers running a Hell's Kitchen bar. The build pulls from the best
free / lawful US linear sources, the strongest community scrapers, and
(optionally) an NFS-mounted home media library.

## What ships

- **`build/wizard/`** — `script.badtv.wizard`. A real Kodi script addon (not
  a textviewer stub) with a menu of one-click actions: install the curated
  addon stack, wire PVR IPTV Simple Client to the bundled playlist,
  authorize Real-Debrid + Trakt, drop in the B@Dtv color theme, add NAS
  sources, kick a library scan.
- **`build/repository/`** — `repository.badtv`. The Kodi repository
  package that delivers the wizard.
- **`iptv/`** — Declarative `sources.yaml` + a Python builder that merges
  Pluto / Plex Live / Samsung TV+ / Stirr / iptv-org news / sports / music /
  international into a single deduped `badtv.m3u` + `badtv.xml`.
- **`assets/`** — Black Donnellys color tokens, SVG branding (logo, icon,
  fanart, splash), and drop-in skin color overrides for Arctic Zephyr
  Reloaded, Estuary MOD V2, and stock Estuary.
- **`config/badtv.conf.example`** — single source of truth for floor2 host,
  repo URL, IPTV toggles, skin target.
- **`install.sh` / `install.ps1`** — one-shot installer that writes
  `sources.xml`, `advancedsettings.xml`, `pvr.iptvsimple/settings.xml`,
  stages the repo zip, and applies the skin override.
- **`media-server/`** — `setup-nfs.sh` / `setup-smb.sh` for the floor2 NAS
  (or any NAS you point them at).
- **`tools/`** — `render-assets.sh` (rasterize SVGs), `build-repo.py` (zip
  packaging), `scan-existing-media.sh` (quality audit).

## Quick install

```bash
git clone https://github.com/jimmershere/badtv.git
cd badtv
./badtv setup
```

That single command is the entire first run. It:

1. apt-installs Kodi + every binary helper addon Debian doesn't bundle by
   default (`kodi-inputstream-adaptive`, `kodi-pvr-iptvsimple`, `mpv`,
   `wireguard-tools`, `nftables`, ...).
2. Stands up a VPN (ExpressVPN / Mullvad / Proton / IVPN / generic
   WireGuard / skip) with a kill-switch.
3. Bootstraps `~/.kodi/userdata/` and writes a sane
   `advancedsettings.xml` for streaming.
4. Drops the B@Dtv repository + wizard addons into
   `~/.kodi/addons/`.
5. Pulls Kodi-official addons (YouTube, Pluto TV, Crackle, PlexMod,
   Arctic Zephyr MOD skin) straight from `mirrors.kodi.tv` -- bypasses
   Kodi entirely so dependency resolution can't fail mid-run.
6. Wires PVR IPTV Simple Client at the 11,842-channel B@Dtv playlist.
7. Copies the B@Dtv color override into the skin.
8. Walks you through Real-Debrid + Trakt device-code OAuth (skippable).
9. Stream-tests one channel via `mpv` so you know whether your network
   actually lets IPTV through *before* you start clicking around Kodi.
10. Launches Kodi in `--standalone -fs` kiosk mode.

After setup, the **in-Kodi wizard** (Programs → B@Dtv Wizard) drops to
maintenance mode -- refresh scraper catalog, check anonymizer status,
add NAS sources, re-apply the theme, run a library scan. None of the
fragile install steps live there.

Status: `./badtv status`.  Re-run one step: `./badtv repair <step>`.
Just launch Kodi: `./badtv launch`.

Long-form: [`docs/INSTALL.md`](docs/INSTALL.md).

## Theme

**The Black Donnellys** in palette form: soot black, whiskey amber, deep
emerald, brick red, parchment. Tokens documented in
[`assets/colors/tokens.md`](assets/colors/tokens.md). The skin overrides ship
as `<colors>` XML drop-ins so they survive upstream skin updates and never
touch layouts. Apply via wizard or copy by hand — see
[`assets/skin/README.md`](assets/skin/README.md).

## Streaming coverage

| Tier                       | What's included                                                                    |
| -------------------------- | ---------------------------------------------------------------------------------- |
| Free / legal linear        | Pluto TV, Plex Live, Samsung TV+, Stirr, PBS, ABC News Live, NBC News Now          |
| Free / legal VOD addons    | Tubi, Pluto TV, Peacock free tier, IMDb TV, YouTube *(Crackle removed 2026-05-24)* |
| Premium scrapers (opt-in)  | Umbrella, Seren, POV, Jacktook *(The Crew/FEN/Scrubs/Exodus retired — zombie repos)* |
| Unrestriction              | Real-Debrid (~$4/mo) **+ TorBox (~$3/mo)** in parallel — TorBox is the May 2026 RD-filter refuge |
| Usenet path *(v3)*         | SABnzbd + NZBGeek (or any Newznab) wired into Sonarr/Radarr — the stable backend   |
| Cloudflare bypass *(v3)*   | Byparr (Camoufox-based, FlareSolverr-API compatible)                               |
| Watch state                | Trakt across every supported addon                                                 |
| Subtitles                  | A4K Subtitles                                                                      |
| International / news / sports | iptv-org per-country + per-category lists, toggleable in `iptv/sources.yaml`    |
| Personal media             | NFS or SMB from your NAS via `media-server/`                                       |

Source list: [`docs/ADDON-LIST.md`](docs/ADDON-LIST.md) and
[`addons/iptv-sources-full.md`](addons/iptv-sources-full.md).

## Repo layout

```text
badtv/
├── README.md
├── CHANGELOG.md
├── LICENSE                   # GPL-3.0
├── Makefile                  # repo / assets / iptv / install / clean
├── install.sh                # Linux + macOS installer
├── install.ps1               # Windows installer (PowerShell)
├── config/
│   ├── badtv.conf.example    # single source of truth
│   └── load.sh               # config layering helper
├── build/
│   ├── repository/           # repository.badtv addon
│   └── wizard/               # script.badtv.wizard (real wizard)
├── assets/
│   ├── branding/             # SVG source for icon/fanart/splash/logo
│   ├── colors/tokens.md      # Black Donnellys palette
│   └── skin/                 # drop-in color overrides
├── iptv/
│   ├── sources.yaml          # declarative IPTV/EPG sources
│   ├── build-playlist.py     # merger / deduper
│   └── dist/                 # built playlist + EPG (gitignored)
├── docs/                     # install, setup, addon list, theme
├── media-server/             # NFS + Samba scripts for the NAS
├── tools/                    # asset renderer, repo packager, audits
└── dist/                     # built repository + wizard zips (gitignored)
```

## Mascot

Same chaos kangaroo from the TerraKodi days, but now wearing a battered
flat cap and standing behind the bar at McKenna's: black sunglasses, pouch
full of VHS, a portable CRT TV on one shoulder, a Blu-ray balanced on top,
General Lee parked in the alley outside, and a half-finished pint of stout
on the back counter.

## Notes

- B@Dtv documents and ships only **lawful free/ad-supported** IPTV sources
  and pointers to user-supplied playlists. Premium TV Everywhere streams
  need your own credentials.
- Third-party Kodi repositories move. The third-party addon list
  ([`addons/recommended.md`](addons/recommended.md)) lists current install
  URLs but expect to swap them when one of the upstream maintainers
  vanishes.
- Real-Debrid and Trakt are optional but transformative. The wizard prompts
  for both.
- Built for **TheClawFirm**, powered by **floor2**, themed by **Hell's Kitchen
  at 2 AM**.

## Self-maintaining scraper catalog

Third-party Kodi scraper repos move and die constantly. B@Dtv ships an
auto-update system so users don't have to chase the churn:

- [`addons/scraper-catalog.json`](addons/scraper-catalog.json) is the
  machine-readable source of truth.
- [`tools/refresh-scrapers.py`](tools/refresh-scrapers.py) probes every
  repo URL on file and refreshes status / version / timestamps.
- [`.github/workflows/refresh-scrapers.yml`](.github/workflows/refresh-scrapers.yml)
  runs that probe daily and commits the result.
- The wizard fetches the live catalog from GitHub on each open (24h
  cache; offline-safe fallback to the copy bundled in the zip), and the
  "Install a third-party scraper from the catalog" menu action installs
  whichever repo is currently `ok`.

Full design + maintenance flow: [`docs/SCRAPERS.md`](docs/SCRAPERS.md).

## Start here

- [`DISCLAIMER.md`](DISCLAIMER.md) — read first
- [`NOTICE.md`](NOTICE.md) — third-party trademarks
- [`docs/PRIVACY.md`](docs/PRIVACY.md) — VPN / DNS / anonymizer guide
- [`docs/INSTALL.md`](docs/INSTALL.md)
- [`docs/SETUP-GUIDE.md`](docs/SETUP-GUIDE.md)
- [`docs/ADDON-LIST.md`](docs/ADDON-LIST.md)
- [`docs/SCRAPERS.md`](docs/SCRAPERS.md)
- [`docs/THEME.md`](docs/THEME.md)
- [`addons/iptv-sources-full.md`](addons/iptv-sources-full.md)
- [`media-server/README.md`](media-server/README.md)
- [`tools/network/README.md`](tools/network/README.md) — privacy helpers
