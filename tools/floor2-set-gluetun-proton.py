#!/usr/bin/env python3
"""Configure Gluetun on floor2 for ProtonVPN + WireGuard.

Run from quasimodo (SSH to floor2):

    ./radtv repair gluetun

Provide your Proton WireGuard private key ONE of these ways:

    # 1. Environment variable (recommended)
    WIREGUARD_PRIVATE_KEY='your-base64-key' ./radtv repair gluetun

    # 2. Proton .conf file downloaded from account.proton.me
    PROTON_WG_CONF=~/Downloads/us-free.conf ./radtv repair gluetun

    # 3. Already in floor2 stack .env — script preserves existing key

Get a key: https://account.proton.me/vpn/WireGuard → generate config → copy PrivateKey
"""
from __future__ import annotations

import base64
import os
import re
import subprocess
import sys
from typing import Dict, Optional, Tuple

FLOOR2_HOST = os.environ.get("FLOOR2_HOST", "192.168.1.206")
FLOOR2_USER = os.environ.get("FLOOR2_USER", "floor2")
STACK_CANDIDATES = (
    "/datapool/preserved/badtv-arr",
    "/datapool/preserved/radtv-arr",
)

PROTON_ENV = {
    "VPN_SERVICE_PROVIDER": "protonvpn",
    "VPN_TYPE": "wireguard",
    "SERVER_COUNTRIES": os.environ.get("SERVER_COUNTRIES", "USA"),
    "VPN_PORT_FORWARDING": os.environ.get("VPN_PORT_FORWARDING", "on"),
    "VPN_PORT_FORWARDING_PROVIDER": "protonvpn",
    "PORT_FORWARD_ONLY": os.environ.get("PORT_FORWARD_ONLY", "on"),
    # Clear OpenVPN leftovers when switching to WireGuard Proton
    "OPENVPN_USER": "",
    "OPENVPN_PASSWORD": "",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def on_floor2() -> bool:
    return os.path.isdir("/datapool/preserved")


def run_remote(script: str) -> Tuple[int, str, str]:
    cmd = ["ssh", "-o", "ConnectTimeout=15", f"{FLOOR2_USER}@{FLOOR2_HOST}", "bash", "-s"]
    cp = subprocess.run(cmd, input=script, text=True, capture_output=True)
    if cp.stdout:
        print(cp.stdout, end="" if cp.stdout.endswith("\n") else "\n")
    if cp.stderr:
        print(cp.stderr, end="" if cp.stderr.endswith("\n") else "\n", file=sys.stderr)
    return cp.returncode, cp.stdout, cp.stderr


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


def parse_wg_conf(path: str) -> Tuple[str, str]:
    key, addr = "", ""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.lower().startswith("privatekey"):
                key = line.split("=", 1)[1].strip()
            elif line.lower().startswith("address"):
                addr = line.split("=", 1)[1].strip()
    return key, addr


def read_env_file(path: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not os.path.isfile(path):
        return out
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def upsert_env_text(text: str, updates: Dict[str, str]) -> str:
    lines = text.splitlines()
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            val = updates[key]
            out.append(f"{key}={val}")
            seen.add(key)
        else:
            out.append(line)
    for key, val in updates.items():
        if key not in seen:
            out.append(f"{key}={val}")
    result = "\n".join(out)
    if not result.endswith("\n"):
        result += "\n"
    return result


def patch_compose_proton(compose: str) -> str:
    compose = re.sub(
        r"VPN_SERVICE_PROVIDER=\$\{\{VPN_SERVICE_PROVIDER:-mullvad\}\}",
        "VPN_SERVICE_PROVIDER=${VPN_SERVICE_PROVIDER:-protonvpn}",
        compose,
    )
    if "VPN_PORT_FORWARDING" not in compose:
        compose = compose.replace(
            "      - FIREWALL_OUTBOUND_SUBNETS=192.168.1.0/24",
            "      - VPN_PORT_FORWARDING=${VPN_PORT_FORWARDING:-on}\n"
            "      - VPN_PORT_FORWARDING_PROVIDER=${VPN_PORT_FORWARDING_PROVIDER:-protonvpn}\n"
            "      - PORT_FORWARD_ONLY=${PORT_FORWARD_ONLY:-on}\n"
            "      - FIREWALL_OUTBOUND_SUBNETS=192.168.1.0/24",
            1,
        )
    return compose


def find_tmp_wg_conf() -> str:
    """Locate a Proton WireGuard config dropped in /tmp on floor2."""
    import glob
    patterns = ("/tmp/*.conf", "/tmp/*proton*", "/tmp/*wg*", "/tmp/*radtv*")
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    if "PrivateKey" in fh.read():
                        return path
            except OSError:
                continue
    return ""


def resolve_wireguard_key(existing_env: Dict[str, str]) -> Tuple[str, str]:
    key = os.environ.get("WIREGUARD_PRIVATE_KEY", "").strip()
    addr = os.environ.get("WIREGUARD_ADDRESSES", "").strip()
    conf = os.environ.get("PROTON_WG_CONF", "").strip()
    if not conf and on_floor2():
        conf = find_tmp_wg_conf()
    if conf:
        if not os.path.isfile(conf):
            log(f"ERROR: PROTON_WG_CONF not found: {conf}")
            sys.exit(1)
        ckey, caddr = parse_wg_conf(conf)
        key = key or ckey
        addr = addr or caddr
    if not key:
        key = existing_env.get("WIREGUARD_PRIVATE_KEY", "").strip()
    if not addr:
        addr = existing_env.get("WIREGUARD_ADDRESSES", "").strip()
    return key, addr


def main() -> int:
    stack = detect_stack()
    env_path = f"{stack}/.env"
    compose_path = f"{stack}/docker-compose.yml"

    log("floor2 Gluetun → ProtonVPN + WireGuard")
    log(f"stack: {stack}")

    if on_floor2():
        existing = read_env_file(env_path)
        wg_key, wg_addr = resolve_wireguard_key(existing)
        updates = dict(PROTON_ENV)
        if wg_key:
            updates["WIREGUARD_PRIVATE_KEY"] = wg_key
        if wg_addr:
            updates["WIREGUARD_ADDRESSES"] = wg_addr
        text = ""
        if os.path.isfile(env_path):
            text = open(env_path, encoding="utf-8").read()
        open(env_path, "w", encoding="utf-8").write(upsert_env_text(text, updates))
        if os.path.isfile(compose_path):
            body = open(compose_path, encoding="utf-8").read()
            open(compose_path, "w", encoding="utf-8").write(patch_compose_proton(body))
        subprocess.run(
            ["bash", "-c", f"cd {stack} && docker compose up -d gluetun qbittorrent"],
            check=False,
        )
        subprocess.run(
            ["bash", "-c", f"cd {stack} && docker compose logs --tail=30 gluetun"],
            check=False,
        )
    else:
        # Ship key/conf to remote without echoing in process list when possible
        local_env = {}
        conf = os.environ.get("PROTON_WG_CONF", "").strip()
        if conf and os.path.isfile(conf):
            k, a = parse_wg_conf(conf)
            if k:
                local_env["WIREGUARD_PRIVATE_KEY"] = k
            if a:
                local_env["WIREGUARD_ADDRESSES"] = a
        if os.environ.get("WIREGUARD_PRIVATE_KEY"):
            local_env["WIREGUARD_PRIVATE_KEY"] = os.environ["WIREGUARD_PRIVATE_KEY"].strip()
        if os.environ.get("WIREGUARD_ADDRESSES"):
            local_env["WIREGUARD_ADDRESSES"] = os.environ["WIREGUARD_ADDRESSES"].strip()

        b64_updates = base64.b64encode(
            "\n".join(f"{k}={v}" for k, v in {**PROTON_ENV, **local_env}.items()).encode()
        ).decode()

        script = f"""set -euo pipefail
STACK={stack!r}
ENV="$STACK/.env"
COMPOSE="$STACK/docker-compose.yml"
python3 - "$ENV" "$COMPOSE" <<'PY'
import base64, os, re, sys
env_path, compose_path = sys.argv[1:3]
overlay = {{}}
raw = base64.b64decode("{b64_updates}").decode()
for line in raw.splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        overlay[k] = v
existing = {{}}
if os.path.isfile(env_path):
    for line in open(env_path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            existing[k] = v.strip()
if "WIREGUARD_PRIVATE_KEY" not in overlay:
    if existing.get("WIREGUARD_PRIVATE_KEY"):
        overlay["WIREGUARD_PRIVATE_KEY"] = existing["WIREGUARD_PRIVATE_KEY"]
if "WIREGUARD_ADDRESSES" not in overlay and existing.get("WIREGUARD_ADDRESSES"):
    overlay["WIREGUARD_ADDRESSES"] = existing["WIREGUARD_ADDRESSES"]
text = open(env_path, encoding="utf-8").read() if os.path.isfile(env_path) else ""
lines = text.splitlines()
out, seen = [], set()
for line in lines:
    if not line.strip() or line.strip().startswith("#") or "=" not in line:
        out.append(line)
        continue
    key = line.split("=", 1)[0].strip()
    if key in overlay:
        out.append(f"{{key}}={{overlay[key]}}")
        seen.add(key)
    else:
        out.append(line)
for key, val in overlay.items():
    if key not in seen:
        out.append(f"{{key}}={{val}}")
result = "\\n".join(out)
if not result.endswith("\\n"):
    result += "\\n"
open(env_path, "w", encoding="utf-8").write(result)
if os.path.isfile(compose_path):
    body = open(compose_path, encoding="utf-8").read()
    body = body.replace(
        "VPN_SERVICE_PROVIDER=${{VPN_SERVICE_PROVIDER:-mullvad}}",
        "VPN_SERVICE_PROVIDER=${{VPN_SERVICE_PROVIDER:-protonvpn}}",
    )
    if "VPN_PORT_FORWARDING" not in body:
        body = body.replace(
            "      - FIREWALL_OUTBOUND_SUBNETS=192.168.1.0/24",
            "      - VPN_PORT_FORWARDING=${{VPN_PORT_FORWARDING:-on}}\\n"
            "      - VPN_PORT_FORWARDING_PROVIDER=${{VPN_PORT_FORWARDING_PROVIDER:-protonvpn}}\\n"
            "      - PORT_FORWARD_ONLY=${{PORT_FORWARD_ONLY:-on}}\\n"
            "      - FIREWALL_OUTBOUND_SUBNETS=192.168.1.0/24",
            1,
        )
    open(compose_path, "w", encoding="utf-8").write(body)
if not overlay.get("WIREGUARD_PRIVATE_KEY") and not existing.get("WIREGUARD_PRIVATE_KEY"):
    print("WARN: WIREGUARD_PRIVATE_KEY still empty — set it in $STACK/.env", file=sys.stderr)
    print("  Get one: https://account.proton.me/vpn/WireGuard", file=sys.stderr)
else:
    print("env updated for ProtonVPN WireGuard")
PY
cd "$STACK"
docker compose up -d gluetun qbittorrent
sleep 4
docker compose ps gluetun qbittorrent || true
docker compose logs --tail=40 gluetun || true
"""
        code, _, err = run_remote(script)
        if code != 0:
            log(f"ERROR: {err[:500]}")
            return code

    log("")
    log("Gluetun should now use:")
    log("  VPN_SERVICE_PROVIDER=protonvpn")
    log("  VPN_TYPE=wireguard")
    log("  VPN_PORT_FORWARDING=on (Proton port-forward / P2P servers)")
    log("")
    log("If Gluetun restart-loops, add your Proton WireGuard private key:")
    log("  WIREGUARD_PRIVATE_KEY='...' ./radtv repair gluetun")
    log("  https://account.proton.me/vpn/WireGuard")
    log("")
    log(f"  ssh {FLOOR2_USER}@{FLOOR2_HOST} 'cd {stack} && docker compose logs --tail=50 gluetun'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
