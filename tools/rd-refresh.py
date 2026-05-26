#!/usr/bin/env python3
"""Daily Real-Debrid token rotator.

Post-May-2026 corporate-restructuring, Real-Debrid issues OAuth access
tokens that expire in 24 hours (was ~89 days). Without rotation, rdt-client
goes "Bad token" and Radarr/Sonarr grabs stop landing.

This script:
  1. Reads the OAuth refresh_token + client_id + client_secret from
     script.module.resolveurl/settings.xml (the canonical source the
     B@Dtv bootstrap writes).
  2. Calls RD's /oauth/v2/token endpoint with grant_type=device to mint
     a fresh access_token.
  3. Writes the new access (and rotated refresh) into:
       * ResolveURL settings.xml
       * Umbrella, Seren, POV settings.xml
       * rdt-client (via its REST API on floor2)
       * ~/.config/badtv/state.json
  4. Logs to ~/.config/badtv/rd-refresh.log

Run daily via cron:
    0 5 * * * /app/badtv/tools/rd-refresh.py

Manual run:
    ./tools/rd-refresh.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Tuple

HOME           = os.path.expanduser("~")
KODI_USERDATA  = os.path.join(HOME, ".kodi", "userdata")
STATE_PATH     = os.path.join(HOME, ".config", "badtv", "state.json")
LOG_PATH       = os.path.join(HOME, ".config", "badtv", "rd-refresh.log")
RU_SETTINGS    = os.path.join(KODI_USERDATA, "addon_data",
                              "script.module.resolveurl", "settings.xml")
RD_TOKEN_URL   = "https://api.real-debrid.com/oauth/v2/token"
RD_USER_URL    = "https://api.real-debrid.com/rest/1.0/user"
FLOOR2_HOST    = "192.168.1.206"
FLOOR2_USER    = "floor2"
RDT_USER       = "jimmer"
RDT_PASS       = "B@Dtv2026!"


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"{ts}  {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def read_resolveurl_creds() -> Tuple[str, str, str, str]:
    if not os.path.isfile(RU_SETTINGS):
        raise SystemExit(f"ResolveURL settings not found at {RU_SETTINGS}")
    root = ET.parse(RU_SETTINGS).getroot()
    s = {x.get("id"): (x.text or "") for x in root.findall("setting")}
    return (s.get("RealDebridResolver_token", ""),
            s.get("RealDebridResolver_refresh", ""),
            s.get("RealDebridResolver_client_id", ""),
            s.get("RealDebridResolver_client_secret", ""))


def refresh_rd(client_id: str, client_secret: str, refresh: str) -> Dict[str, str]:
    data = urllib.parse.urlencode({
        "client_id":     client_id,
        "client_secret": client_secret,
        "code":          refresh,
        "grant_type":    "http://oauth.net/grant_type/device/1.0",
    }).encode()
    req = urllib.request.Request(
        RD_TOKEN_URL, data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def fetch_username(access: str) -> str:
    try:
        req = urllib.request.Request(RD_USER_URL,
            headers={"Authorization": f"Bearer {access}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()).get("username", "")
    except Exception:
        return ""


def patch_addon(addon_id: str, desired: Dict[str, str], dry: bool=False) -> None:
    d = os.path.join(KODI_USERDATA, "addon_data", addon_id)
    if not os.path.isdir(d):
        log(f"  - {addon_id}: not installed, skip")
        return
    path = os.path.join(d, "settings.xml")
    if os.path.isfile(path):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            root = ET.Element("settings", version="2")
    else:
        root = ET.Element("settings", version="2")
    existing = {s.get("id"): s for s in root.findall("setting")}
    for k, v in desired.items():
        e = existing.get(k)
        if e is None:
            e = ET.SubElement(root, "setting", id=k)
        e.text = v
    if dry:
        log(f"  - {addon_id}: would patch {list(desired)}")
    else:
        ET.ElementTree(root).write(path, encoding="UTF-8", xml_declaration=True)
        log(f"  - {addon_id}: patched {list(desired)}")


def patch_rdt_client(access: str, dry: bool=False) -> None:
    if dry:
        log("  - rdt-client: would update Provider:ApiKey (skipped, --dry-run)")
        return
    ssh = ["ssh", "-o", "BatchMode=yes",
           f"{FLOOR2_USER}@{FLOOR2_HOST}"]
    jar = "/tmp/rdtcookies-rotate.txt"
    subprocess.run(ssh + [
        f"rm -f {jar}; curl -sS --cookie-jar {jar} -X POST "
        "http://127.0.0.1:6500/Api/Authentication/Login "
        "-H 'Content-Type: application/json' "
        f"-d '{{\"userName\":\"{RDT_USER}\",\"password\":\"{RDT_PASS}\"}}' "
        ">/dev/null"], check=False, timeout=15)
    payload = json.dumps([{"key": "Provider:ApiKey", "value": access}])
    r = subprocess.run(ssh + [
        f"curl -sS --cookie {jar} -X PUT "
        "http://127.0.0.1:6500/Api/Settings "
        "-H 'Content-Type: application/json' "
        f"-d '{payload}'"], capture_output=True, text=True, timeout=15)
    log(f"  - rdt-client: Provider:ApiKey updated ({(r.stdout or '(empty body = ok)')[:60]})")
    # Restart so background worker picks up the new token. Without this,
    # rdt-client keeps using the cached old token until next compose restart.
    subprocess.run(ssh + ["docker restart badtv-rdtclient >/dev/null 2>&1"],
                   check=False, timeout=20)
    log("  - rdt-client: container restarted to reload provider config")


def update_state(access: str, refresh: str, expires_at: str, dry: bool=False) -> None:
    if not os.path.isfile(STATE_PATH):
        log("  - state.json: not present, skip")
        return
    state = json.load(open(STATE_PATH))
    v = state.setdefault("vars", {})
    v["rd_access_token"]      = access
    v["rd_refresh_token"]     = refresh
    v["rd_token_renewed_at"]  = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    v["rd_token_expires_at"]  = expires_at
    if dry:
        log("  - state.json: would update (dry-run)")
        return
    json.dump(state, open(STATE_PATH, "w"), indent=2)
    log(f"  - state.json: updated, expires {expires_at}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Rotate the Real-Debrid OAuth token.")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would happen without writing")
    args = ap.parse_args()

    log("=== rd-refresh start ===")
    access_old, refresh, cid, csec = read_resolveurl_creds()
    if not (refresh and cid and csec):
        log("ERR: missing refresh/client_id/client_secret in ResolveURL settings.xml")
        log("     run `./badtv repair realdebrid` to re-authorize from a keyboard")
        return 1

    log(f"current token: {access_old[:10]}... (verifying)")
    try:
        req = urllib.request.Request(RD_USER_URL,
            headers={"Authorization": f"Bearer {access_old}"})
        urllib.request.urlopen(req, timeout=8).read()
        log("  current token still valid -- nothing to do")
        return 0
    except urllib.error.HTTPError as e:
        if e.code == 401:
            log(f"  current token rejected (HTTP 401) -- rotating")
        else:
            log(f"  unexpected HTTP {e.code} -- rotating anyway")
    except Exception as exc:
        log(f"  could not reach RD ({exc}) -- skipping this run")
        return 0

    try:
        tok = refresh_rd(cid, csec, refresh)
    except urllib.error.HTTPError as e:
        log(f"ERR: RD refresh failed: HTTP {e.code} {e.read().decode()[:200]}")
        log("     the refresh_token is also dead; re-auth via `./badtv repair realdebrid`")
        return 1

    access_new  = tok.get("access_token", "")
    refresh_new = tok.get("refresh_token", refresh)
    expires_in  = int(tok.get("expires_in", 0) or 86400)
    expires_at  = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                time.gmtime(time.time() + expires_in))
    username = fetch_username(access_new)
    log(f"NEW token: {access_new[:10]}...  user={username}  expires_in={expires_in}s "
        f"({expires_in//3600}h)")

    patch_addon("script.module.resolveurl", {
        "RealDebridResolver_enabled":       "true",
        "RealDebridResolver_login":         "true",
        "RealDebridResolver_client_id":     cid,
        "RealDebridResolver_client_secret": csec,
        "RealDebridResolver_token":         access_new,
        "RealDebridResolver_refresh":       refresh_new,
    }, dry=args.dry_run)

    patch_addon("plugin.video.umbrella", {
        "realdebrid.enable":   "true",
        "realdebridtoken":     access_new,
        "realdebridrefresh":   refresh_new,
        "realdebrid.clientid": cid,
        "realdebridsecret":    csec,
        "realdebridusername":  username,
    }, dry=args.dry_run)

    expires_abs = str(int(time.time() + expires_in))
    patch_addon("plugin.video.seren", {
        "realdebrid.enabled": "true",
        "rd.auth":            access_new,
        "rd.refresh":         refresh_new,
        "rd.client_id":       cid,
        "rd.secret":          csec,
        "rd.username":        username,
        "rd.expiry":          expires_abs,
    }, dry=args.dry_run)

    patch_addon("plugin.video.pov", {
        "rd.enabled":   "true",
        "rd.token":     access_new,
        "rd.refresh":   refresh_new,
        "rd.client_id": cid,
        "rd.secret":    csec,
        "rd.username":  username,
        "rd.expires":   expires_abs,
    }, dry=args.dry_run)

    patch_rdt_client(access_new, dry=args.dry_run)
    update_state(access_new, refresh_new, expires_at, dry=args.dry_run)

    log(f"=== rd-refresh done ({'dry-run' if args.dry_run else 'live'}) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
