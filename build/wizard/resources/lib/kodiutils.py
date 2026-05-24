"""Thin wrappers around xbmc* APIs.

Centralised so the rest of the wizard reads as plain Python and so the
modules can be imported (and partly tested) outside Kodi -- the
``HAS_KODI`` flag short-circuits to no-ops when xbmc* isn't available.
"""
from __future__ import annotations

import os
from typing import Iterable, Optional

try:
    import xbmc  # type: ignore
    import xbmcaddon  # type: ignore
    import xbmcgui  # type: ignore
    import xbmcvfs  # type: ignore

    HAS_KODI = True
except ImportError:  # pragma: no cover - only true when running under Kodi
    HAS_KODI = False
    xbmc = xbmcaddon = xbmcgui = xbmcvfs = None  # type: ignore


ADDON_ID = "script.badtv.wizard"


def addon():
    if not HAS_KODI:
        raise RuntimeError("Kodi runtime not available")
    return xbmcaddon.Addon(ADDON_ID)


def addon_path() -> str:
    if HAS_KODI:
        return xbmcvfs.translatePath(addon().getAddonInfo("path"))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def userdata_path() -> str:
    if HAS_KODI:
        return xbmcvfs.translatePath(addon().getAddonInfo("profile"))
    return os.path.expanduser("~/.kodi/userdata/addon_data/" + ADDON_ID)


def kodi_userdata() -> str:
    """Top-level Kodi userdata directory, where sources.xml etc. live."""
    if HAS_KODI:
        return xbmcvfs.translatePath("special://userdata/")
    candidates = [
        os.path.expanduser("~/.kodi/userdata"),
        os.path.expanduser("~/Library/Application Support/Kodi/userdata"),
        os.path.expandvars(r"%APPDATA%\Kodi\userdata"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return candidates[0]


def get_setting(key: str, default: str = "") -> str:
    if not HAS_KODI:
        return default
    value = addon().getSetting(key)
    return value if value else default


def set_setting(key: str, value: str) -> None:
    if HAS_KODI:
        addon().setSetting(key, value)


def notify(message: str, heading: str = "B@Dtv", icon: str = "") -> None:
    if HAS_KODI:
        xbmcgui.Dialog().notification(heading, message, icon or "info", 4000)
    else:
        print(f"[{heading}] {message}")


def info(heading: str, body: str) -> None:
    if HAS_KODI:
        xbmcgui.Dialog().ok(heading, body)
    else:
        print(f"\n=== {heading} ===\n{body}\n")


def confirm(heading: str, body: str, yes_label: str = "Yes", no_label: str = "No") -> bool:
    if HAS_KODI:
        return xbmcgui.Dialog().yesno(heading, body, yeslabel=yes_label, nolabel=no_label)
    print(f"\n[CONFIRM] {heading}: {body}")
    return True


def select(heading: str, options: Iterable[str]) -> Optional[int]:
    options = list(options)
    if HAS_KODI:
        result = xbmcgui.Dialog().select(heading, options)
        return None if result < 0 else result
    print(f"\n[SELECT] {heading}")
    for idx, opt in enumerate(options):
        print(f"  {idx}. {opt}")
    return None


def text_input(heading: str, default: str = "") -> Optional[str]:
    if HAS_KODI:
        result = xbmcgui.Dialog().input(heading, default)
        return result if result else None
    print(f"[INPUT] {heading} (default: {default!r})")
    return default


def log(message: str, level: str = "info") -> None:
    prefix = "[B@Dtv]"
    if HAS_KODI:
        level_map = {
            "debug": xbmc.LOGDEBUG,
            "info": xbmc.LOGINFO,
            "warning": xbmc.LOGWARNING,
            "error": xbmc.LOGERROR,
        }
        xbmc.log(f"{prefix} {message}", level=level_map.get(level, xbmc.LOGINFO))
    else:
        print(f"{prefix} [{level}] {message}")


def execute(builtin: str) -> None:
    """Run a Kodi builtin (e.g. ``InstallAddon(plugin.video.youtube)``)."""
    if HAS_KODI:
        xbmc.executebuiltin(builtin)
    else:
        log(f"executebuiltin({builtin})", "debug")


def reload_skin() -> None:
    execute("ReloadSkin()")
