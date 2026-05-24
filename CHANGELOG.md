# Changelog

## 2.1.0 — Legal posture + privacy + self-updating catalog (2026-05-24)

### Legal
- **`DISCLAIMER.md`** — comprehensive no-warranty / user-responsibility /
  IPTV-legality / no-piracy-promotion / DMCA-contact disclaimer.
- **`NOTICE.md`** — third-party trademark and copyright acknowledgments
  (Kodi/XBMC Foundation, NBCUniversal "The Black Donnellys", Real-Debrid,
  Trakt, Plex, Tubi, Pluto TV, Samsung TV+, Stirr, Crackle, Peacock,
  IMDb TV, YouTube, all third-party scraper authors, fonts, OSS deps).
- `install.sh` first-run prints disclaimer summary and requires the user
  to type `I AGREE` (or pass `--accept-disclaimer` / set
  `BADTV_ACCEPT_DISCLAIMER=1` for automation).
- Wizard's About panel now links DISCLAIMER / NOTICE / PRIVACY and
  reiterates the non-affiliation statement.

### Privacy
- **`docs/PRIVACY.md`** — threat model, recommended VPN providers
  (Mullvad / ProtonVPN / IVPN with rationale), kill-switch concept,
  DNS guidance, why Tor isn't appropriate for streaming, Kodi hygiene tips.
- **`tools/network/`** — three helper scripts:
  - `vpn-status.sh` — hits ipinfo.io / ifconfig.io / icanhazip.com in
    parallel, prints results, agreement check. No install, no sudo.
  - `setup-wireguard.sh` — takes a user-supplied WireGuard `.conf`,
    installs `wireguard-tools` + `nftables`, brings up `badtv-wg`,
    installs an nftables kill-switch that drops non-WG egress, enables
    the systemd unit. Has `--dry-run`, `--down`, `--status`.
  - `setup-dns.sh` — switches `systemd-resolved` to Cloudflare 1.1.1.1
    + Quad9 9.9.9.9 over DoT with DNSSEC. Revertible.
- Wizard menu gains **"Check anonymizer status"** action using the same
  three-service check as `vpn-status.sh`.

### Scraper catalog (recap of 2.0.x)
- `addons/scraper-catalog.json` is the canonical machine-readable list.
- `tools/refresh-scrapers.py` probes each repo URL daily via
  `.github/workflows/refresh-scrapers.yml`; commits diffs back to `main`.
- Wizard's `resources/lib/catalog.py` fetches the live catalog at runtime
  (24h cache) with a bundled offline fallback.

---

## 2.0.0 — "B@Dtv" (2026-05-23)

### Rebrand
- Renamed project from **TerraKodi** to **B@Dtv**. Directory moved to
  `/app/badtv`. Addon IDs migrated:
  - `plugin.video.terrakodi` → `script.badtv.wizard`
  - `repository.terrakodi` → `repository.badtv`
- New Black Donnellys-inspired identity: soot black, whiskey amber, deep
  emerald, brick red, parchment. Tokens in `assets/colors/tokens.md`,
  theme rules in `docs/THEME.md`.
- New SVG branding pack (logo, icon, fanart, splash) in `assets/branding/`,
  plus `tools/render-assets.sh` to rasterize.

### Wizard
- Replaced the textviewer stub with a real script addon (`script.badtv.wizard`)
  organized under `resources/lib/` (`badtv_wizard`, `actions`, `kodiutils`,
  `sources_xml`, `pvr_iptv`).
- Menu-driven actions:
  - Install the curated official addon stack.
  - Surface third-party scraper repos (Umbrella / Seren / Crew / FEN
    Light / Scrubs V2 / Exodus Redux).
  - Authorize Real-Debrid via URLResolver.
  - Authorize Trakt in Umbrella / Seren.
  - Configure PVR IPTV Simple Client end-to-end (M3U + EPG, idempotent
    settings.xml write).
  - Add floor2 NFS sources to `userdata/sources.xml` (idempotent).
  - Apply B@Dtv skin color override to Arctic Zephyr Reloaded / Estuary
    MOD V2 / Estuary.
  - Trigger library scan.
  - About / branding screen.
- Added proper `resources/settings.xml`, `resources/language/...strings.po`
  for localization.
- Wizard fixes the previously-wrong extension point: now a proper
  `xbmc.python.script` with `<provides>executable</provides>`, so it lists
  under **Program add-ons** as intended.

### IPTV pipeline (new)
- `iptv/sources.yaml` — declarative source list (Pluto / Plex Live /
  Samsung TV+ / Stirr / iptv-org news/sports/music/index, per-country
  international slots, epg.pw fallback EPG).
- `iptv/build-playlist.py` — stdlib + PyYAML merger that fetches each
  enabled source, dedupes channels by `tvg-id` / name, and writes
  `iptv/dist/badtv.m3u` + `iptv/dist/badtv.xml`.
- `make iptv` target wraps the above.

### Skin overrides (new)
- Drop-in `<colors>` XML for three skins:
  `arctic-zephyr-reloaded`, `estuary-mod-v2`, `estuary`. Wizard applies
  automatically; manual install in `assets/skin/README.md`.

### Installer (new)
- `install.sh` (Linux/macOS) + `install.ps1` (Windows): detect Kodi
  userdata, drop `sources.xml`, `advancedsettings.xml`,
  `pvr.iptvsimple/settings.xml`, stage the repo zip, copy the active skin's
  B@Dtv color override.
- Idempotent. `--dry-run` flag. Honors `KODI_USERDATA` env var.
- Inline + helper Python (`tools/_apply_sources.py`, `tools/_apply_pvr.py`)
  share the wizard's settings shape.

### Config (new)
- `config/badtv.conf.example` is the single source of truth for floor2
  host, repo URL, IPTV toggles, skin target. `config/badtv.conf` (gitignored)
  overrides.
- `config/load.sh` layers the two and exports `BADTV_*`, `FLOOR2_*`,
  `IPTV_*`, etc. for every shell entry point.
- Removed hardcoded `192.168.1.206`, `datapool`, and `jimmershere/terrakodi`
  references from `media-server/setup-nfs.sh`, `media-server/setup-smb.sh`,
  `media-server/kodi-library.xml`, and the install path.

### Build
- New `Makefile` with `repo`, `assets`, `iptv`, `install`, `clean`, `check`,
  `help` targets.
- `tools/build-repo.py` rewrites the zip-root prefix so the addon zip
  extracts to `script.badtv.wizard/` (Kodi's requirement) regardless of the
  source dir name.
- `make check` parses every addon XML and imports every wizard module.

### Docs
- README, `docs/INSTALL.md`, `docs/SETUP-GUIDE.md`, `docs/ADDON-LIST.md`,
  `addons/recommended.md`, `addons/iptv-sources.md`, and
  `addons/iptv-sources-full.md` all rewritten end-to-end for the B@Dtv
  brand, new wizard, IPTV pipeline, and one-shot installer.
- New `docs/THEME.md` documents the Black Donnellys palette + skin
  rules.

### Housekeeping
- Deleted prebuilt TerraKodi zips from `dist/` (regenerated via `make repo`).
- Extended `.gitignore` for `iptv/dist/*.m3u`, `iptv/dist/*.xml`,
  `config/badtv.conf`, `assets/branding/*.png`, `assets/branding/*.jpg`.

---

## 1.0.0 — "TerraKodi" (2025)

Initial TerraKodi scaffold: stub wizard, repository addon, addon list
docs, floor2 NFS/SMB setup scripts, media audit tools.
