#!/usr/bin/env python3
"""Set qBittorrent Web UI credentials on floor2 and restart the container.

Run from quasimodo (SSH to floor2 required):

    ./radtv repair qbittorrent
    # or:
    QBITTORRENT_USER=jimmer QBITTORRENT_PASSWORD='your-pass' \\
      python3 tools/floor2-set-qbittorrent.py

Writes a local handover file on floor2 (mode 0600), never commits secrets to git.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from typing import Optional, Tuple

_TOOLS = os.path.dirname(os.path.abspath(__file__))
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
from floor2_common import (
    floor2_host,
    floor2_user,
    on_floor2,
    run_remote,
    ssh_destination,
    ssh_preflight,
    STACK_CANDIDATES,
)

# Set via env when running, or use the generated default below.
QBIT_USER = os.environ.get("QBITTORRENT_USER", "jimmer")
QBIT_PASS = os.environ.get("QBITTORRENT_PASSWORD", "J1mm3r-F2-qBT-9k!")


def log(msg: str) -> None:
    print(msg, flush=True)


def detect_stack() -> str:
    if os.environ.get("FLOOR2_STACK"):
        return os.environ["FLOOR2_STACK"]
    if on_floor2():
        for s in STACK_CANDIDATES:
            if os.path.isfile(f"{s}/docker-compose.yml"):
                return s
    probe = "\n".join(
        f'[[ -f "{s}/docker-compose.yml" ]] && echo "{s}" && exit 0'
        for s in STACK_CANDIDATES
    ) + '\necho ""\n'
    _, out, _ = run_remote(probe)
    for line in out.splitlines():
        if line.strip() in STACK_CANDIDATES:
            return line.strip()
    return STACK_CANDIDATES[0]


def qbittorrent_pbkdf2(password: str, salt: Optional[bytes] = None) -> str:
    """qBittorrent WebUI Password_PBKDF2 format (PBKDF2-SHA512, 100k rounds)."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha512", password.encode("utf-8"), salt, 100_000)
    return f"@ByteArray({base64.b64encode(salt).decode()}:{base64.b64encode(digest).decode()})"


def patch_qbit_conf(conf_text: str, username: str, password: str) -> str:
    pbkdf2 = qbittorrent_pbkdf2(password)
    lines = conf_text.splitlines()
    out: list[str] = []
    saw_prefs = False
    skip_keys = {"WebUI\\Username", "WebUI\\Password_PBKDF2"}
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line else ""
        if key in skip_keys:
            continue
        out.append(line)
        if line.strip() == "[Preferences]":
            saw_prefs = True
    if not saw_prefs:
        if out and out[-1].strip():
            out.append("")
        out.append("[Preferences]")
    out.append(f"WebUI\\Username={username}")
    out.append(f'WebUI\\Password_PBKDF2="{pbkdf2}"')
    if not conf_text.endswith("\n"):
        out.append("")
    return "\n".join(out)


def find_qbit_service(compose: str) -> str:
    m = re.search(r"^\s{2}(qbittorrent|badtv-qbittorrent|radtv-qbittorrent):", compose, re.M)
    return m.group(1) if m else "qbittorrent"


