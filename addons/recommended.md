# Recommended Kodi Addons (R&Dtv stack)

`./radtv setup` installs the **Auto** layer in full — addons + repos + every
dependency. The **Manual** layer is for stuff that needs a user-specific
account / app-key / per-machine credential the bootstrap can't pretend to
have. This file is the human-readable source of truth; the machine-readable
copy is [`scraper-catalog.json`](scraper-catalog.json).

## Auto (bootstrap installs from Kodi-official mirrors)

- **PVR IPTV Simple Client** — live TV engine (apt: `kodi-pvr-iptvsimple`)
- **YouTube** (`plugin.video.youtube`)
- **Pluto TV** (`plugin.video.plutotv`) — free linear + VOD
- **Plex MOD** (`script.plexmod`) — bridge to your Plex
- **Arctic Zephyr MOD** (`skin.arctic.zephyr.mod`) — skin

## Auto (bootstrap installs from third-party repos — **grey area, RD-driven**)

These need their own GitHub-Pages repo addon, which the bootstrap fetches
and extracts directly. No "Files manager → add source → install from zip
→ install from repository" friction. All pre-enabled in `Addons33.db`.

| Addon | Addon ID | Repo zip | Lives at |
| --- | --- | --- | --- |
| **Umbrella** | `plugin.video.umbrella` | [umbrellaplug.github.io](https://umbrellaplug.github.io/) | `repository.umbrella` |
| **The Crew** | `plugin.video.thecrew` | [team-crew.github.io](https://team-crew.github.io/) | `repository.thecrew` |
| **Seren** | `plugin.video.seren` | [nixgates.github.io/packages](https://nixgates.github.io/packages/) | `repository.nixgates` |
| **POV** | `plugin.video.pov` | [kodifitzwell.github.io/repo](https://kodifitzwell.github.io/repo/) | `repository.kodifitzwell` |
| **CocoScrapers** | `script.module.cocoscrapers` | [cocojoe2411.github.io](https://cocojoe2411.github.io/) | `repository.cocoscrapers` |
| **ResolveURL** | `script.module.resolveurl` | direct via [Gujal00/smrzips](https://github.com/Gujal00/smrzips) | (no wrapper repo) |

The wizard's Real-Debrid step writes your RD token into each of these
addons' `settings.xml` in the keys they each expect — no per-addon
re-authorization round.

## Manual (per-user)

- **YouTube API key** (`plugin.video.youtube` → settings → API → fill).
  Required for personal subscriptions; anonymous browsing + watch works
  without one.
- **Plex server / account** — log into Plex MOD with your own credentials.
- **Trakt** — each scraper (Umbrella, Seren, …) ships its own registered
  Trakt OAuth client. Authorize inside the scraper's settings; R&Dtv
  doesn't centralize this because hosting Trakt client credentials for
  every install would burn through the API quota.
- **FEN Light AM** — was the canonical FEN fork, but the
  `fenlightanonymouse.github.io` Pages mirror is 404 as of 2026-05-24.
  Still installable manually from inside [Red Wizard](https://repo.redwizard.xyz/)
  ([`repository.redwizard-1.2.2.zip`](https://repo.redwizard.xyz/repository.redwizard-1.2.2.zip)).
  Not in the auto list because the install path is "install Red Wizard,
  open it, browse to FEN Light AM, install" — a tree the bootstrap can't
  reproduce without baking a custom installer.

## Catalog maintenance

The canonical machine-readable list lives in
[`scraper-catalog.json`](scraper-catalog.json). The in-Kodi wizard fetches
the live catalog from `raw.githubusercontent.com` on each open (24h cache,
offline-safe fallback to the bundled copy). To probe URLs and refresh
status / version timestamps:

```
python3 tools/refresh-scrapers.py
```

The GitHub Actions workflow [`refresh-scrapers`](../.github/workflows/refresh-scrapers.yml)
runs that probe daily and commits the diff back to `main`.

## Retired

These addons / repos went dark in 2025-2026 with no successor — the
catalog lists them in a `retired:` block for posterity but the wizard
won't try to install them:

| Addon | Last known repo | Retired |
| --- | --- | --- |
| Asgard | `kodiversum.github.io` | 2026-05-24 (Pages 404) |
| Venom | `kodiversum.github.io` | 2026-05-24 (Pages 404) |
| Homelander | `kodi-community-repos.github.io` | 2026-05-24 (Pages 404) |
| Exodus Redux | `a4k-openproject.github.io/a4kScrapers/repo/` | 2026-05-24 (Pages 404) |
| Scrubs V2 | `a4k-openproject.github.io/a4kScrapers/repo/` | 2026-05-24 (Pages 404) |
| Crackle | Kodi mirror | upstream marked `<lifecyclestate type="broken">` |

## Curation rule

Fewer reliable addons > a graveyard of half-broken repos. If two scrapers
overlap heavily, ship one and link the other.
