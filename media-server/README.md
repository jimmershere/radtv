# `media-server/` — local media backbone

Optional. B@Dtv works fine as a streaming-only build, but if you've got a NAS
with a real movie/TV/music library, the scripts here wire it up cleanly.

The reference deployment is **floor2** — TheClawFirm's 8TB ZFS box at
`192.168.1.206`. Every host/path/pool name is read from
[`../config/badtv.conf.example`](../config/badtv.conf.example), so pointing
B@Dtv at a different NAS is a one-file edit.

## What ships here

| File                  | Role                                                     |
| --------------------- | -------------------------------------------------------- |
| `setup-nfs.sh`        | Create ZFS dataset, install media subdirs, export NFS.   |
| `setup-smb.sh`        | Same, but for Samba.                                     |
| `kodi-library.xml`    | Reference snippet of Kodi sources.xml entries.           |

Both scripts:

- read `FLOOR2_HOST`, `FLOOR2_ZFS_DATASET`, `FLOOR2_MOUNTPOINT`,
  `FLOOR2_SUBDIRS[]`, and `FLOOR2_NFS_CLIENT_SPEC` from the config layer;
- create the dataset only if missing;
- only append exports/shares that don't already exist (idempotent).

## Recommended folder layout

```
$FLOOR2_MOUNTPOINT/
├── Movies/           # "Movie Name (Year)/Movie Name (Year).mkv"
├── TV/               # "Show/Season 01/Show - s01e01.mkv"
├── Music/
└── Photos/
```

## Recommended process

```bash
# on the NAS:
sudo bash media-server/setup-nfs.sh    # or setup-smb.sh

# on each Kodi client, ONCE:
bash install.sh                         # adds the sources to sources.xml
```

That's it — after a Kodi restart you'll find `floor2 Movies`, `floor2 TV`,
etc. under Files in the browser, and you can import any of them into the
library.

## Auditing what you already have

Before pulling 8 TB of mixed-bag video into Kodi, get a quality snapshot:

```bash
bash tools/scan-existing-media.sh /media media-scan-report.tsv
bash tools/quality-check.sh           media-scan-report.tsv
```

The scan tags everything as `watchable`, `consider_upgrade`, or
`reencode_or_replace`. The check rolls those tags up so you can decide what's
worth replacing before scanning the rest into the library.

## Jellyfin frontend

The reference floor2 stack now runs Jellyfin as the owned-library frontend over
the same media tree:

- Jellyfin URL: `http://192.168.1.206:8096`
- Stack root: `/datapool/preserved/badtv-arr`
- Compose override: `/datapool/preserved/badtv-arr/docker-compose.override.yml`
- Credential handover file: `/datapool/preserved/badtv-arr/jellyfin/rdtv-admin.json`

Jellyfin mounts `/datapool/media` as `/media:ro`, so it can index and stream
the library without owning writes. Keep Sonarr/Radarr/download clients as the
writers and Jellyfin as a read-only presentation layer.

See [`../docs/JELLYFIN.md`](../docs/JELLYFIN.md) for operational checks,
credential handover rules, and Kodi sync notes.
