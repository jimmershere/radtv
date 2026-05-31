# R&Dtv 2026 Test Cheat Sheet

Generated: 2026-05-31 12:52 UTC

Use this as a safe smoke-test guide for the R&Dtv media platform. It intentionally lists credential handover paths but never includes secret values.

## Access points

- Jellyfin: `http://192.168.1.206:8096`
- Jellyfin HTTPS port mapping: `8920` (TLS still needs explicit setup before use)
- Prowlarr: `http://192.168.1.206:9696`
- Sonarr: `http://192.168.1.206:8989`
- Radarr: `http://192.168.1.206:7878`
- rdt-client: `http://192.168.1.206:6500`
- qBittorrent Web UI: `http://192.168.1.206:8091`
- Credential handover file on floor2: `/datapool/preserved/badtv-arr/jellyfin/rdtv-admin.json`

## Credential handover rules

- Do not paste credential contents into chat, shell history, Git, screenshots, or issue trackers.
- Retrieve Jellyfin credentials only over a trusted SSH session or password manager workflow.
- Expected credential file mode: `600 floor2 floor2`.
- If the file is exposed, rotate the Jellyfin admin password and API key immediately.

## Floor2 stack health

Run from a trusted machine with SSH access:

```bash
ssh floor2@192.168.1.206 'cd /datapool/preserved/badtv-arr && docker compose ps'
ssh floor2@192.168.1.206 'cd /datapool/preserved/badtv-arr && docker ps --filter name=badtv-jellyfin --format "{{.Names}} {{.Status}} {{.Ports}}"'
ssh floor2@192.168.1.206 'stat -c "%a %U %G %n" /datapool/preserved/badtv-arr/jellyfin/rdtv-admin.json'
```

Pass criteria:

- Jellyfin is `Up` and `healthy`.
- Credential file reports `600 floor2 floor2`.
- Existing *arr/download services remain running.

## Jellyfin smoke test

1. Open `http://192.168.1.206:8096`.
2. Sign in using the handover credentials from floor2.
3. Confirm libraries exist:
   - Movies
   - Shows
4. Open one known movie or episode detail page.
5. Confirm metadata/art loads.
6. Start playback on LAN.
7. Confirm no write access is needed from Jellyfin: media is mounted read-only as `/media:ro`.

## Jellyfin API/library check

Use this only after loading credentials into local environment variables or a password manager-backed shell. Do not inline secrets.

```bash
# Example placeholders only. Do not commit real values.
export JELLYFIN_URL='http://192.168.1.206:8096'
export JELLYFIN_API_KEY='<from password manager>'
curl -fsS -H "X-Emby-Token: $JELLYFIN_API_KEY" "$JELLYFIN_URL/Library/VirtualFolders"
```

Pass criteria:

- Response includes `Movies` and `Shows`.

## Prowlarr / Byparr check

```bash
ssh floor2@192.168.1.206 'docker ps --format "{{.Names}} {{.Status}}" | grep -E "badtv-(prowlarr|byparr|flaresolverr)" || true'
```

Pass criteria:

- Prowlarr is running.
- Byparr is preferred for the 2026 path.
- If `badtv-flaresolverr` is still present, it is legacy and should be replaced by the Byparr compose path when the bootstrap cleanup runs.

## Sonarr/Radarr sanity

Open the UIs:

- Sonarr: `http://192.168.1.206:8989`
- Radarr: `http://192.168.1.206:7878`

Check:

- Root folders point under `/media/tv` and `/media/movies`.
- Download clients are present.
- Remote path mapping exists for rdt-client where needed.
- Prowlarr sync is enabled.

## Download clients

Check containers:

```bash
ssh floor2@192.168.1.206 'docker ps --format "{{.Names}} {{.Status}}" | grep -E "badtv-(rdtclient|qbittorrent|gluetun|sabnzbd)" || true'
```

Expected:

- `badtv-rdtclient` is healthy/running.
- `badtv-gluetun` is healthy before using qBittorrent.
- `badtv-qbittorrent` is routed through Gluetun.
- `badtv-sabnzbd` is present after Usenet setup.

## IPTV / Kodi checks

Local repo validation:

```bash
make -C '/app/warp/R&Dtv' check
```

Kodi client checks:

- R&Dtv Wizard is installed under Program add-ons.
- PVR IPTV Simple Client is enabled.
- TV guide populates.
- R&Dtv skin color override appears for supported skins.
- Jellyfin for Kodi can point at `http://192.168.1.206:8096`.

## Repo/package checks

```bash
make -C '/app/warp/R&Dtv' repo
make -C '/app/warp/R&Dtv' check
python3 /app/warp/R&Dtv/tools/lint-zips.py
```

Pass criteria:

- XML parse succeeds.
- Wizard imports succeed.
- `script.radtv.wizard-2.0.0.zip` lints clean.
- `repository.radtv-2.0.1.zip` lints clean.

## Troubleshooting quick hits

- Jellyfin not reachable: `ssh floor2@192.168.1.206 'cd /datapool/preserved/badtv-arr && docker compose logs --tail=200 jellyfin'`
- Credential rejected: retrieve the handover file again, verify no stale copied password, then rotate if needed.
- Movies/Shows empty: verify `/datapool/media/movies` and `/datapool/media/tv` contain media and run a Jellyfin library scan.
- qBittorrent cannot reach network: check Gluetun health first.
- IPTV fetch flaky: rerun; remote EPG providers sometimes truncate large responses.

## Done criteria

- Jellyfin opens from LAN.
- Handover admin login works.
- Movies and Shows libraries exist.
- At least one media item can be browsed or played.
- floor2 compose stack is healthy.
- `make -C '/app/warp/R&Dtv' check` exits 0.
