#!/usr/bin/env python3
"""Repair Sonarr on floor2 + fix Knaben indexer in Prowlarr.

Run from a machine that can SSH to floor2 (e.g. quasimodo):

    ./radtv repair sonarr
    python3 tools/floor2-repair-sonarr.py

Actions:
  - Pin Sonarr to 4.0.18.2971-ls315
  - Ensure /datapool/media/downloads/tv-sonarr is mounted in Sonarr
  - Add Sonarr remote-path mappings for rdt-client downloads
  - Remove/re-add Knaben in Prowlarr (fixes stale knaben.eu definitions)
  - Restart Sonarr (and Prowlarr after Knaben repair)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

SONARR_IMAGE = "lscr.io/linuxserver/sonarr:4.0.18.2971-ls315"
SONARR_VERSION = "4.0.18.2971"
TV_SONARR_HOST = "/datapool/media/downloads/tv-sonarr"
TV_SONARR_CONTAINER = "/media/downloads/tv-sonarr"

FLOOR2_HOST = os.environ.get("FLOOR2_HOST", "192.168.1.206")
FLOOR2_USER = os.environ.get("FLOOR2_USER", "floor2")
STACK_CANDIDATES = (
    "/datapool/preserved/badtv-arr",
    "/datapool/preserved/radtv-arr",
)


def log(msg: str) -> None:
    print(msg, flush=True)


def run_remote(script: str) -> Tuple[int, str, str]:
    cmd = ["ssh", "-o", "ConnectTimeout=15", f"{FLOOR2_USER}@{FLOOR2_HOST}", "bash", "-s"]
    log(f"  $ ssh {FLOOR2_USER}@{FLOOR2_HOST}")
    cp = subprocess.run(cmd, input=script, text=True, capture_output=True)
    if cp.stdout:
        print(cp.stdout, end="" if cp.stdout.endswith("\n") else "\n")
    if cp.stderr:
        print(cp.stderr, end="" if cp.stderr.endswith("\n") else "\n", file=sys.stderr)
    return cp.returncode, cp.stdout, cp.stderr


def on_floor2() -> bool:
    return os.path.isdir("/datapool/preserved")


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def remote_compose_repair(stack: str) -> int:
    script = f"""set -euo pipefail
STACK={shell_quote(stack)}
COMPOSE="$STACK/docker-compose.yml"
SONARR_IMAGE={shell_quote(SONARR_IMAGE)}
TV_HOST={shell_quote(TV_SONARR_HOST)}
TV_CTR={shell_quote(TV_SONARR_CONTAINER)}

[[ -f "$COMPOSE" ]] || {{ echo "missing $COMPOSE" >&2; exit 1; }}

echo ">> stack: $STACK"
sudo mkdir -p "$TV_HOST"
sudo chown -R floor2:floor2 "$TV_HOST" 2>/dev/null || sudo chown -R 1000:1000 "$TV_HOST"

python3 - "$COMPOSE" "$SONARR_IMAGE" "$TV_HOST" "$TV_CTR" <<'PY'
import re, sys
path, image, tv_host, tv_ctr = sys.argv[1:5]
body = open(path, encoding="utf-8").read()
body = re.sub(
    r"(?m)(^  sonarr:\\n(?:  [^\\n]*\\n)*?    image: ).*$",
    rf"\\1{{image}}",
    body,
    count=1,
)
mount = f"      - {{tv_host}}:{{tv_ctr}}"
if tv_ctr not in body:
    body = re.sub(
        r"(?m)(^  sonarr:\\n(?:  [^\\n]*\\n)*?    volumes:\\n(?:      - [^\\n]+\\n)+)",
        lambda m: m.group(1) + mount + "\\n",
        body,
        count=1,
    )
open(path, "w", encoding="utf-8").write(body)
print("patched compose: Sonarr image + tv-sonarr mount")
PY

