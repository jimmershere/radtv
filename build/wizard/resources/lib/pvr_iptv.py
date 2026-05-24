"""Configure PVR IPTV Simple Client by writing its settings.xml.

Kodi reads this from ``userdata/addon_data/pvr.iptvsimple/settings.xml`` and
each setting is one ``<setting id="..." default="false">value</setting>``
entry. Writing it directly avoids forcing the user through the addon's
settings UI.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Dict


PVR_ADDON_ID = "pvr.iptvsimple"


def _load_or_init(path: str) -> ET.ElementTree:
    if os.path.isfile(path):
        return ET.parse(path)
    return ET.ElementTree(ET.Element("settings", version="2"))


def write_pvr_settings(
    kodi_userdata: str,
    m3u_url: str,
    epg_url: str,
    extras: Dict[str, str] | None = None,
) -> str:
    """Write/update pvr.iptvsimple settings.xml. Returns the file path."""
    settings_dir = os.path.join(kodi_userdata, "addon_data", PVR_ADDON_ID)
    os.makedirs(settings_dir, exist_ok=True)
    path = os.path.join(settings_dir, "settings.xml")

    desired: Dict[str, str] = {
        "m3uPathType": "1",          # 1 = remote URL, 0 = local path
        "m3uUrl": m3u_url,
        "m3uCache": "true",
        "epgPathType": "1",
        "epgUrl": epg_url,
        "epgCache": "true",
        "startNum": "1",
        "logoPathType": "1",
        "catchupEnabled": "true",
    }
    if extras:
        desired.update(extras)

    tree = _load_or_init(path)
    root = tree.getroot()
    existing = {s.get("id"): s for s in root.findall("setting")}

    for key, value in desired.items():
        elem = existing.get(key)
        if elem is None:
            elem = ET.SubElement(root, "setting", id=key)
        elem.text = value

    tree.write(path, encoding="UTF-8", xml_declaration=True)
    return path
