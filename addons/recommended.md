# Recommended Kodi Addons (B@Dtv stack)

The B@Dtv wizard installs the **Auto** layer and tells you where to grab the
**Manual** layer. This file is the source of truth for what's current — keep
it tight and current; dead repo references are the #1 cause of "the wizard
doesn't work."

## Auto (wizard installs from Kodi's official mirrors)

- **PVR IPTV Simple Client** — live TV engine
- **YouTube** — official YouTube
- **Tubi** — free ad-supported VOD
- **Pluto TV** — free linear + VOD
- **Crackle** — free Sony VOD
- **Plex** — bridge to a Plex server
- **A4K Subtitles** — subtitle retrieval
- **Arctic Zephyr Reloaded** — recommended skin
- **metadatautils** — helper module

## Manual (third-party repos)

| Addon         | Addon ID                  | Repo URL                                                  |
| ------------- | ------------------------- | --------------------------------------------------------- |
| Umbrella      | `plugin.video.umbrella`   | `https://a4k-openproject.github.io/a4kScrapers/repo/`     |
| Seren         | `plugin.video.seren`      | `https://nixgates.github.io/packages/`                    |
| The Crew      | `plugin.video.thecrew`    | `https://team-crew.github.io/`                            |
| FEN Light     | `plugin.video.fenlight`   | `https://tikipeter.github.io/`                            |
| Scrubs V2     | `plugin.video.scrubsv2`   | `https://a4k-openproject.github.io/a4kScrapers/repo/`     |
| Exodus Redux  | `plugin.video.exodusredux`| `https://a4k-openproject.github.io/a4kScrapers/repo/`     |

The wizard's **"Show third-party scrapers"** menu prints this table on
demand inside Kodi.

## Auto-updated catalog

The table above is also captured in machine-readable form at
[`scraper-catalog.json`](scraper-catalog.json), which the daily GitHub
Actions workflow keeps fresh by probing each URL. The wizard fetches the
live JSON at runtime so a repo move shows up in users' Kodi installs
without anyone shipping a new wizard release.

Full design: [`../docs/SCRAPERS.md`](../docs/SCRAPERS.md).

## Source-discovery workflow

Because repositories change, the maintenance routine for *adding* a new
scraper (the script can't decide that — judgment call) is:

1. Check addon health and last update date upstream.
2. Confirm the repo zip URL and addon ID still match (some repos rename).
3. Test install on a clean Kodi profile.
4. Append the new entry to [`scraper-catalog.json`](scraper-catalog.json)
   per the schema in [`../docs/SCRAPERS.md`](../docs/SCRAPERS.md).
5. Run `python3 tools/refresh-scrapers.py --only-id <new-id>` to populate
   `status` / `version` before committing.

URL maintenance (the *status* of existing entries) is fully automated by
[`../tools/refresh-scrapers.py`](../tools/refresh-scrapers.py) and the
[`refresh-scrapers`](../.github/workflows/refresh-scrapers.yml) workflow.

## Curation rule

Fewer reliable addons > a graveyard of half-broken repos. If two scrapers
overlap heavily, ship one and link the other.
