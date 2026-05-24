"""Top-level wizard menu loop.

Surfaces every action defined in ``actions`` through a single repeated
xbmcgui.Dialog().select() so the wizard feels like a checklist rather than a
one-shot.
"""
from __future__ import annotations

from typing import Callable, List, Tuple

from . import actions, kodiutils as ku


MenuItem = Tuple[str, Callable[[], None]]


def _menu() -> List[MenuItem]:
    return [
        ("Install official addons (IPTV, YouTube, Tubi, Pluto, Plex, A4K Subs, skin)",
         actions.install_official_addons),
        ("Show third-party scrapers (live catalog)",
         actions.show_third_party_addons),
        ("Install a third-party scraper from the catalog",
         actions.install_third_party_scraper),
        ("Refresh scraper catalog from GitHub now",
         actions.refresh_catalog_now),
        ("Check anonymizer status (current public IP)",
         actions.check_anonymizer_status),
        ("Configure PVR IPTV Simple Client (B@Dtv playlist + EPG)",
         actions.configure_pvr),
        ("Authorize Real-Debrid (via URLResolver)",
         actions.authorize_real_debrid),
        ("Authorize Trakt in Umbrella",
         lambda: actions.authorize_trakt_in("plugin.video.umbrella")),
        ("Authorize Trakt in Seren",
         lambda: actions.authorize_trakt_in("plugin.video.seren")),
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
        choice = ku.select("B@Dtv Wizard", labels)
        if choice is None or choice == len(items):
            return 0
        label, fn = items[choice]
        ku.log(f"menu: {label}")
        try:
            fn()
        except Exception as exc:  # pragma: no cover -- runtime safety net
            ku.log(f"action failed: {exc}", "error")
            ku.info("Action failed", f"{label}\n\n{exc}")
