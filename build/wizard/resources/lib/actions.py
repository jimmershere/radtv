"""Concrete actions the wizard menu can perform."""
from __future__ import annotations

import os
import shutil
from typing import List

from . import catalog, kodiutils as ku, network
from .pvr_iptv import write_pvr_settings, PVR_ADDON_ID
from .sources_xml import Source, merge_sources


# Curated install list. Order matters -- IPTV client first so live TV works
# before the user finishes the wizard, then scrapers from most-recommended
# down to legacy fallbacks.
RECOMMENDED_ADDONS: List[str] = [
    "pvr.iptvsimple",
    "plugin.video.youtube",
    "service.subtitles.a4ksubtitles",
    "script.module.metadatautils",
    "plugin.video.tubitv",
    "plugin.video.plutotv",
    "plugin.video.crackle",
    "plugin.video.plexus",
    "plugin.video.plex",
    "skin.arctic.zephyr.reloaded",
]


# --- individual actions ------------------------------------------------------


def install_official_addons() -> None:
    ku.log("install_official_addons: starting")
    for addon_id in RECOMMENDED_ADDONS:
        ku.execute(f"InstallAddon({addon_id})")
    ku.notify("Queued install for the official addon stack.")


def show_third_party_addons() -> None:
    """List third-party scrapers using the live catalog.

    The wizard fetches the latest catalog from raw.githubusercontent.com on
    each open (cached 24h) so repo URL changes show up without a wizard
    update. Always falls back to the bundled copy when offline.
    """
    cat = catalog.load()
    if not cat.get("scrapers"):
        ku.info("Third-party scrapers", "Catalog unavailable (no network, no bundled copy).")
        return
    header = (
        "Third-party scraper repos. Add the repo (Files > Add source), then "
        "install the addon from it (Install from zip > the repo's zip > "
        "Install from repository).\n\n"
        "Status legend: OK / MOVED (URL alive but addon gone) / "
        "DOWN (HTTP error) / NET? (network unreachable from this device)."
    )
    body = header + "\n\n" + catalog.format_for_dialog(cat)
    ku.info("Third-party scrapers", body)


def install_third_party_scraper() -> None:
    """Prompt-select a scraper from the catalog, then queue the install.

    Uses Kodi's ``InstallAddon(<addon_id>)`` builtin. The user still has to
    have the repo source added; the wizard prints the repo URL alongside
    the prompt to make that obvious.
    """
    cat = catalog.load()
    scrapers = cat.get("scrapers") or []
    if not scrapers:
        ku.info("Install scraper", "Catalog unavailable.")
        return

    labels: List[str] = []
    for scraper in scrapers:
        repo = catalog.best_repo(scraper) or {}
        status = repo.get("status", "unknown")
        version = repo.get("version") or "?"
        labels.append(f"{scraper['name']} (v{version}, {status})")

    idx = ku.select("Install third-party scraper", labels)
    if idx is None:
        return
    scraper = scrapers[idx]
    repo = catalog.best_repo(scraper)
    if repo is None:
        ku.info(scraper["name"], "No repo URL on file.")
        return

    if repo.get("status") != "ok":
        proceed = ku.confirm(
            scraper["name"],
            f"Last probe marked this repo [B]{repo.get('status')}[/B].\n\n"
            f"Repo: {repo['url']}\n\n"
            "Try installing anyway? (You'll need the source added in Kodi's "
            "Files manager first.)",
        )
        if not proceed:
            return

    ku.execute(f"InstallAddon({scraper['addon_id']})")
    ku.notify(f"Install queued: {scraper['name']}.")
    ku.log(f"InstallAddon({scraper['addon_id']}) from {repo['url']}")


def refresh_catalog_now() -> None:
    """Force a live re-fetch of the catalog (bypassing the 24h cache)."""
    cat = catalog.load(force_refresh=True)
    updated = cat.get("updated") or "?"
    n = len(cat.get("scrapers", []))
    ku.notify(f"Catalog refreshed: {n} scrapers (updated {updated}).")


def check_anonymizer_status() -> None:
    """Show the user their current public IP from three independent services.

    Hits ipinfo.io / ifconfig.io / icanhazip.com -- the same trio the
    tools/network/vpn-status.sh helper uses. No caching, no telemetry; the
    request is initiated only when the user explicitly picks this menu item.
    """
    ku.notify("Checking public IP... (3 services in parallel)")
    results = network.check_public_ip()
    body = network.format_for_dialog(results)
    ku.info("Anonymizer status", body)


def authorize_real_debrid() -> None:
    """Open the URL Resolver settings; from there the user clicks Authorize."""
    ku.info(
        "Real-Debrid authorization",
        "B@Dtv will open URLResolver settings. Pick 'Universal Resolvers' > "
        "'Real-Debrid' > 'Authorize My Account', then follow the device-code "
        "URL on your phone or laptop.",
    )
    ku.execute("Addon.OpenSettings(script.module.resolveurl)")


