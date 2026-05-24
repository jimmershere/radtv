"""B@Dtv in-Kodi wizard -- maintenance-mode menu.

First-run setup (install Kodi binary addons, VPN, addon downloads, PVR
config, OAuth, skin theme) is done by the HOST-SIDE bootstrap script
(`./badtv setup` in the repo). The in-Kodi wizard is intentionally
narrower now: it surfaces the runtime maintenance actions that make
sense to do from the couch with a remote -- catalog refresh, anonymizer
status check, library scan, theme reapply, NAS sources, third-party
scraper installs from the live catalog.

If you're seeing this menu and B@Dtv isn't set up yet, run on your
laptop:

    ./badtv setup

(the README has the full walk-through). Everything in this menu assumes
the host-side bootstrap has already done the heavy lifting.
"""
from __future__ import annotations

from typing import Callable, List, Tuple

from . import actions, kodiutils as ku


MenuItem = Tuple[str, Callable[[], None]]


def _menu() -> List[MenuItem]:
    # Maintenance-mode only. Setup-time actions live in bootstrap.py.
    return [
        ("Show third-party scrapers (live catalog)",
         actions.show_third_party_addons),
        ("Install a third-party scraper from the catalog",
         actions.install_third_party_scraper),
        ("Refresh scraper catalog from GitHub now",
         actions.refresh_catalog_now),
        ("Check anonymizer status (current public IP)",
         actions.check_anonymizer_status),
        ("Add floor2 NFS media sources to Kodi",
         actions.add_floor2_sources),
        ("Apply B@Dtv theme to current skin",
         actions.apply_badtv_theme),
        ("Run library scan now",
         actions.run_library_scan),
        ("About B@Dtv",
         actions.show_about),
    ]


def run() -> int:
    while True:
        items = _menu()
        labels = [label for label, _ in items] + ["Exit"]
        choice = ku.select("B@Dtv Wizard  -  maintenance mode", labels)
        if choice is None or choice == len(items):
            return 0
        label, fn = items[choice]
        ku.log(f"menu: {label}")
        try:
            fn()
        except Exception as exc:  # pragma: no cover -- runtime safety net
            ku.log(f"action failed: {exc}", "error")
            ku.info("Action failed", f"{label}\n\n{exc}")
