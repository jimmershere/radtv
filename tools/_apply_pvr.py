#!/usr/bin/env python3
"""Helper for install.ps1 (mirrors the inline Python block in install.sh)."""
import os
import sys
from xml.etree import ElementTree as ET


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        sys.exit("usage: _apply_pvr.py <settings.xml> <m3u-url> <epg-url>")
    path, m3u, epg = argv[1], argv[2], argv[3]

    if os.path.isfile(path):
        tree = ET.parse(path)
        root = tree.getroot()
    else:
        root = ET.Element("settings", version="2")
        tree = ET.ElementTree(root)

    desired = {
        "m3uPathType": "1",
        "m3uUrl": m3u,
        "m3uCache": "true",
        "epgPathType": "1",
        "epgUrl": epg,
        "epgCache": "true",
        "startNum": "1",
        "logoPathType": "1",
        "catchupEnabled": "true",
    }
    existing = {s.get("id"): s for s in root.findall("setting")}
    for k, v in desired.items():
        elem = existing.get(k) or ET.SubElement(root, "setting", id=k)
        elem.text = v
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tree.write(path, encoding="UTF-8", xml_declaration=True)
    print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
