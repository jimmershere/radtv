# B@Dtv Install

> **Read [`../DISCLAIMER.md`](../DISCLAIMER.md) before installing.** B@Dtv
> is GPL-3.0 packaging software with no warranty. The installer will print
> a summary and prompt for `I AGREE` on first run. To skip the prompt in
> automation, pass `--accept-disclaimer` or set
> `BADTV_ACCEPT_DISCLAIMER=1`.

There are two paths: the **fast path** (one-shot installer does everything) and
the **manual path** (you click through Kodi by hand). Pick one.

## 0. Prereqs

- Kodi 19+ (Matrix / Nexus / Omega) on Windows, macOS, Linux, Android, Fire
  TV, or LibreELEC/CoreELEC.
- Python 3.10+ on the machine where you'll build (for the IPTV merger + zip
  packager). Not needed on the Kodi device itself if you're using the
  prebuilt zips from the [Releases page].
- Kodi → **Settings → System → Add-ons → Unknown sources: ON** (any
  third-party addon needs this).

### Debian / Ubuntu / Mint extras

The `kodi` apt package does **not** pull in the binary helper addons several
parts of B@Dtv (and most modern Kodi streams) depend on. Install them once
or the wizard's "Install official addons" step will fail with errors like
*"The dependency on inputstream.adaptive version 19.0.0 could not be
satisfied"*:

```bash
sudo apt-get install -y \
  kodi-inputstream-adaptive \
  kodi-pvr-iptvsimple \
  kodi-inputstream-rtmp \
  kodi-vfs-libarchive
```

| Package                       | Required for                                            |
| ----------------------------- | ------------------------------------------------------- |
| `kodi-inputstream-adaptive`   | YouTube, Tubi, Pluto TV, Twitch, most modern HLS/DASH.  |
| `kodi-pvr-iptvsimple`         | Live TV (the PVR backend B@Dtv's wizard configures).    |
| `kodi-inputstream-rtmp`       | RTMP-based community streams + a few legacy addons.     |
| `kodi-vfs-libarchive`         | Browse zip/rar archives natively (some scrapers want it).|

LibreELEC / CoreELEC ship all of these in their image; you only need this
apt step on a general-purpose Linux distro with Kodi installed from the
distro package.

[Releases page]: https://github.com/jimmershere/badtv/releases

---

## Fast path (recommended)

```bash
git clone https://github.com/jimmershere/badtv.git
cd badtv

# Optional: edit floor2 host, repo URL, skin target, IPTV toggles
cp config/badtv.conf.example config/badtv.conf

make all                # builds iptv/dist/badtv.{m3u,xml} + dist/*.zip + assets
bash install.sh         # patches the local Kodi userdata in place
```

Then open Kodi:

1. **Settings → Add-ons → Install from zip file** → pick
   `dist/repository.badtv-2.0.0.zip`.
2. **Install from repository → B@Dtv Repository → Program add-ons →
   B@Dtv Wizard → Install.**
3. **Programs → B@Dtv Wizard.** Work through the menu:
   - install official addons (queues PVR IPTV Simple, Tubi, Pluto TV, Plex,
     YouTube, A4K Subtitles, the Arctic Zephyr Reloaded skin);
   - show third-party scrapers (live catalog — Umbrella / Seren / Crew /
     FEN Light / Scrubs V2 / Exodus Redux / Venom / Asgard / Homelander)
     with per-repo `OK` / `DOWN` / `MOVED` status pulled fresh from
     GitHub; see [`SCRAPERS.md`](SCRAPERS.md) for how the catalog
     self-maintains;
   - install a third-party scraper directly from the catalog (queues
     `InstallAddon(<addon_id>)` once the user has added the matching repo
     source);
   - refresh scraper catalog from GitHub on demand;
   - configure PVR IPTV Simple Client (M3U + EPG already pre-filled);
   - authorize Real-Debrid and Trakt;
   - apply B@Dtv theme to your skin;
   - add floor2 NFS sources (no-op if you don't have a NAS);
   - run a library scan.

On Windows use `pwsh ./install.ps1` instead of `bash install.sh`.

`install.sh --dry-run` shows what would change without writing anything.

---

## Manual path

If `install.sh` is off the table (read-only filesystem, locked-down device,
managed kiosk):

1. **Get the repo zip onto the device.** Either build it (`make repo`) or
   download `dist/repository.badtv-2.0.0.zip` from the Releases page.
2. **Kodi → Settings → Add-ons → Install from zip file → repository.badtv-….zip.**
3. **Install from repository → B@Dtv Repository → Program add-ons →
   B@Dtv Wizard.**
4. **Programs → B@Dtv Wizard** does the rest (same menu as above).

The wizard's "Configure PVR IPTV Simple Client" action writes
`userdata/addon_data/pvr.iptvsimple/settings.xml` directly — you don't have
to type the M3U URL by hand. Its "Add floor2 NFS media sources" action
writes `userdata/sources.xml` directly too.

---

## Connect a NAS (optional)

If you've got an 8 TB ZFS box (a literal floor2 or anything similar):

```bash
# on the NAS:
sudo bash media-server/setup-nfs.sh    # or setup-smb.sh

# on the Kodi client:
#   The wizard's "Add floor2 NFS media sources" action wires up sources.xml
#   automatically once $FLOOR2_HOST in config/badtv.conf is correct.
```

Then in Kodi → **Files → Add videos → Browse → NFS → floor2** and import
Movies / TV / Music as the right library type.

See [`../media-server/README.md`](../media-server/README.md) for the full
walkthrough.

---

## Privacy / VPN (optional but recommended)

For practical guidance on VPN providers, the kill-switch concept, and the
B@Dtv helper scripts that bring up WireGuard + DoT for you, see
[`PRIVACY.md`](PRIVACY.md) and [`../tools/network/README.md`](../tools/network/README.md).

The wizard also has a **"Check anonymizer status"** action that pings
three independent public-IP echo services and shows what each sees you
as. Run it once before you start streaming so you know your VPN is doing
what you think it is.

## Final tune-up

The wizard handles most of this, but for completeness:

- **Settings → Skin → Colours → badtv** to lock in the B@Dtv palette.
- **Settings → Player → Adjust display refresh rate → On Start/Stop.**
- **Settings → System → Display → Whitelist** all resolutions your TV
  reports.
- **Settings → Services → UPnP / DLNA** if you want Kodi as a renderer.
- Subtitles: A4K Subtitles is already installed; configure preferred
  language under its settings.
- Live TV: confirm the guide populates by opening **TV → Guide** a few
  minutes after configuring PVR IPTV Simple Client.

## Done

After that B@Dtv is functionally install-and-done; the remaining one-time
steps are personal service logins (Real-Debrid, Trakt, any premium IPTV
service you maintain).
