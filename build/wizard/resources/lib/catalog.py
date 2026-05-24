"""Load the B@Dtv scraper catalog at runtime.

The wizard ships with a bundled copy of ``addons/scraper-catalog.json`` (so
it always works offline). At runtime it tries to fetch the latest version
from the user-configurable ``BADTV_REPO_RAW_URL`` first; on any failure
(no network, 404, malformed JSON) it falls back to the bundled copy.

The fetched copy is cached in the addon's user-data dir for 24 hours so the
wizard doesn't hammer the repo on every open.
"""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from . import kodiutils as ku


CACHE_TTL_SECONDS = 24 * 60 * 60          # 24h
HTTP_TIMEOUT = 8
USER_AGENT = "B@Dtv-wizard-catalog/2.0"


def _bundled_path() -> str:
    """Path to the catalog bundled inside the addon."""
    # addon root contains addon.xml + default.py + resources/. Catalog ships
    # in resources/data/scraper-catalog.json (copied at build time -- see
    # tools/build-repo.py for staging).
    return os.path.join(ku.addon_path(), "resources", "data", "scraper-catalog.json")


def _cache_path() -> str:
    return os.path.join(ku.userdata_path(), "scraper-catalog.cache.json")


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        ku.log(f"catalog: failed reading {path}: {exc}", "warning")
        return None


def _cache_is_fresh(path: str, ttl_seconds: int = CACHE_TTL_SECONDS) -> bool:
    try:
        return (time.time() - os.path.getmtime(path)) < ttl_seconds
    except OSError:
        return False


def _fetch_remote(url: str) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=ctx) as resp:
            data = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError, ssl.SSLError) as exc:
        ku.log(f"catalog: remote fetch failed ({url}): {exc}", "warning")
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        ku.log(f"catalog: remote returned non-JSON: {exc}", "warning")
        return None


def _validate(catalog: Dict[str, Any]) -> bool:
    if not isinstance(catalog, dict):
        return False
    if catalog.get("schema_version") != 1:
        return False
    return isinstance(catalog.get("scrapers"), list)


def load(*, force_refresh: bool = False) -> Dict[str, Any]:
    """Load the catalog. Hierarchy:

    1. fresh on-disk cache (<24h old) unless ``force_refresh``;
    2. live fetch from ``BADTV_REPO_RAW_URL/addons/scraper-catalog.json``;
    3. previously-cached copy regardless of freshness;
    4. bundled copy that shipped with the wizard.

    Always returns *something* validly shaped, even if every fetch failed.
    """
    cache = _cache_path()

    if not force_refresh and _cache_is_fresh(cache):
        cached = _read_json(cache)
        if cached and _validate(cached):
            return cached

    repo_raw = ku.get_setting(
        "badtv_repo_raw_url",
        "https://raw.githubusercontent.com/jimmershere/badtv/main",
    ).rstrip("/")
    remote_url = f"{repo_raw}/addons/scraper-catalog.json"
    remote = _fetch_remote(remote_url)
    if remote and _validate(remote):
        try:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache, "w", encoding="utf-8") as fh:
                json.dump(remote, fh, indent=2)
        except OSError as exc:
            ku.log(f"catalog: cache write failed: {exc}", "warning")
        return remote

    cached = _read_json(cache)
    if cached and _validate(cached):
        ku.log("catalog: using stale cache (remote unreachable)", "warning")
        return cached

    bundled = _read_json(_bundled_path())
    if bundled and _validate(bundled):
        ku.log("catalog: using bundled fallback", "warning")
        return bundled

    # Last resort: empty catalog
    ku.log("catalog: empty fallback", "error")
    return {"schema_version": 1, "updated": None, "scrapers": []}


def best_repo(scraper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the first repo with status='ok', else first overall, else None."""
    repos = scraper.get("repos") or []
    for repo in repos:
        if repo.get("status") == "ok":
            return repo
    return repos[0] if repos else None


def format_for_dialog(catalog: Dict[str, Any]) -> str:
    """Render the catalog as a Kodi ``[B]...[/B]``-tagged text blob."""
    updated = catalog.get("updated") or "?"
    lines = [f"Catalog updated: {updated}", ""]
    for scraper in catalog.get("scrapers", []):
        repo = best_repo(scraper)
        if repo is None:
            continue
        status = repo.get("status", "unknown")
        marker = {
            "ok": "[COLOR=FF1F6E4F][OK][/COLOR]",
            "down": "[COLOR=FF6B1A1F][DOWN][/COLOR]",
            "moved": "[COLOR=FFD4A24C][MOVED][/COLOR]",
            "unreachable": "[COLOR=FF8A6A2A][NET?][/COLOR]",
        }.get(status, f"[{status.upper()}]")
        version = repo.get("version") or "?"
        lines.append(
            f"{marker} [B]{scraper['name']}[/B]  v{version}\n"
            f"  id:   {scraper['addon_id']}\n"
            f"  repo: {repo['url']}\n"
        )
    return "\n".join(lines).rstrip()
