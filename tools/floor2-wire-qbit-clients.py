#!/usr/bin/env python3
"""Wire qBittorrent into Prowlarr/Sonarr/Radarr on floor2 (Gluetun network).

qBittorrent shares Gluetun's network (network_mode: service:gluetun). Other
*arr containers must use the Gluetun container hostname (e.g. badtv-gluetun)
on port 8091 — not the Gluetun internal IP from logs.

Gluetun blocks inbound by default; FIREWALL_INPUT_PORTS=8091 is required.

Run on floor2:
    ./radtv repair wire-qbit
    ./radtv repair qbittorrent   # also runs credential + wiring steps
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

FLOOR2_HOST = os.environ.get("FLOOR2_HOST", "192.168.1.206")
STACK_CANDIDATES = (
    "/datapool/preserved/badtv-arr",
    "/datapool/preserved/radtv-arr",
)
QBIT_PORT = 8091
QBIT_USER = os.environ.get("QBITTORRENT_USER", "jimmer")
QBIT_PASS = os.environ.get("QBITTORRENT_PASSWORD", "J1mm3r-F2-qBT-9k!")


def log(msg: str) -> None:
    print(msg, flush=True)


def on_floor2() -> bool:
    return os.path.isdir("/datapool/preserved")


def detect_stack() -> str:
    if os.environ.get("FLOOR2_STACK"):
        return os.environ["FLOOR2_STACK"]
    for stack in STACK_CANDIDATES:
        if os.path.isfile(f"{stack}/docker-compose.yml"):
            return stack
    return STACK_CANDIDATES[0]


def read_compose(stack: str) -> str:
    return open(f"{stack}/docker-compose.yml", encoding="utf-8").read()


def gluetun_hostname(compose: str) -> str:
    m = re.search(r"container_name:\s*(\S+-gluetun)\b", compose)
    if m:
        return m.group(1)
    m = re.search(r"^\s{2}gluetun:\s*$", compose, re.M)
    return "badtv-gluetun" if m else "gluetun"


def patch_gluetun_firewall(compose: str) -> str:
    compose = re.sub(r"\$\{\{([^}]+)\}\}", r"${\1}", compose)
    if "FIREWALL_INPUT_PORTS" not in compose:
        if "FIREWALL_OUTBOUND_SUBNETS" in compose:
            compose = compose.replace(
                "      - FIREWALL_OUTBOUND_SUBNETS=",
                "      - FIREWALL_INPUT_PORTS=${FIREWALL_INPUT_PORTS:-8091}\n"
                "      - FIREWALL_OUTBOUND_SUBNETS=",
                1,
            )
        else:
            compose = compose.replace(
                "    environment:",
                "    environment:\n"
                "      - FIREWALL_INPUT_PORTS=${FIREWALL_INPUT_PORTS:-8091}",
                1,
            )
    # Allow Docker bridge traffic (Prowlarr -> Gluetun) + LAN
    compose = re.sub(
        r"(FIREWALL_OUTBOUND_SUBNETS=\$\{FIREWALL_OUTBOUND_SUBNETS:-)([^}]+)(\})",
        lambda m: (
            f"{m.group(1)}{m.group(2)},172.16.0.0/12{m.group(3)}"
            if "172.16.0.0/12" not in m.group(2)
            else m.group(0)
        ),
        compose,
    )
    compose = re.sub(
        r"(FIREWALL_OUTBOUND_SUBNETS=)(192\.168\.1\.0/24)\s*$",
        r"\1\2,172.16.0.0/12",
        compose,
        flags=re.M,
    )
    return compose


def upsert_env_line(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    out: List[str] = []
    found = False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    result = "\n".join(out)
    if not result.endswith("\n"):
        result += "\n"
    return result


def read_handover(stack: str) -> Tuple[str, str]:
    path = f"{stack}/qbittorrent/rdtv-qbit-handover.json"
    if os.path.isfile(path):
        try:
            data = json.loads(open(path, encoding="utf-8").read())
            return data.get("username", QBIT_USER), data.get("password", QBIT_PASS)
        except (json.JSONDecodeError, OSError):
            pass
    return QBIT_USER, QBIT_PASS


def read_xml_key(stack: str, app: str) -> str:
    path = f"{stack}/{app}/config.xml"
    if not os.path.isfile(path):
        return ""
    m = re.search(r"<ApiKey>([^<]+)</ApiKey>", open(path, encoding="utf-8").read())
    return m.group(1).strip() if m else ""


def api_json(method: str, url: str, key: str, payload: Any = None) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"X-Api-Key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from exc


def set_field(fields: List[Dict[str, Any]], name: str, value: Any) -> None:
    for field in fields:
        if field.get("name") == name:
            field["value"] = value
            return
    fields.append({"name": name, "value": value})


def build_qbit_payload(schema: Dict[str, Any], host: str, user: str, password: str,
                       category: str, name: str) -> Dict[str, Any]:
    skip = {"id", "tags"}
    payload = {k: v for k, v in schema.items() if k not in skip}
    payload["name"] = name
    payload["enable"] = True
    payload["protocol"] = "torrent"
    payload["priority"] = 1
    payload["removeCompletedDownloads"] = True
    payload["removeFailedDownloads"] = True
    fields = list(payload.get("fields") or [])
    set_field(fields, "host", host)
    set_field(fields, "port", QBIT_PORT)
    set_field(fields, "useSsl", False)
    set_field(fields, "urlBase", "")
    set_field(fields, "username", user)
    set_field(fields, "password", password)
    set_field(fields, "category", category)
    payload["fields"] = fields
    return payload


def register_prowlarr_qbit(prowlarr_url: str, apikey: str, host: str, user: str, password: str) -> None:
    log(">> Prowlarr: register qBittorrent download client")
    schemas = api_json("GET", f"{prowlarr_url}/api/v1/downloadclient/schema", apikey) or []
    schema = next((s for s in schemas if s.get("implementation") == "QBittorrent"), None)
    if not schema:
        raise RuntimeError("Prowlarr QBittorrent schema not found")
    existing = api_json("GET", f"{prowlarr_url}/api/v1/downloadclient", apikey) or []
    for client in existing:
        if client.get("implementation") == "QBittorrent":
            log(f"   removing old qBittorrent client id={client['id']}")
            api_json("DELETE", f"{prowlarr_url}/api/v1/downloadclient/{client['id']}", apikey)
    payload = build_qbit_payload(schema, host, user, password, "prowlarr", "qBittorrent")
    created = api_json("POST", f"{prowlarr_url}/api/v1/downloadclient", apikey, payload)
    if not created or "id" not in created:
        raise RuntimeError("Prowlarr qBittorrent create failed")
    log(f"   added qBittorrent (id={created['id']}) host={host} port={QBIT_PORT}")
    try:
        api_json("POST", f"{prowlarr_url}/api/v1/downloadclient/test", apikey, created)
        log("   Prowlarr test: OK")
    except RuntimeError as exc:
        log(f"   WARN: Prowlarr test failed: {exc}")


def register_arr_qbit(base_url: str, apikey: str, label: str, host: str,
                      user: str, password: str, category: str) -> None:
    log(f">> {label}: register qBittorrent download client")
    schemas = api_json("GET", f"{base_url}/api/v3/downloadclient/schema", apikey) or []
    schema = next((s for s in schemas if s.get("implementation") == "QBittorrent"), None)
    if not schema:
        log(f"   WARN: {label} QBittorrent schema not found — skip")
        return
    existing = api_json("GET", f"{base_url}/api/v3/downloadclient", apikey) or []
    for client in existing:
        if client.get("implementation") == "QBittorrent":
            api_json("DELETE", f"{base_url}/api/v3/downloadclient/{client['id']}", apikey)
    payload = build_qbit_payload(schema, host, user, password, category, "qBittorrent")
    created = api_json("POST", f"{base_url}/api/v3/downloadclient", apikey, payload)
    if created and "id" in created:
        log(f"   {label}: qBittorrent added (id={created['id']})")
    else:
        log(f"   WARN: {label} qBittorrent add failed")


def test_from_prowlarr(stack: str, host: str) -> None:
    compose = read_compose(stack)
    m = re.search(r"container_name:\s*(\S+-prowlarr)\b", compose)
    prowlarr_c = m.group(1) if m else "badtv-prowlarr"
    cmd = (
        f"docker exec {prowlarr_c} wget -q -O- --timeout=5 "
        f"http://{host}:{QBIT_PORT}/ 2>&1 | head -c 80 || true"
    )
    cp = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    if cp.returncode == 0 and cp.stdout.strip():
        log(f"   connectivity from {prowlarr_c} -> {host}:{QBIT_PORT}: OK")
    else:
        log(f"   WARN: connectivity test failed ({prowlarr_c} -> {host}:{QBIT_PORT})")
        if cp.stderr:
            log(f"   {cp.stderr.strip()[:200]}")


def main() -> int:
    if not on_floor2():
        log("ERROR: run this on floor2 (or via: ssh floor2 'cd /app/radtv && ./radtv repair wire-qbit')")
        return 1

    stack = detect_stack()
    compose_path = f"{stack}/docker-compose.yml"
    env_path = f"{stack}/.env"
    log(f"stack: {stack}")

    compose = read_compose(stack)
    host = gluetun_hostname(compose)
    log(f"qBittorrent host for *arr apps: {host} (port {QBIT_PORT})")

    patched = patch_gluetun_firewall(compose)
    if patched != compose:
        open(compose_path, "w", encoding="utf-8").write(patched)
        log("patched docker-compose.yml: FIREWALL_INPUT_PORTS=8091")

    env_text = open(env_path, encoding="utf-8").read() if os.path.isfile(env_path) else ""
    env_text = upsert_env_line(env_text, "FIREWALL_INPUT_PORTS", str(QBIT_PORT))
    if "FIREWALL_OUTBOUND_SUBNETS" in env_text and "172.16.0.0/12" not in env_text:
        env_text = re.sub(
            r"^FIREWALL_OUTBOUND_SUBNETS=(.*)$",
            lambda m: f"FIREWALL_OUTBOUND_SUBNETS={m.group(1)},172.16.0.0/12"
            if "172.16.0.0/12" not in m.group(1) else m.group(0),
            env_text,
            flags=re.M,
        )
    open(env_path, "w", encoding="utf-8").write(env_text)
    log("updated .env: FIREWALL_INPUT_PORTS=8091")

    log("restarting gluetun + qbittorrent...")
    subprocess.run(
        ["bash", "-c", f"cd {stack} && docker compose up -d gluetun qbittorrent"],
        check=False,
    )
    import time
    time.sleep(8)

    user, password = read_handover(stack)
    prowlarr_key = read_xml_key(stack, "prowlarr")
    if prowlarr_key:
        try:
            register_prowlarr_qbit(f"http://127.0.0.1:9696", prowlarr_key, host, user, password)
        except Exception as exc:
            log(f"WARN: Prowlarr wiring: {exc}")
    else:
        log("WARN: no Prowlarr API key — add qBittorrent manually in Prowlarr UI")

    sonarr_key = read_xml_key(stack, "sonarr")
    if sonarr_key:
        try:
            register_arr_qbit(
                f"http://127.0.0.1:8989", sonarr_key, "Sonarr",
                host, user, password, "tv-qbit",
            )
        except Exception as exc:
            log(f"WARN: Sonarr wiring: {exc}")

    radarr_key = read_xml_key(stack, "radarr")
    if radarr_key:
        try:
            register_arr_qbit(
                f"http://127.0.0.1:7878", radarr_key, "Radarr",
                host, user, password, "movies-qbit",
            )
        except Exception as exc:
            log(f"WARN: Radarr wiring: {exc}")

    test_from_prowlarr(stack, host)

    log("")
    log("Prowlarr qBittorrent settings:")
    log(f"  Host:     {host}")
    log(f"  Port:     {QBIT_PORT}")
    log(f"  Username: {user}")
    log(f"  Password: (see handover file or run ./radtv repair qbittorrent)")
    log(f"  Browser:  http://{FLOOR2_HOST}:{QBIT_PORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
