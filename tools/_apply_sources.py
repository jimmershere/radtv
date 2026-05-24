#!/usr/bin/env python3
"""Helper for install.sh: merge floor2 entries into Kodi sources.xml."""
import os
import sys
import xml.etree.ElementTree as ET


SECTIONS = ("programs", "video", "music", "pictures", "files", "games")
ENTRIES = [
    ("video",    "floor2 Movies", "Movies"),
    ("video",    "floor2 TV",     "TV"),
    ("music",    "floor2 Music",  "Music"),
    ("pictures", "floor2 Photos", "Photos"),
]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.exit("usage: _apply_sources.py <sources.xml> <floor2-host>")
    path, host = argv[1], argv[2]

    if os.path.isfile(path):
        tree = ET.parse(path)
        root = tree.getroot()
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        root = ET.Element("sources")
        for s in SECTIONS:
            ET.SubElement(root, s)
        tree = ET.ElementTree(root)

    added = 0
    for section, name, subdir in ENTRIES:
        section_elem = root.find(section)
        if section_elem is None:
            section_elem = ET.SubElement(root, section)
        url = f"nfs://{host}/media/{subdir}/"
        exists = any(
            (src.findtext("name") or "").strip() == name
            and (src.findtext("path") or "").strip() == url
            for src in section_elem.findall("source")
        )
        if exists:
            continue
        src = ET.SubElement(section_elem, "source")
        ET.SubElement(src, "name").text = name
        p = ET.SubElement(src, "path"); p.set("pathversion", "1"); p.text = url
        ET.SubElement(src, "allowsharing").text = "true"
        added += 1

    tree.write(path, encoding="UTF-8", xml_declaration=True)
    print(f"  sources.xml: +{added} entries (host={host})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
