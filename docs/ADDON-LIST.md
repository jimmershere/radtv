# B@Dtv Addon List

The B@Dtv stack: shortest path to a loaded, modern Kodi install without
collecting half-broken repos along the way.

## Quick reference

| Layer            | Addons                                                            | Status |
| ---------------- | ----------------------------------------------------------------- | ------ |
| Live TV core     | PVR IPTV Simple Client                                            | Auto   |
| Free legal VOD   | YouTube, Tubi, Pluto TV, Crackle, Plex                            | Auto   |
| Subtitles        | A4K Subtitles                                                     | Auto   |
| Skin             | Arctic Zephyr Reloaded                                            | Auto   |
| Watch state      | Trakt (via each scraper)                                          | Manual |
| Unrestriction    | Real-Debrid via URLResolver                                       | Manual |
| Premium scrapers | Umbrella, Seren, The Crew, FEN Light, Scrubs V2, Exodus Redux     | Manual |
| Personal media   | NFS/SMB from floor2 (or any NAS)                                  | Auto   |

**Auto** = installed/configured by the wizard.
**Manual** = wizard tells you where, you do the click-through (mostly because
the addon ships from a third-party repo Kodi can't reach until you add it).

---

## Core all-in-one video addons

### Umbrella
- **Role:** Best all-around movie/TV addon.
- **Repo:** `https://a4k-openproject.github.io/a4kScrapers/repo/`
- **Strengths:** fast scraping, Debrid support, Trakt, flexible providers.
- **Best for:** primary daily-driver playback.

### Seren
- **Role:** Premium-focused, Debrid-first.
- **Repo:** `https://nixgates.github.io/packages/`
- **Strengths:** polished playback, strong cached-source workflows.
- **Best for:** users who want premium-quality links and clean automation.

### The Crew
- **Role:** Multi-source workhorse.
- **Repo:** `https://team-crew.github.io/`
- **Strengths:** movies, TV, sports sections, specialty content.
- **Best for:** broad fallback coverage.

### FEN Light
- **Role:** premium scraper-heavy.
- **Repo:** `https://tikipeter.github.io/`
- **Strengths:** Debrid workflows, speed, customization.
- **Best for:** users comfortable tuning providers and filters.

### Scrubs V2
- **Role:** dependable free-link backup.
- **Repo:** `https://a4k-openproject.github.io/a4kScrapers/repo/`
- **Strengths:** straightforward menus, lightweight.

### Exodus Redux
- **Role:** Classic familiar layout.
- **Repo:** `https://a4k-openproject.github.io/a4kScrapers/repo/`
- **Best for:** users who like the old-school Exodus-style experience.
- **Note:** community support varies; treat as a legacy layer.

---

## Official + platform addons

### YouTube
- Official YouTube playback. Trailers, channels, music, playlists.

### Plex
- Bridge to existing Plex libraries / remote access.

### Tubi
- Free ad-supported VOD. Legal, low-maintenance, big catalog.

### Pluto TV
- Free linear + VOD. Stable, ad-supported, news + sports channels included.

### Crackle
- Free Sony VOD.

### Peacock (free tier)
- NBC content via the Peacock addon when available.

---

## Live TV and infrastructure

### PVR IPTV Simple Client
- Kodi's official IPTV playlist client. **Must-install** for B@Dtv live TV.
- Wizard pre-fills it with the bundled B@Dtv playlist + EPG.

### A4K Subtitles
- Subtitle search across multiple providers.

### Trakt.tv
- Account integration. Authorize inside each scraper.

### URLResolver / ResolveURL
- Kodi's link-unrestriction layer. Where you authorize Real-Debrid.

---

## Skin

### Arctic Zephyr Reloaded
- Highly customizable, dark-friendly skin. B@Dtv ships a `badtv` color
  override that turns it into a Black Donnellys back-bar.
- Alternative skin targets: Estuary MOD V2, stock Estuary. See
  [`../assets/skin/README.md`](../assets/skin/README.md).

---

## Real-Debrid setup

Real-Debrid is the single biggest quality upgrade in this stack.

1. Buy/renew at <https://real-debrid.com> (~$4/mo).
2. Wizard → **Authorize Real-Debrid** (opens URLResolver settings).
3. URLResolver → Universal Resolvers → Real-Debrid → **Authorize My Account**.
4. Visit the device-code URL, enter the code.
5. In Umbrella / Seren / Crew / FEN, Settings → Accounts → Real-Debrid →
   Authorize.
6. Test playback on a popular title and confirm cached sources show first.

---

## Recommended install order

1. PVR IPTV Simple Client *(auto)*
2. YouTube, Tubi, Pluto TV, Plex, Crackle *(auto)*
3. A4K Subtitles *(auto)*
4. Arctic Zephyr Reloaded skin *(auto)*
5. URLResolver → authorize Real-Debrid
6. Add third-party repo for Umbrella → install Umbrella → authorize
   Trakt + Real-Debrid in Umbrella
7. Repeat (6) for Seren / Crew / FEN Light as wanted
8. Wizard → **Apply B@Dtv theme to current skin**
9. Wizard → **Add floor2 NFS media sources** (if applicable)
10. Library → **Update library**

---

## Operational note

Third-party repositories move. B@Dtv handles this with a self-maintaining
catalog: [`../addons/scraper-catalog.json`](../addons/scraper-catalog.json)
is probed daily by [`../tools/refresh-scrapers.py`](../tools/refresh-scrapers.py)
(via [`../.github/workflows/refresh-scrapers.yml`](../.github/workflows/refresh-scrapers.yml)),
and the wizard fetches the latest catalog at runtime so users get current
URLs without shipping a new release.

See [`SCRAPERS.md`](SCRAPERS.md) for the full design + how to add a new
scraper or mirror.
