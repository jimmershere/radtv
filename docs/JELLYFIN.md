# R&Dtv Jellyfin deployment
This document records the 2026 Jellyfin deployment for the R&Dtv / legacy floor2 stack on `floor2`.
## Role in the architecture
Jellyfin is the owned-library frontend for the *arr-managed media library. Kodi remains the lean local-TV and scraper frontend, while Jellyfin gives browser, mobile, Roku, Apple TV, Android TV, and DLNA-style access to the same canonical media tree.
The intended shape is:
- `Sonarr` manages TV into `/datapool/media/tv`
- `Radarr` manages movies into `/datapool/media/movies`
- `Prowlarr` manages indexers for the *arr apps
- `SABnzbd`, `rdt-client`, and `qBittorrent` provide download backends
- `Jellyfin` reads the owned media tree read-only through `/media`
- Kodi can sync the same owned library through the Jellyfin-for-Kodi addon
This implements move 4 from `docs/grey-area-streaming-2026.pdf`: keep Umbrella and Jacktook in Kodi, but treat them as supplemental scrapers over an owned library rather than the primary source of truth.
## floor2 deployment
Reference host:
- Host: `floor2`
- LAN address: `192.168.1.206`
- Stack root: `/datapool/preserved/badtv-arr`
- Compose override: `/datapool/preserved/badtv-arr/docker-compose.override.yml`
- Container: `badtv-jellyfin`
- Image: `jellyfin/jellyfin:latest`
- Public LAN URL: `http://192.168.1.206:8096`
- Optional HTTPS port mapping: `8920`
The floor2 compose path and container names still use the pre-rebrand `badtv` operational prefix because they refer to the already-provisioned server. The GitHub product/repository name is now `radtv`.

The override adds Jellyfin without replacing the existing *arr stack. It mounts:
- `./jellyfin/config` → `/config`
- `./jellyfin/cache` → `/cache`
- `/datapool/media` → `/media:ro`
The media mount is intentionally read-only from Jellyfin. Sonarr/Radarr/download clients own writes; Jellyfin owns presentation, indexing, users, and playback.
## Provisioned libraries
The current floor2 Jellyfin server has:
- `Movies` → `/media/movies`
- `Shows` → `/media/tv`
An initial scan was kicked after library creation. Future scans can be started from the Jellyfin admin UI or by using the Jellyfin API key stored in the handover file.
## Credential handover
Credentials are not checked into this repository and should not be pasted into chat, shell history, logs, tickets, or screenshots.
The floor2 credential handover file is:
- `/datapool/preserved/badtv-arr/jellyfin/rdtv-admin.json`
Expected permissions:
- mode `0600`
- owner `floor2`
- group `floor2`
Retrieve it only over an already trusted SSH session to floor2. Do not print the contents in shared terminals or logs. If you need to hand it to another administrator, move it through a password manager or another encrypted channel.
The file contains:
- `url`
- `admin_user`
- `admin_password`
- `api_key`
If the handover file is ever exposed, rotate both the Jellyfin admin password and API key immediately, then replace the file with a fresh `0600` copy.
## Health checks
From a trusted machine with SSH access to floor2:
```
ssh floor2@192.168.1.206 'cd /datapool/preserved/badtv-arr && docker ps --filter name=badtv-jellyfin --format "{{.Names}} {{.Status}} {{.Ports}}"'
ssh floor2@192.168.1.206 'stat -c "%a %U %G %n" /datapool/preserved/badtv-arr/jellyfin/rdtv-admin.json'
```
Expected state:
- `badtv-jellyfin` is `Up` and `healthy`
- `8096/tcp` is mapped to the LAN
- credential file reports `600 floor2 floor2`
## Operations
Start or update Jellyfin:
```
ssh floor2@192.168.1.206 'cd /datapool/preserved/badtv-arr && docker compose up -d jellyfin'
```
Restart Jellyfin:
```
ssh floor2@192.168.1.206 'cd /datapool/preserved/badtv-arr && docker compose restart jellyfin'
```
Inspect logs:
```
ssh floor2@192.168.1.206 'cd /datapool/preserved/badtv-arr && docker compose logs --tail=200 jellyfin'
```
Back up Jellyfin config:
```
ssh floor2@192.168.1.206 'tar -C /datapool/preserved/badtv-arr -czf jellyfin-config-backup.tgz jellyfin/config jellyfin/rdtv-admin.json docker-compose.override.yml'
```
## Kodi integration
The bootstrap contains support for installing and pre-seeding `plugin.video.jellyfin` so Kodi can sync Jellyfin’s owned library into Kodi’s local video database. That path is still intended to be driven by:
```
./radtv repair jellyfin
```
If the plugin schema changes upstream, the fallback is manual pairing in Kodi:
1. Install the Jellyfin Kodi repository.
2. Install `Jellyfin for Kodi`.
3. Point it at `http://192.168.1.206:8096`.
4. Sign in with the admin credentials from the handover file or create a dedicated non-admin Jellyfin user for daily playback.
For day-to-day playback, prefer a non-admin Jellyfin user. Keep the handover admin only for maintenance.
