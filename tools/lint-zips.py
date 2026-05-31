#!/usr/bin/env python3
"""Structural lint of R&Dtv addon zips against Kodi installer requirements.

Catches the things Kodi refuses to install but only reports as a generic
'Failed to install dependency' or 'Failed to install Add-on from zip file':

 - exactly one top-level directory in the zip
 - that directory's name == addon id in addon.xml (Kodi enforces this)
 - addon.xml parseable, with id / name / version / provider-name attributes
 - at least one <extension> element with a known point
 - extension `library` files actually exist in the zip
 - <assets> referenced by xbmc.addon.metadata actually exist
 - <requires>/<import> entries are either kodi-builtin or come with a heads-up

Returns 0 on clean, 1 on any FAIL. Run from repo root:

    python3 tools/lint-zips.py
    python3 tools/lint-zips.py dist/script.radtv.wizard-2.0.0.zip   # specific
"""
from __future__ import annotations

import os
import sys
import zipfile
from xml.etree import ElementTree as ET


KODI_BUILTIN_IMPORTS = {
    "xbmc.python", "xbmc.gui", "xbmc.json", "xbmc.metadata", "xbmc.addon",
    "xbmc.core", "xbmc.pvrclient", "xbmc.player.musicviz",
    "xbmc.python.script", "xbmc.python.pluginsource",
}

KNOWN_EXTENSION_POINTS = {
    "xbmc.python.script", "xbmc.python.pluginsource",
    "xbmc.python.module", "xbmc.python.weather",
    "xbmc.python.library", "xbmc.python.service",
    "xbmc.addon.repository", "xbmc.addon.metadata",
    "xbmc.gui.skin", "xbmc.metadata.scraper.movies",
    "xbmc.metadata.scraper.tvshows", "xbmc.subtitle.module",
}


def lint(zip_path: str) -> int:
    """Return number of FAIL findings for one zip."""
    fails = 0
    print(f"\n=== {os.path.basename(zip_path)} ===")
    if not os.path.isfile(zip_path):
        print(f"  FAIL: zip not found")
        return 1

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

        roots = {n.split("/", 1)[0] for n in names}
        if len(roots) != 1:
            print(f"  FAIL: multiple top-level entries: {sorted(roots)}")
            return 1
        top = roots.pop()
        print(f"  top-level dir: {top}")

        addon_xml_name = f"{top}/addon.xml"
        if addon_xml_name not in names:
            print(f"  FAIL: {addon_xml_name} missing")
            return 1

        try:
            root = ET.fromstring(zf.read(addon_xml_name))
        except ET.ParseError as exc:
            print(f"  FAIL: addon.xml parse error: {exc}")
            return 1

        addon_id       = root.get("id")
        addon_name     = root.get("name")
        addon_version  = root.get("version")
        addon_provider = root.get("provider-name")
        print(f"  id={addon_id}  name={addon_name!r}  version={addon_version}  provider={addon_provider!r}")

        for field, value in (
            ("id", addon_id), ("name", addon_name),
            ("version", addon_version), ("provider-name", addon_provider),
        ):
            if not value:
                print(f"  FAIL: addon.xml missing required attribute: {field}")
                fails += 1

        if addon_id and addon_id != top:
            print(f"  FAIL: top-level dir {top!r} != addon id {addon_id!r}")
            fails += 1

        extensions = root.findall("extension")
        if not extensions:
            print("  FAIL: no <extension> elements")
            fails += 1

        for ext in extensions:
            point = ext.get("point")
            print(f"  extension point: {point}")
            if point not in KNOWN_EXTENSION_POINTS:
                print(f"    WARN: unknown extension point {point!r}")

            library = ext.get("library")
            if library:
                lib_name = f"{top}/{library}"
                if lib_name not in names:
                    print(f"  FAIL: extension library {library!r} missing ({lib_name})")
                    fails += 1
                else:
                    print(f"    library {library} -> ok")

        meta = root.find("extension[@point='xbmc.addon.metadata']")
        if meta is not None:
            assets = meta.find("assets")
            if assets is not None:
                for child in assets:
                    asset_name = f"{top}/{child.text}"
                    if asset_name not in names:
                        print(f"  WARN: declared asset {child.tag}={child.text!r} not in zip")
                    else:
                        size = zf.getinfo(asset_name).file_size
                        print(f"    asset {child.tag}={child.text} -> ok ({size} bytes)")

        for req in root.findall(".//requires/import"):
            imp = req.get("addon")
            if imp in KODI_BUILTIN_IMPORTS:
                print(f"  import {imp} -> kodi-builtin")
            else:
                print(f"  import {imp} -> external (must be installable from a Kodi repo)")

    return fails


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        targets = argv[1:]
    else:
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        targets = [
            os.path.join(repo, "dist/script.radtv.wizard-2.0.0.zip"),
            os.path.join(repo, "dist/repository.radtv-2.0.1.zip"),
        ]
    total = 0
    for t in targets:
        total += lint(t)
    print(f"\n--- {total} structural problem(s) found ---")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