cd "$STACK"
echo ">> pulling Sonarr {SONARR_VERSION}"
docker compose pull sonarr
echo ">> recreating Sonarr"
docker compose up -d sonarr
docker compose ps sonarr
"""
    if on_floor2():
        cp = subprocess.run(["bash", "-c", script], text=True)
        return cp.returncode
    code, _, err = run_remote(script)
    if code != 0:
        log(f"ERROR: compose repair failed: {err[:500]}")
    return code


def detect_stack() -> str:
    if os.environ.get("FLOOR2_STACK"):
        return os.environ["FLOOR2_STACK"]
    if on_floor2():
        for stack in STACK_CANDIDATES:
            if os.path.isfile(f"{stack}/docker-compose.yml"):
                return stack
    probe = "\n".join(
        f'[[ -f "{s}/docker-compose.yml" ]] && echo "{s}" && exit 0'
        for s in STACK_CANDIDATES
    ) + '\necho ""\n'
    code, out, _ = run_remote(probe)
    if code == 0:
        for line in out.splitlines():
            if line.strip() in STACK_CANDIDATES:
                return line.strip()
    return STACK_CANDIDATES[0]


def read_xml_key(stack: str, app: str) -> str:
    path = f"{stack}/{app}/config.xml"
    if on_floor2() and os.path.isfile(path):
        body = open(path, encoding="utf-8").read()
    else:
        code, out, _ = run_remote(f"sudo cat {path} 2>/dev/null || true")
        if code != 0:
            return ""
        body = out
    m = re.search(r"<ApiKey>([^<]+)</ApiKey>", body)
    return m.group(1).strip() if m else ""


def read_compose(stack: str) -> str:
    path = f"{stack}/docker-compose.yml"
    if on_floor2():
        return open(path, encoding="utf-8").read()
    _, out, _ = run_remote(f"cat {path}")
    return out


def prowlarr_api(base: str, key: str, method: str, path: str,
                 payload: Optional[Dict[str, Any]] = None) -> Any:
    url = base.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"X-Api-Key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else None


def arr_api(base: str, key: str, method: str, path: str,
            payload: Optional[Dict[str, Any]] = None,
            ignore_dupe: bool = False) -> Any:
    url = base.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"X-Api-Key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        if ignore_dupe and exc.code == 400:
            return None
        raise


def fix_knaben(prowlarr_url: str, apikey: str) -> bool:
    log(">> repairing Knaben indexer in Prowlarr")
    indexers = prowlarr_api(prowlarr_url, apikey, "GET", "/api/v1/indexer") or []
    knaben = next((i for i in indexers if i.get("name") == "Knaben"), None)
    if knaben:
        log(f"   removing stale Knaben (id={knaben['id']})")
        prowlarr_api(prowlarr_url, apikey, "DELETE", f"/api/v1/indexer/{knaben['id']}")

    schemas = prowlarr_api(prowlarr_url, apikey, "GET", "/api/v1/indexer/schema") or []
    schema = next((s for s in schemas if s.get("name") == "Knaben"), None)
    if not schema:
        log("   ERROR: Knaben schema missing — update Prowlarr image to latest")
        return False

    profiles = prowlarr_api(prowlarr_url, apikey, "GET", "/api/v1/appprofile") or []
    profile_id = profiles[0]["id"] if profiles else 1
    payload = {k: v for k, v in schema.items()
               if k not in ("id", "indexerUrls", "legacyUrls", "definitionName")}
    payload.update({"name": "Knaben", "enable": True, "appProfileId": profile_id, "priority": 25})

    created = prowlarr_api(prowlarr_url, apikey, "POST", "/api/v1/indexer", payload)
    if not created or "id" not in created:
        log("   ERROR: failed to re-create Knaben")
        return False
    log(f"   Knaben re-added (id={created['id']})")
    try:
        prowlarr_api(prowlarr_url, apikey, "POST", "/api/v1/indexer/testall")
    except urllib.error.HTTPError:
        pass
    log("   triggered Prowlarr indexer health check")
    return True


def fix_sonarr_paths(sonarr_url: str, sonarr_key: str, rdt_host: str) -> None:
    log(">> ensuring Sonarr remote-path mappings")
    maps = arr_api(sonarr_url, sonarr_key, "GET", "/api/v3/remotepathmapping") or []
    existing_remote = {m.get("remotePath") for m in maps}
    wanted = [
        ("/datapool/media/downloads/", "/media/downloads/"),
        ("/datapool/media/downloads/tv-sonarr/", f"{TV_SONARR_CONTAINER}/"),
    ]
    for remote, local in wanted:
        if remote in existing_remote:
            log(f"   map exists: {remote} -> {local}")
            continue
        res = arr_api(
            sonarr_url, sonarr_key, "POST", "/api/v3/remotepathmapping",
            payload={"host": rdt_host, "remotePath": remote, "localPath": local},
            ignore_dupe=True,
        )
        if res:
            log(f"   added map: {remote} -> {local}")


def restart_service(stack: str, service: str) -> None:
    cmd = f"cd {stack} && docker compose restart {service}"
    if on_floor2():
        subprocess.run(["bash", "-c", cmd], check=False)
    else:
        run_remote(cmd)


def main() -> int:
    log(f"floor2 repair: Sonarr {SONARR_VERSION} + Knaben")
    log(f"target: {FLOOR2_USER}@{FLOOR2_HOST}")

    stack = detect_stack()
    log(f"stack: {stack}")

    if remote_compose_repair(stack) != 0:
        return 1

    time.sleep(6)

    prowlarr_key = read_xml_key(stack, "prowlarr")
    if prowlarr_key:
        if fix_knaben(f"http://{FLOOR2_HOST}:9696", prowlarr_key):
            restart_service(stack, "prowlarr")
    else:
        log("WARN: could not read Prowlarr API key — skip Knaben repair")

    sonarr_key = read_xml_key(stack, "sonarr")
    if sonarr_key:
        compose = read_compose(stack)
        m = re.search(r"container_name:\s*(\S+-rdtclient)", compose)
        rdt_host = m.group(1) if m else "badtv-rdtclient"
        try:
            fix_sonarr_paths(f"http://{FLOOR2_HOST}:8989", sonarr_key, rdt_host)
        except Exception as exc:
            log(f"WARN: Sonarr path mapping: {exc}")

    log("done.")
    log(f"Sonarr:   http://{FLOOR2_HOST}:8989")
    log(f"Prowlarr: http://{FLOOR2_HOST}:9696")
    return 0


if __name__ == "__main__":
    sys.exit(main())
