# IPTV Sources for B@Dtv

B@Dtv's IPTV guidance prioritizes **lawful free-to-air, ad-supported, or
user-supplied playlists**. The canonical machine-readable list lives in
[`../iptv/sources.yaml`](../iptv/sources.yaml); the builder in
[`../iptv/build-playlist.py`](../iptv/build-playlist.py) merges them into
`iptv/dist/badtv.{m3u,xml}`. This document is the human-readable rationale
behind the choices and a map for swapping things when sources move.

## Kodi setup path

The wizard does this for you. By hand:

1. Install **PVR IPTV Simple Client**.
2. Add-ons → My add-ons → PVR clients → PVR IPTV Simple Client → Configure.
3. **M3U Playlist URL:**
   `https://raw.githubusercontent.com/jimmershere/badtv/main/iptv/dist/badtv.m3u`
4. **XMLTV EPG URL:**
   `https://raw.githubusercontent.com/jimmershere/badtv/main/iptv/dist/badtv.xml`
5. Save and restart Kodi / toggle the addon.
6. **TV → Guide** to verify channels + EPG.

## Best free playlist directories

### MJH playlists — *the* reliable free US linear set
`https://i.mjh.nz/` aggregates Pluto, Plex Live, Samsung TV+, Stirr, Tubi
(EPGs), and a handful of others into well-maintained M3U + XML pairs.
B@Dtv builds against `i.mjh.nz/{PlutoTV,Plex,SamsungTVPlus,Stirr}/us.m3u8`
plus matching `.xml` EPGs.

### iptv-org
`https://iptv-org.github.io/iptv/` — community-maintained global directory.
Per-country (`countries/<cc>.m3u`) and per-category (`categories/<cat>.m3u`)
lists. B@Dtv enables news / sports / music + the full index by default; per-
country lists ship disabled (flip in `sources.yaml`).

### epg.pw
`https://epg.pw/xmltv.xml` — broad US/UK/CA/AU EPG used as a fallback layer
behind the per-source EPGs.

## US channels and news

B@Dtv treats US news as a layered strategy because direct M3U availability
for the big cable networks rotates constantly.

### Free / always-on (in the default playlist)
- PBS / PBS NewsHour
- Pluto TV news category (CBS News, NBC News Now, ABC News Live, Bloomberg)
- Stirr news
- Samsung TV+ news block

### Fox News / CNN / MSNBC specifically
Generally **not** dependable as permanent free M3U links. Options:
- the network's own free streaming app (`foxnews.com/live` etc.) — open
  through Kodi's browser addon or a TV-side native app
- TV Everywhere credentials with your existing cable/satellite/streaming
  subscription
- a personal paid IPTV service you maintain
- alternative coverage from the free news category (Bloomberg, Reuters,
  Sky News, France 24, DW, PBS NewsHour)

## International sources

`sources.yaml` ships per-country slots for UK, Canada, Mexico, Germany,
Brazil. Enable the ones you want and pass `--only-id iptv-org-gb` (etc.)
to the builder. For other countries, copy one of the existing
`iptv-org-<cc>` blocks and change the URL to
`https://iptv-org.github.io/iptv/countries/<cc>.m3u`.

## Sports

The least stable category. Recommended:

- Official sports apps/addons where possible (ESPN+, MLB, NHL).
- TV Everywhere credentials in the relevant addon.
- iptv-org sports category as a fallback (already enabled).
- A user-supplied M3U slot for lawful sources you maintain (set
  `IPTV_M3U_URL_OVERRIDE` in `config/badtv.conf`).

## Best practice

- One stable daily-driver playlist (the B@Dtv bundle).
- One overflow international playlist (toggle on per-country slots).
- One news-only lightweight playlist if you want news without the noise.
- Keep EPG URLs separate from M3U URLs so guide failures don't break
  channel import.