def main() -> int:
    if not on_floor2() and not ssh_preflight():
        log("ERROR: cannot SSH to floor2 from this machine")
        log("  run: ./radtv repair floor2-ssh")
        log("  or:  ssh floor2@192.168.1.206")
        return 1

    host = floor2_host()
    stack = detect_stack()
    conf_host = f"{stack}/qbittorrent/qBittorrent/qBittorrent.conf"
    handover = f"{stack}/qbittorrent/rdtv-qbit-handover.json"

    log(f"floor2 qBittorrent: user={QBIT_USER} port=8091")
    log(f"target: {floor2_user()}@{host}")
    log(f"stack: {stack}")

    if on_floor2():
        os.makedirs(os.path.dirname(conf_host), exist_ok=True)
        existing = ""
        if os.path.isfile(conf_host):
            existing = open(conf_host, encoding="utf-8").read()
        patched = patch_qbit_conf(existing, QBIT_USER, QBIT_PASS)
        with open(conf_host, "w", encoding="utf-8") as fh:
            fh.write(patched)
        compose = open(f"{stack}/docker-compose.yml", encoding="utf-8").read()
        svc = find_qbit_service(compose)
        subprocess.run(["bash", "-c", f"cd {stack} && docker compose restart {svc}"], check=False)
    else:
        py = patch_qbit_conf("", QBIT_USER, QBIT_PASS)
        # ship patch remotely
        b64_user = base64.b64encode(QBIT_USER.encode()).decode()
        b64_pass = base64.b64encode(QBIT_PASS.encode()).decode()
        script = f"""set -euo pipefail
STACK={stack!r}
CONF="$STACK/qbittorrent/qBittorrent/qBittorrent.conf"
HANDOVER="$STACK/qbittorrent/rdtv-qbit-handover.json"
mkdir -p "$(dirname "$CONF")"
python3 - "$CONF" <<'PY'
import base64, hashlib, os, secrets, sys
conf_path = sys.argv[1]
user = base64.b64decode("{b64_user}").decode()
password = base64.b64decode("{b64_pass}").decode()
salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 100_000)
pbkdf2 = f'@ByteArray({{base64.b64encode(salt).decode()}}:{{base64.b64encode(digest).decode()}})'
existing = ""
if os.path.isfile(conf_path):
    with open(conf_path, encoding="utf-8") as f:
        existing = f.read()
lines = existing.splitlines()
out = []
saw = False
skip = {{"WebUI\\\\Username", "WebUI\\\\Password_PBKDF2"}}
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in skip:
        continue
    out.append(line)
    if line.strip() == "[Preferences]":
        saw = True
if not saw:
    if out and out[-1].strip():
        out.append("")
    out.append("[Preferences]")
out.append(f"WebUI\\\\Username={{user}}")
out.append(f'WebUI\\\\Password_PBKDF2="{{pbkdf2}}"')
text = "\\n".join(out)
if not text.endswith("\\n"):
    text += "\\n"
with open(conf_path, "w", encoding="utf-8") as f:
    f.write(text)
print(f"patched {{conf_path}}")
PY
python3 - "$HANDOVER" <<'PY'
import base64, json, os, sys
path = sys.argv[1]
payload = {{
    "url": "http://{host}:8091",
    "username": base64.b64decode("{b64_user}").decode(),
    "password": base64.b64decode("{b64_pass}").decode(),
    "note": "qBittorrent Web UI via Gluetun on floor2",
}}
with open(path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
    f.write("\\n")
os.chmod(path, 0o600)
print(f"handover {{path}} (0600)")
PY
cd "$STACK"
svc="$(grep -E '^  (qbittorrent|badtv-qbittorrent|radtv-qbittorrent):' docker-compose.yml | head -1 | sed 's/:$//' | tr -d ' ')"
echo "restarting $svc"
docker compose restart "$svc"
sleep 3
docker compose ps "$svc" || true
"""
        code, _, err = run_remote(script)
        if code != 0:
            log(f"ERROR: remote setup failed: {err[:400]}")
            return code

    handover_data = {
        "url": f"http://{host}:8091",
        "username": QBIT_USER,
        "password": QBIT_PASS,
        "note": "qBittorrent Web UI via Gluetun on floor2",
    }
    if on_floor2():
        with open(handover, "w", encoding="utf-8") as fh:
            json.dump(handover_data, fh, indent=2)
            fh.write("\n")
        os.chmod(handover, 0o600)

    log("")
    log("qBittorrent Web UI credentials:")
    log(f"  URL:      http://{host}:8091")
    log(f"  Username: {QBIT_USER}")
    log(f"  Password: {QBIT_PASS}")
    log(f"  Handover: {handover} on floor2 (mode 0600)")
    log("")
    log("If login fails, ensure Gluetun is healthy first:")
    log(f"  ssh {ssh_destination()} 'cd {stack} && docker compose ps gluetun qbittorrent'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
