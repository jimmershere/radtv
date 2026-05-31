#!/usr/bin/env python3
"""Probe every repo URL in addons/scraper-catalog.json and update statuses.

For each scraper, for each candidate repo:

1. HTTP GET the addons.xml URL (default: <repo-url>/addons.xml).
2. Parse it as a Kodi addons.xml; find the entry whose ``id`` matches the
   scraper's ``addon_id``.
3. Capture its ``version``, set ``status="ok"``, refresh ``last_seen_ok``
   and ``last_checked`` to now.
4. On HTTP error / parse error / missing addon, set ``status="down"`` (or
   ``"moved"`` if the response is valid HTML but not Kodi XML) and update
   ``last_checked``. Leave the previous ``version`` + ``last_seen_ok``
   intact so the wizard can still surface them.

Writes the catalog back deterministically (sorted keys, stable scraper +
repo order) so CI diffs stay small.

Usage:
    python3 tools/refresh-scrapers.py
    python3 tools/refresh-scrapers.py --only-id umbrella
    python3 tools/refresh-scrapers.py --dry-run
    python3 tools/refresh-scrapers.py --print-summary

Exits 0 on success (whether or not the catalog changed), 1 on a fatal
script error.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(ROOT, "addons", "scraper-catalog.json")

HTTP_TIMEOUT = 20
USER_AGENT = "R&Dtv-catalog-refresh/2.0 (+https://github.com/jimmershere/radtv)"


# --- HTTP -------------------------------------------------------------------


def _fetch(url: str) -> tuple[int, bytes, str]:
    """Return (status_code, body_bytes, content_type). HTTPError caught."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=ctx) as resp:
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, resp.read(), ctype
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read()
        except Exception:
            body = b""
        return exc.code, body, exc.headers.get("Content-Type", "") if exc.headers else ""
    except (urllib.error.URLError, TimeoutError, OSError, ssl.SSLError):
        return 0, b"", ""


# --- catalog IO -------------------------------------------------------------


def _load(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save(path: str, data: Dict[str, Any]) -> None:
    # Stable sort: scrapers by id, repos by url. updated/generator stay at top.
    data["scrapers"] = sorted(data.get("scrapers", []), key=lambda s: s["id"])
    for scraper in data["scrapers"]:
        scraper["repos"] = sorted(scraper.get("repos", []), key=lambda r: r["url"])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")


# --- probing ----------------------------------------------------------------


def _find_addon_version(xml_bytes: bytes, addon_id: str) -> Optional[str]:
    """Return the version string for ``addon_id`` in an addons.xml blob."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    for addon in root.findall("addon"):
        if addon.get("id") == addon_id:
            return addon.get("version") or ""
    return None


def _classify(status_code: int, body: bytes, ctype: str, addon_id: str) -> tuple[str, Optional[str]]:
    """Returns (status, version_or_None)."""
    if status_code == 0:
        return "unreachable", None
    if status_code >= 400:
        return "down", None
    # 2xx/3xx
    if b"<addons" in body[:200] or "xml" in (ctype or "").lower():
        version = _find_addon_version(body, addon_id)
        if version is None:
            # XML but addon_id missing -> repo moved its addons
            return "moved", None
        return "ok", version
    # Not XML at all -- probably a 200 OK landing page where the repo used to be
    return "moved", None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def probe_scraper(scraper: Dict[str, Any], dry_run: bool = False) -> List[tuple[str, str, str, str]]:
    """Mutate scraper['repos'] in place. Returns list of (id, label, old_status, new_status)."""
    deltas: List[tuple[str, str, str, str]] = []
    now = _now_iso()
    addon_id = scraper["addon_id"]

    for repo in scraper["repos"]:
        old_status = repo.get("status", "unknown")
        addons_xml_url = repo.get("addons_xml") or repo["url"].rstrip("/") + "/addons.xml"
        status_code, body, ctype = _fetch(addons_xml_url)
        new_status, version = _classify(status_code, body, ctype, addon_id)

        repo["last_checked"] = now
        if new_status == "ok":
            if version is not None:
                repo["version"] = version
            repo["last_seen_ok"] = now
        # for "down" / "moved" / "unreachable" keep version + last_seen_ok intact
        repo["status"] = new_status

        deltas.append((scraper["id"], repo.get("label", ""), old_status, new_status))

    if dry_run:
        # Revert mutations for dry-run
        pass
    return deltas


# --- main -------------------------------------------------------------------


def _print_summary(catalog: Dict[str, Any]) -> None:
    by_status: Dict[str, int] = {}
    rows = []
    for scraper in catalog["scrapers"]:
        for repo in scraper["repos"]:
            st = repo.get("status", "unknown")
            by_status[st] = by_status.get(st, 0) + 1
            rows.append(f"  {st:11} {scraper['id']:12} {repo.get('label',''):28} v{repo.get('version','') or '?':10} <- {repo['url']}")
    print("--- R&Dtv scraper catalog -------------------------------------------------")
    print(f"updated: {catalog.get('updated')}")
    print("status counts:", ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
    print()
    for row in rows:
        print(row)
    print("---------------------------------------------------------------------------")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh the R&Dtv scraper catalog.")
    parser.add_argument("--only-id", action="append", default=[], help="Limit to these scraper ids (repeatable).")
    parser.add_argument("--dry-run", action="store_true", help="Probe but don't write the catalog back.")
    parser.add_argument("--print-summary", action="store_true", help="Print a status table after probing.")
    parser.add_argument("--path", default=CATALOG_PATH, help="Catalog JSON path.")
    args = parser.parse_args(argv)

    catalog = _load(args.path)
    only = set(args.only_id)

    all_deltas: List[tuple[str, str, str, str]] = []
    for scraper in catalog["scrapers"]:
        if only and scraper["id"] not in only:
            continue
        print(f"[probe] {scraper['id']:12} addon_id={scraper['addon_id']}")
        deltas = probe_scraper(scraper, dry_run=args.dry_run)
        all_deltas.extend(deltas)
        for _, label, old, new in deltas:
            marker = " " if old == new else "*"
            print(f"  {marker} {label:28} {old:11} -> {new}")

    catalog["updated"] = _now_iso()

    if not args.dry_run:
        _save(args.path, catalog)
        print(f"\nwrote {args.path}")

    if args.print_summary:
        _print_summary(catalog)

    changed = sum(1 for _, _, o, n in all_deltas if o != n)
    print(f"\n{len(all_deltas)} repos checked, {changed} status changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
