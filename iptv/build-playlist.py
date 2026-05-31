#!/usr/bin/env python3
"""Merge R&Dtv IPTV sources into a single M3U + XMLTV.

Reads iptv/sources.yaml, fetches each enabled M3U and EPG, dedupes channels
by tvg-id (falling back to channel name), and writes:

    iptv/dist/radtv.m3u
    iptv/dist/radtv.xml

Run from the repo root:

    python3 iptv/build-playlist.py
    python3 iptv/build-playlist.py --only-category us_free
    python3 iptv/build-playlist.py --skip-id iptv-org-index

Stdlib + PyYAML only. No third-party HTTP libs -- urllib does the job.
"""
from __future__ import annotations

import argparse
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set
from xml.etree import ElementTree as ET

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "PyYAML missing. Install it: pip install --user pyyaml\n"
        "or: apt install python3-yaml\n"
    )
    sys.exit(2)


ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(ROOT)
DIST_DIR = os.path.join(ROOT, "dist")
SOURCES_YAML = os.path.join(ROOT, "sources.yaml")

HTTP_TIMEOUT = 30
USER_AGENT = "R&Dtv-IPTV-Builder/2.0 (+https://github.com/jimmershere/radtv)"


@dataclass
class Channel:
    name: str
    url: str
    tvg_id: str = ""
    tvg_logo: str = ""
    group: str = ""
    extras: Dict[str, str] = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        return self.tvg_id.strip().lower() or self.name.strip().lower()


# --- HTTP --------------------------------------------------------------------


def _fetch(url: str) -> bytes:
    if url.startswith(("http://", "https://")):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=ctx) as resp:
            return resp.read()
    # local path
    path = url if os.path.isabs(url) else os.path.join(REPO_ROOT, url)
    with open(path, "rb") as fh:
        return fh.read()


# --- M3U parsing -------------------------------------------------------------


_EXTINF_RE = re.compile(r"^#EXTINF:(?P<duration>-?\d+)(?P<attrs>[^,]*),(?P<name>.+)$")
_ATTR_RE = re.compile(r'(?P<key>[a-zA-Z0-9_-]+)="(?P<val>[^"]*)"')


def parse_m3u(blob: bytes, default_group: str = "") -> List[Channel]:
    text = blob.decode("utf-8", errors="replace")
    lines = [ln.rstrip("\r\n") for ln in text.splitlines()]
    channels: List[Channel] = []
    pending: Optional[Channel] = None

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            m = _EXTINF_RE.match(line)
            if not m:
                pending = None
                continue
            name = m.group("name").strip()
            attrs = {am.group("key"): am.group("val") for am in _ATTR_RE.finditer(m.group("attrs") or "")}
            pending = Channel(
                name=name,
                url="",
                tvg_id=attrs.pop("tvg-id", ""),
                tvg_logo=attrs.pop("tvg-logo", ""),
                group=attrs.pop("group-title", default_group),
                extras=attrs,
            )
        elif line.startswith("#"):
            # ignore other directives (#EXTVLCOPT, etc.) for now
            continue
        else:
            if pending is None:
                continue
            pending.url = line
            channels.append(pending)
            pending = None
    return channels


# --- M3U writing -------------------------------------------------------------


def write_m3u(path: str, channels: Iterable[Channel], epg_url: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f'#EXTM3U url-tvg="{epg_url}"\n')
        for ch in channels:
            attrs = []
            if ch.tvg_id:
                attrs.append(f'tvg-id="{ch.tvg_id}"')
            if ch.tvg_logo:
                attrs.append(f'tvg-logo="{ch.tvg_logo}"')
            if ch.group:
                attrs.append(f'group-title="{ch.group}"')
            attr_str = (" " + " ".join(attrs)) if attrs else ""
            fh.write(f"#EXTINF:-1{attr_str},{ch.name}\n")
            fh.write(f"{ch.url}\n")


# --- XMLTV merging -----------------------------------------------------------


