"""Read and merge entries into Kodi's userdata/sources.xml."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Source:
    section: str  # "video" | "music" | "pictures" | "files"
    name: str
    path: str
    allow_sharing: bool = True


_DEFAULT_SECTIONS = ("programs", "video", "music", "pictures", "files", "games")


def _ensure_tree(path: str) -> ET.ElementTree:
    if os.path.isfile(path):
        return ET.parse(path)
    root = ET.Element("sources")
    for section in _DEFAULT_SECTIONS:
        ET.SubElement(root, section)
    return ET.ElementTree(root)


def _entry_exists(section_elem: ET.Element, name: str, path: str) -> bool:
    for src in section_elem.findall("source"):
        src_name = (src.findtext("name") or "").strip()
        src_path = (src.findtext("path") or "").strip()
        if src_name == name and src_path == path:
            return True
    return False


def merge_sources(sources_xml_path: str, sources: List[Source]) -> int:
    """Add ``sources`` to sources.xml (idempotent). Returns number added."""
    tree = _ensure_tree(sources_xml_path)
    root = tree.getroot()
    added = 0

    for src in sources:
        section_elem = root.find(src.section)
        if section_elem is None:
            section_elem = ET.SubElement(root, src.section)

        if _entry_exists(section_elem, src.name, src.path):
            continue

        source_elem = ET.SubElement(section_elem, "source")
        ET.SubElement(source_elem, "name").text = src.name
        path_elem = ET.SubElement(source_elem, "path")
        path_elem.set("pathversion", "1")
        path_elem.text = src.path
        ET.SubElement(source_elem, "allowsharing").text = "true" if src.allow_sharing else "false"
        added += 1

    os.makedirs(os.path.dirname(sources_xml_path), exist_ok=True)
    tree.write(sources_xml_path, encoding="UTF-8", xml_declaration=True)
    return added
