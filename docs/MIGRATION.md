# R&Dtv migration notes
This document records the GitHub and package migration from the old `badtv` home to the new `radtv` home.
## Current GitHub state
- New active repository: `https://github.com/jimmershere/radtv`
- Visibility: public
- Default branch: `main`
- Description: `R&Dtv 2026 streaming and media platform`
- Old repository: `https://github.com/jimmershere/badtv`
- Old repository visibility: private
- Old repository state: archived
- Old repository description: `Sunset: moved to https://github.com/jimmershere/radtv`
## What changed
- Product name: `B@Dtv` → `R&Dtv`
- GitHub repository name: `jimmershere/badtv` → `jimmershere/radtv`
- Host-side command: `./badtv` → `./radtv`
- User config example: `config/badtv.conf.example` → `config/radtv.conf.example`
- Kodi repository addon: `repository.badtv` → `repository.radtv`
- Kodi wizard addon: `script.badtv.wizard` → `script.radtv.wizard`
- IPTV generated files: `iptv/dist/badtv.m3u` and `iptv/dist/badtv.xml` → `iptv/dist/radtv.m3u` and `iptv/dist/radtv.xml`
- Skin color override: `badtv.xml` → `radtv.xml`
## Fresh clone
Use the new repository for all future installs:
```bash
git clone https://github.com/jimmershere/radtv.git
cd radtv
./radtv setup
```
The old `jimmershere/badtv` repository is intentionally no longer public and should not be used as an install source.
## Existing local clones
For a clone that still points at `jimmershere/badtv`, repoint `origin` to the new repository:
```bash
git remote set-url origin https://github.com/jimmershere/radtv.git
git fetch origin
git switch fork/v2-torbox-usenet
git pull --ff-only
```
If the old remote should be retained for audit history, keep it as `badtv`:
```bash
git remote rename origin badtv
git remote add origin https://github.com/jimmershere/radtv.git
git fetch origin
```
## Kodi upgrade notes
The addon IDs changed, so Kodi treats the R&Dtv repository and wizard as new addons instead of in-place updates to the old `badtv` IDs.
Recommended path:
1. Build or download `dist/repository.radtv-2.0.1.zip`.
2. Install it through Kodi: Settings → Add-ons → Install from zip file.
3. Install `R&Dtv Wizard` from `R&Dtv Repository`.
4. Run `./radtv status` or `./radtv setup` on host-side installs.
5. Re-apply the `radtv` skin color override if the old `badtv` color option was selected.
The old `repository.badtv` and `script.badtv.wizard` addons can be removed from Kodi after the new repository and wizard are installed.
## floor2 legacy operational names
The GitHub/product/package migration does not rename the already-provisioned floor2 Docker/ZFS paths by itself.
Known legacy names that may remain valid on floor2:
- `/datapool/preserved/badtv-arr`
- `badtv-jellyfin`
- other existing `badtv-*` compose service/container names
Those names are operational state, not the public product name. Keep them as-is unless doing a planned floor2 maintenance window with backups and service migration steps.
## Documentation source of truth
- Install flow: `docs/INSTALL.md`
- Jellyfin/floor2 operations: `docs/JELLYFIN.md`
- Smoke-test checklist: `docs/RDTV_TEST_CHEATSHEET.md`
- Branding source: `assets/branding/logo.svg`
