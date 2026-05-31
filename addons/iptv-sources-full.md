# R&Dtv — Full IPTV & Streaming Sources

**Personal home use. Not for redistribution or resale.**

The wizard configures most of this automatically. This file is the
human-readable reference for *what* is being configured and *why*.

---

## Real-Debrid setup (do this FIRST — unlocks everything)

Real-Debrid is a link unrestriction service. ~$4/month. Makes every scraper
work perfectly.

1. Sign up: <https://real-debrid.com>
2. Wizard → **Authorize Real-Debrid** (opens URLResolver settings) →
   Universal Resolvers → Real-Debrid → Authorize My Account.
3. Visit the device-code URL on your phone, enter the code.
4. In each scraper (Umbrella / Seren / Crew / FEN), Settings → Accounts →
   Real-Debrid → Authorize.
5. Every stream the scrapers find now becomes premium quality, no buffering.

---

## Tier 1 — The big scrapers (movies + TV)

### Umbrella
- Best all-in-one. Real-Debrid + Trakt = the only addon you need for movies/TV.
- Repo: `https://a4k-openproject.github.io/a4kScrapers/repo/`
- Install: Add source → Addons → Install from zip.

### Seren
- Premium scraper, Real-Debrid native.
- Repo: `https://nixgates.github.io/packages/`
- Setup: Real-Debrid + Trakt mandatory.

### Exodus Redux
- Classic, always works, no account needed for basic playback.
- Repo: `https://a4k-openproject.github.io/a4kScrapers/repo/`

### The Crew
- Multi-source, reliable fallback. Has sports sections.
- Repo: `https://team-crew.github.io/`

### FEN Light
- Fast, clean, Real-Debrid optimized.
- Repo: `https://tikipeter.github.io/`

---

## Tier 2 — Live TV (IPTV)

PVR IPTV Simple Client is built into Kodi. Add any M3U URL → instant live TV.
The R&Dtv builder pre-merges everything below into a single playlist.

### Default sources (enabled in `iptv/sources.yaml`)

**US — free / legal linear:**
```
https://i.mjh.nz/PlutoTV/us.m3u8           # Pluto TV
https://i.mjh.nz/Plex/us.m3u8              # Plex Live TV
https://i.mjh.nz/SamsungTVPlus/us.m3u8     # Samsung TV Plus
https://i.mjh.nz/Stirr/all.m3u8            # Stirr
```

**Community-maintained (US news / sports / music):**
```
https://iptv-org.github.io/iptv/categories/news.m3u
https://iptv-org.github.io/iptv/categories/sports.m3u
https://iptv-org.github.io/iptv/categories/music.m3u
https://iptv-org.github.io/iptv/index.m3u   # global catch-all
```

### Fox News / CNN / MSNBC specifically
Generally **not** dependable as permanent free M3U links. Best-practice
options:
- Network's free streaming app: `foxnews.com/live`, `cnn.com/live`,
  `msnbc.com/live` — open via Kodi's browser addon or TV-side native.
- TV Everywhere credentials (Sling / YouTube TV / DirecTV Stream).
- Local affiliates often appear in the iptv-org US list.
- The free news category includes CBS News, NBC News Now, ABC News Live,
  Bloomberg, Reuters, Sky News, France 24, DW, PBS NewsHour.

### International — all countries
```
# Global catch-all
https://iptv-org.github.io/iptv/index.m3u

# By country (replace XX):
https://iptv-org.github.io/iptv/countries/XX.m3u

# Common examples:
https://iptv-org.github.io/iptv/countries/gb.m3u    # United Kingdom
https://iptv-org.github.io/iptv/countries/ca.m3u    # Canada
https://iptv-org.github.io/iptv/countries/mx.m3u    # Mexico
https://iptv-org.github.io/iptv/countries/de.m3u    # Germany
https://iptv-org.github.io/iptv/countries/br.m3u    # Brazil
```

`sources.yaml` has slots for each; flip `enabled: true` to include.

### Sports
```
https://iptv-org.github.io/iptv/categories/sports.m3u   # iptv-org sports
```

Better options for serious sports viewing:
- ESPN+ (via WatchESPN-style addons)
- Rising Tides (community)
- TV Everywhere on your existing sports package

---

## Tier 3 — Premium IPTV services (paid, $10-20/month)

For reliable 24/7 news + sports + live TV without hunting free sources:

- **XTREAM Codes**-compatible services. Search "best IPTV service Reddit"
  for current recommendations (this list rotates).
- Add via: Kodi → PVR IPTV Simple Client → M3U URL or Xtream login.
- Gets you: Fox News, CNN, MSNBC, ESPN, NFL RedZone, etc. reliably.

R&Dtv stays out of recommending specific providers — verify the legality in
your region, then point PVR IPTV Simple Client at the service's URL via
`IPTV_M3U_URL_OVERRIDE` in `config/radtv.conf`.

---

## Tier 4 — Free on-demand addons

| Addon          | Content                                |
| -------------- | -------------------------------------- |
| Tubi           | Free movies + TV, legal, ad-supported  |
| Pluto TV       | Free live + VOD                        |
| Crackle        | Free movies                            |
| Peacock (free) | NBC content                            |
| IMDb TV        | Amazon's free service                  |
| Plex           | Your library + free linear / VOD       |

---

## EPG (Electronic Program Guide)

Makes live TV show what's on, like a real cable guide:

```
# Bundled R&Dtv EPG (merged from MJH + epg.pw)
https://raw.githubusercontent.com/jimmershere/radtv/main/iptv/dist/radtv.xml

# Wide US/UK/CA/AU fallback:
https://epg.pw/xmltv.xml

# Per-source:
https://i.mjh.nz/PlutoTV/us.xml
https://i.mjh.nz/Plex/us.xml
```

---

## VPN (recommended)

- Mullvad, ProtonVPN, NordVPN — pick by jurisdiction / payment preference.
- Run at the router level so every device on the network is covered.
- Unlocks geo-restricted streams.
- Kodi has no built-in VPN — run it at the network or OS layer.

---

## Kodi build settings (all-access setup)

```
Settings → System → Add-ons:
  ✅ Unknown sources: ON

Settings → Player:
  ✅ Adjust display refresh rate: On Start/Stop
  ✅ Sync playback to display: ON

Settings → System → Display:
  Resolution: 1080p or native
  Whitelist: all resolutions

Settings → Skin → Colours:
  radtv  (after running the wizard's "Apply R&Dtv theme" action)
```

`install.sh` writes a sensible `advancedsettings.xml` for buffering /
prefetch that helps with high-bitrate streams.
