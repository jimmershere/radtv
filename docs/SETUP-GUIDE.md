# B@Dtv Setup Guide

The wizard automates most of the setup; this is the human-readable version
of what it's doing so you can override or skip selectively.

## What the wizard installs (official)

1. **PVR IPTV Simple Client** — live TV engine. Required for the B@Dtv
   playlist.
2. **YouTube** — official YouTube playback.
3. **A4K Subtitles** — subtitle search.
4. **Tubi** — free, legal, ad-supported VOD.
5. **Pluto TV** — free, legal, ad-supported linear + VOD.
6. **Crackle** — free, legal VOD.
7. **Plex** — bridge to an existing Plex library if you have one.
8. **Arctic Zephyr Reloaded** (skin).
9. **metadatautils** — shared helper module for several addons.

## What the wizard surfaces but doesn't auto-install (third-party)

These come from third-party repos that the user has to add manually (Kodi's
**Install from zip file** → repo zip → Install from repository):

| Addon         | Repo                                                                  | Why                                       |
| ------------- | --------------------------------------------------------------------- | ----------------------------------------- |
| Umbrella      | `https://a4k-openproject.github.io/a4kScrapers/repo/`                 | Best all-around movie/TV scraper.         |
| Seren         | `https://nixgates.github.io/packages/`                                | Premium Real-Debrid-first scraper.        |
| The Crew      | `https://team-crew.github.io/`                                        | Multi-source workhorse, sports sections.  |
| FEN Light     | `https://tikipeter.github.io/`                                        | Fast, clean, Real-Debrid optimized.       |
| Scrubs V2     | `https://a4k-openproject.github.io/a4kScrapers/repo/`                 | Lightweight free-link backup.             |
| Exodus Redux  | `https://a4k-openproject.github.io/a4kScrapers/repo/`                 | Legacy familiar layout.                   |

Third-party repos move. The wizard's "Show third-party scrapers" menu item
prints the current set; check
[`../addons/recommended.md`](../addons/recommended.md) before assuming any
URL above is still alive.

## Real-Debrid

~$4/month. Unlocks cached premium-quality links inside every supported
scraper. **The single biggest quality upgrade in this stack.**

1. Sign up at <https://real-debrid.com>.
2. Wizard → **Authorize Real-Debrid**. (Opens URLResolver settings.)
3. URLResolver → Universal Resolvers → Real-Debrid → **Authorize My Account**.
4. Visit the displayed device-code URL on your phone or laptop, enter the
   code, confirm.
5. In each scraper (Umbrella / Seren / Crew / FEN), Settings → Accounts →
   Real-Debrid → Authorize.
6. Sync providers / clear cache on first use.

## Trakt

Free. Synchronizes watched state, watchlist, progress, collections across
every supported addon and every device.

1. Wizard → **Authorize Trakt in Umbrella** (or Seren, or each addon you use).
2. Visit the device-code URL, enter the code.
3. Each addon's Trakt settings → Sync watchlist / collection / progress.

## Live TV

The wizard's "Configure PVR IPTV Simple Client" action does these in one shot:

1. Writes `userdata/addon_data/pvr.iptvsimple/settings.xml` with
   `m3uUrl` + `epgUrl` pointing at the bundled B@Dtv playlist.
2. Enables PVR IPTV Simple Client.
3. Triggers Kodi to load the playlist.

Open **TV → Guide** and the EPG should populate within a minute.

To override: wizard settings → **Live TV (PVR IPTV Simple)** → set custom
M3U or EPG URL.

## Local media (floor2 / any NAS)

1. On the NAS: `sudo bash media-server/setup-nfs.sh`.
2. In Kodi (or via the wizard's "Add floor2 NFS media sources" action),
   `userdata/sources.xml` gets entries like:
   ```
   nfs://<FLOOR2_HOST>/media/Movies/
   nfs://<FLOOR2_HOST>/media/TV/
   nfs://<FLOOR2_HOST>/media/Music/
   nfs://<FLOOR2_HOST>/media/Photos/
   ```
3. **Files → Add videos → Browse → NFS** and import each section as the
   appropriate library type.
4. Library → **Update library** kicks off the scrape.

For best library scraping:

- Movies: `Movie Name (Year)/Movie Name (Year).mkv`
- TV: `Show Name/Season 01/Show Name - s01e01.mkv`

## Theme

Wizard → **Apply B@Dtv theme to current skin**. The wizard copies a colors
XML override into the active skin's `colors/` directory and selects it. To
revert: **Settings → Skin → Colours →** pick the skin's original theme.

Manual install steps in [`../assets/skin/README.md`](../assets/skin/README.md).

## Reliability tips

- Ethernet beats Wi-Fi for big local playback. Always.
- NFS beats SMB on Linux/LibreELEC; SMB beats NFS on Windows clients.
- Curated stack > everything. More addons = more breakage, not more sources.
- Cache + resolver cleanup fixes most playback issues — Umbrella has a
  one-touch "Clear Cache" action.
- When a third-party repo dies, swap the source in
  [`../addons/recommended.md`](../addons/recommended.md) rather than ripping
  the whole stack apart.
