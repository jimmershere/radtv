# `iptv/` — R&Dtv live TV pipeline

Pulls a list of public M3U + XMLTV sources, merges them into a single
deduped playlist with EPG, and writes the result to `iptv/dist/`. The Kodi
wizard points PVR IPTV Simple Client at the resulting URL (or a local file).

## Files

| Path                  | Role                                                                 |
| --------------------- | -------------------------------------------------------------------- |
| `sources.yaml`        | Canonical, declarative source list. Enable/disable per source.       |
| `build-playlist.py`   | Fetch + merge runner. Stdlib + PyYAML.                               |
| `dist/radtv.m3u`      | Built playlist (gitignored).                                         |
| `dist/radtv.xml`      | Built XMLTV EPG (gitignored).                                        |

## Build

```bash
make iptv
# or:
python3 iptv/build-playlist.py
```

Useful flags:

```bash
python3 iptv/build-playlist.py --dry-run                   # parse only
python3 iptv/build-playlist.py --only-category us_free     # one slice
python3 iptv/build-playlist.py --skip-id iptv-org-index    # skip the big one
python3 iptv/build-playlist.py --epg-url https://my.host/radtv.xml
```

## What's included by default

The `enabled: true` sources cover the strongest free/legal US live offering:

- **Pluto TV** — Paramount's ad-supported linear network.
- **Plex Live TV** — Plex's free linear.
- **Samsung TV Plus** — Samsung's free linear.
- **Stirr** — Sinclair's free linear.
- **iptv-org / news** — community-maintained free news streams.
- **iptv-org / sports** — community-maintained free sports.
- **iptv-org / music** — community-maintained music TV.
- **iptv-org / index** — global catch-all (large; turn off if you want lean).

Per-country international lists ship disabled — flip them on in
`sources.yaml` or pass `--only-id`.

## Adding your own source

Append to `sources.yaml`:

```yaml
- id: my-custom-list
  name: My custom playlist
  category: us_free
  enabled: true
  m3u: https://example.com/playlist.m3u
  epg: https://example.com/guide.xml
  group: "Custom"
```

That's it — next `make iptv` picks it up.

## Legal note

R&Dtv ships only **lawful free/ad-supported sources** and the user's own
playlists. Paid IPTV resellers and pirate aggregators stay out of
`sources.yaml`. If you maintain a private playlist for premium TV
Everywhere streams you have authenticated access to, drop it in
`config/radtv.conf` and point PVR IPTV Simple Client at that URL instead.