def authorize_trakt_in(addon_id: str) -> None:
    ku.info(
        "Trakt",
        f"Opening {addon_id} settings. Find 'Trakt' > 'Authorize' and follow "
        "the device-code URL.",
    )
    ku.execute(f"Addon.OpenSettings({addon_id})")


def configure_pvr() -> None:
    repo_raw = ku.get_setting("badtv_repo_raw_url",
                              "https://raw.githubusercontent.com/jimmershere/badtv/main")
    m3u_url = f"{repo_raw}/iptv/dist/badtv.m3u"
    epg_url = f"{repo_raw}/iptv/dist/badtv.xml"

    custom = ku.confirm(
        "B@Dtv IPTV",
        f"Use the bundled B@Dtv playlist?\n\nM3U: {m3u_url}\nEPG: {epg_url}",
    )
    if not custom:
        m3u_url = ku.text_input("M3U URL", m3u_url) or m3u_url
        epg_url = ku.text_input("EPG URL", epg_url) or epg_url

    path = write_pvr_settings(ku.kodi_userdata(), m3u_url=m3u_url, epg_url=epg_url)
    ku.execute(f"EnableAddon({PVR_ADDON_ID})")
    ku.notify("PVR IPTV Simple Client configured.")
    ku.log(f"Wrote PVR settings to {path}")


def add_floor2_sources() -> None:
    host = ku.get_setting("floor2_host", "192.168.1.206")
    subdirs = ["Movies", "TV", "Music", "Photos"]

    sources: List[Source] = []
    for sub in subdirs:
        url = f"nfs://{host}/media/{sub}/"
        section = (
            "music" if sub == "Music"
            else "pictures" if sub == "Photos"
            else "video"
        )
        sources.append(Source(section=section, name=f"floor2 {sub}", path=url))

    sources_path = os.path.join(ku.kodi_userdata(), "sources.xml")
    added = merge_sources(sources_path, sources)
    ku.notify(f"Added {added} floor2 sources to Kodi.")
    ku.log(f"sources.xml updated at {sources_path} (+{added})")


def apply_badtv_theme() -> None:
    """Copy the B@Dtv color XML into the active skin's colors/ dir.

    Only Arctic Zephyr Reloaded and Estuary MOD V2 are wired up; other skins
    fall back to a friendly explanation. The override is a single XML file --
    if the user uninstalls the skin we just stop applying.
    """
    target = ku.get_setting("badtv_skin_target", "arctic-zephyr-reloaded")
    skin_dirs = {
        "arctic-zephyr-reloaded": ("skin.arctic.zephyr.reloaded", "Arctic Zephyr Reloaded"),
        "estuary-mod-v2": ("skin.estuary.modv2", "Estuary MOD V2"),
        "estuary": ("skin.estuary", "Estuary"),
    }
    if target not in skin_dirs:
        ku.info("Skin theme", f"Unknown skin target '{target}'. Edit the addon settings.")
        return

    skin_id, human = skin_dirs[target]
    addons_root = os.path.join(os.path.dirname(ku.kodi_userdata()), "addons")
    skin_root = os.path.join(addons_root, skin_id)
    if not os.path.isdir(skin_root):
        ku.info("Skin theme", f"{human} isn't installed yet. Install it from the addon menu first.")
        return

    src = os.path.join(ku.addon_path(), "resources", "skin", target, "colors", "badtv.xml")
    if not os.path.isfile(src):
        ku.info("Skin theme", f"Missing override file: {src}")
        return

    dst_dir = os.path.join(skin_root, "colors")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "badtv.xml")
    shutil.copy2(src, dst)
    ku.log(f"Copied B@Dtv color override -> {dst}")

    ku.execute(f"Skin.SetString(ColorTheme,badtv)")
    ku.reload_skin()
    ku.notify(f"B@Dtv theme applied to {human}.")


def run_library_scan() -> None:
    ku.execute("UpdateLibrary(video)")
    ku.execute("UpdateLibrary(music)")
    ku.notify("Library scan triggered.")


def show_about() -> None:
    body = (
        "[B]B@Dtv[/B]  -  Hell's Kitchen-grade Kodi.\n\n"
        "This in-Kodi wizard is [B]maintenance mode[/B]. First-run setup "
        "(installing Kodi binary addons, VPN, addons, OAuth, skin theme) "
        "is done by the host-side bootstrap on your laptop:\n\n"
        "    ./badtv setup\n\n"
        "Source: https://github.com/jimmershere/badtv\n\n"
        "[B]Legal & privacy:[/B]\n"
        "  - DISCLAIMER.md (no warranty, user responsibility)\n"
        "  - NOTICE.md (third-party trademarks)\n"
        "  - docs/PRIVACY.md (VPN + DNS guidance)\n\n"
        "[I]B@Dtv is not affiliated with NBCUniversal, the XBMC Foundation, or "
        "any scraper/streaming service. Don't use B@Dtv to infringe copyright.[/I]"
    )
    ku.info("About B@Dtv", body)