def merge_xmltv(blobs: List[bytes], keep_tvg_ids: Set[str]) -> bytes:
    """Merge multiple XMLTV documents, keeping only channels in keep_tvg_ids.

    keep_tvg_ids comparison is case-insensitive. If keep_tvg_ids is empty all
    channels are kept (useful for debug runs).
    """
    out = ET.Element("tv", attrib={"generator-info-name": "R&Dtv-IPTV-Builder"})
    seen_channels: Set[str] = set()

    keep = {k.lower() for k in keep_tvg_ids} if keep_tvg_ids else set()

    for blob in blobs:
        try:
            root = ET.fromstring(blob)
        except ET.ParseError as exc:
            sys.stderr.write(f"  ! skipping malformed EPG: {exc}\n")
            continue

        for ch in root.findall("channel"):
            cid = (ch.get("id") or "").strip()
            if not cid:
                continue
            if keep and cid.lower() not in keep:
                continue
            if cid.lower() in seen_channels:
                continue
            seen_channels.add(cid.lower())
            out.append(ch)

        for prog in root.findall("programme"):
            cid = (prog.get("channel") or "").strip()
            if not cid:
                continue
            if keep and cid.lower() not in keep:
                continue
            out.append(prog)

    ET.indent(out, space="  ")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(out, encoding="utf-8")


# --- main --------------------------------------------------------------------


def load_sources() -> List[dict]:
    with open(SOURCES_YAML, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("sources", []) if data else []


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build R&Dtv merged IPTV playlist.")
    parser.add_argument("--only-id", action="append", default=[],
                        help="Limit to these source ids (repeatable).")
    parser.add_argument("--skip-id", action="append", default=[],
                        help="Skip these source ids (repeatable).")
    parser.add_argument("--only-category", action="append", default=[],
                        help="Limit to these categories (repeatable).")
    parser.add_argument("--epg-url", default="",
                        help="EPG URL to embed in the M3U header. Defaults to the local file path.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse + report counts without writing dist files.")
    args = parser.parse_args(argv)

    sources = load_sources()
    if not sources:
        sys.stderr.write("No sources defined in sources.yaml\n")
        return 1

    only_id = set(args.only_id)
    skip_id = set(args.skip_id)
    only_cat = set(args.only_category)

    all_channels: List[Channel] = []
    epg_blobs: List[bytes] = []
    seen_keys: Set[str] = set()

    for src in sources:
        sid = src.get("id", "?")
        if not src.get("enabled", False) and sid not in only_id:
            continue
        if only_id and sid not in only_id:
            continue
        if sid in skip_id:
            continue
        cat = src.get("category", "")
        if only_cat and cat not in only_cat:
            continue

        name = src.get("name", sid)
        group_prefix = src.get("group", "")

        if src.get("m3u"):
            print(f"[m3u] {sid} <- {src['m3u']}")
            try:
                blob = _fetch(src["m3u"])
            except (urllib.error.URLError, OSError) as exc:
                sys.stderr.write(f"  ! fetch failed: {exc}\n")
                continue
            chans = parse_m3u(blob, default_group=group_prefix or name)
            added = 0
            for ch in chans:
                if group_prefix and not ch.group.startswith(group_prefix):
                    ch.group = f"{group_prefix} / {ch.group}" if ch.group else group_prefix
                if ch.dedup_key in seen_keys:
                    continue
                seen_keys.add(ch.dedup_key)
                all_channels.append(ch)
                added += 1
            print(f"  + {added} unique channels (of {len(chans)} parsed)")

        if src.get("epg"):
            print(f"[epg] {sid} <- {src['epg']}")
            try:
                epg_blobs.append(_fetch(src["epg"]))
            except (urllib.error.URLError, OSError) as exc:
                sys.stderr.write(f"  ! fetch failed: {exc}\n")

    print(f"\nTotal: {len(all_channels)} channels, {len(epg_blobs)} EPG sources")

    if args.dry_run:
        return 0

    os.makedirs(DIST_DIR, exist_ok=True)
    m3u_path = os.path.join(DIST_DIR, "radtv.m3u")
    epg_path = os.path.join(DIST_DIR, "radtv.xml")
    epg_url = args.epg_url or f"file://{epg_path}"

    write_m3u(m3u_path, all_channels, epg_url=epg_url)
    print(f"wrote {m3u_path} ({os.path.getsize(m3u_path)} bytes)")

    keep_ids = {ch.tvg_id for ch in all_channels if ch.tvg_id}
    epg_bytes = merge_xmltv(epg_blobs, keep_ids)
    with open(epg_path, "wb") as fh:
        fh.write(epg_bytes)
    print(f"wrote {epg_path} ({len(epg_bytes)} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
