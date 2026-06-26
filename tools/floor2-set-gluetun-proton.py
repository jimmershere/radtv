#!/usr/bin/env python3
"""Configure Gluetun on floor2 for ProtonVPN + WireGuard.

Run from quasimodo (SSH to floor2):

    ./radtv repair gluetun
    ./radtv repair import-wg    # headless — no protonvpn signin

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
import time
from typing import Dict, Optional, Tuple

FLOOR2_HOST = os.environ.get("FLOOR2_HOST", "192.168.1.206")
FLOOR2_USER = os.environ.get("FLOOR2_USER", "floor2")
STACK_CANDIDATES = (
    "/datapool/preserved/badtv-arr",
    "/datapool/preserved/radtv-arr",
)

# OpenVPN via Proton preset (uses OpenVPN/IKEv2 creds from account.proton.me — not your login email).
PROTON_OPENVPN_ENV = {
    "VPN_SERVICE_PROVIDER": "protonvpn",
    "VPN_TYPE": "openvpn",
    "SERVER_COUNTRIES": os.environ.get("SERVER_COUNTRIES", "Switzerland"),
    "VPN_PORT_FORWARDING": os.environ.get("VPN_PORT_FORWARDING", "on"),
    "VPN_PORT_FORWARDING_PROVIDER": "protonvpn",
    "PORT_FORWARD_ONLY": os.environ.get("PORT_FORWARD_ONLY", "on"),
    "OPENVPN_USER": "",
    "OPENVPN_PASSWORD": "",
    "WIREGUARD_PRIVATE_KEY": "",
    "WIREGUARD_ADDRESSES": "",
}

PROTON_WG_ENV = {
    "VPN_SERVICE_PROVIDER": "protonvpn",
    "VPN_TYPE": "wireguard",
    "SERVER_COUNTRIES": os.environ.get("SERVER_COUNTRIES", "United States"),
    "VPN_PORT_FORWARDING": os.environ.get("VPN_PORT_FORWARDING", "on"),
    "VPN_PORT_FORWARDING_PROVIDER": "protonvpn",
    "PORT_FORWARD_ONLY": os.environ.get("PORT_FORWARD_ONLY", "on"),
    "OPENVPN_USER": "",
    "OPENVPN_PASSWORD": "",
}

# Proton-downloaded .conf installed as wg0.conf — key tied to one endpoint.
CUSTOM_WG_ENV = {
    "VPN_SERVICE_PROVIDER": "custom",
    "VPN_TYPE": "wireguard",
    "VPN_PORT_FORWARDING": "off",
    "VPN_PORT_FORWARDING_PROVIDER": "",
    "PORT_FORWARD_ONLY": "off",
    "SERVER_COUNTRIES": "",
    "SERVER_CITIES": "",
    "OPENVPN_USER": "",
    "OPENVPN_PASSWORD": "",
}

# Gluetun + ProtonVPN require full country names (not ISO codes like CH or USA).
PROTON_COUNTRY_ALIASES: Dict[str, str] = {
    "usa": "United States",
    "us": "United States",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "uae": "United Arab Emirates",
    "ch": "Switzerland",
    "de": "Germany",
    "fr": "France",
    "ca": "Canada",
    "nl": "Netherlands",
    "se": "Sweden",
    "no": "Norway",
    "es": "Spain",
    "it": "Italy",
    "jp": "Japan",
    "au": "Australia",
    "nz": "New Zealand",
    "sg": "Singapore",
    "hk": "Hong Kong",
    "tw": "Taiwan",
    "kr": "Korea",
    "mx": "Mexico",
    "br": "Brazil",
    "in": "India",
    "pl": "Poland",
    "ro": "Romania",
    "cz": "Czech Republic",
    "at": "Austria",
    "be": "Belgium",
    "dk": "Denmark",
    "fi": "Finland",
    "ie": "Ireland",
    "pt": "Portugal",
    "tr": "Turkey",
    "ua": "Ukraine",
    "ru": "Russian Federation",
    "za": "South Africa",
}


def normalize_proton_country(value: str) -> str:
    """Map USA/CH/etc. to Gluetun's Proton country names."""
    v = value.strip()
    if not v:
        return "United States"
    alias = PROTON_COUNTRY_ALIASES.get(v.lower())
    if alias:
        return alias
    return v


def infer_country_from_wg_conf(path: str) -> str:
    """Guess Proton server country from WireGuard config path or Endpoint hostname."""
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0]
    # floor2-CH-262, us-free, ch-27, UK#1, etc.
    for part in re.split(r"[-_#]+", stem):
        code = part.strip().lower()
        if code in PROTON_COUNTRY_ALIASES:
            return PROTON_COUNTRY_ALIASES[code]
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if not line.lower().startswith("endpoint"):
                    continue
                host = line.split("=", 1)[1].strip().split(":")[0].lower()
                m = re.search(r"(?:^|\.)([a-z]{2})[-.]", host)
                if m and m.group(1) in PROTON_COUNTRY_ALIASES:
                    return PROTON_COUNTRY_ALIASES[m.group(1)]
                m = re.search(r"^([a-z]{2})[-.]", host)
                if m and m.group(1) in PROTON_COUNTRY_ALIASES:
                    return PROTON_COUNTRY_ALIASES[m.group(1)]
    except OSError:
        pass
    return ""


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
    data = parse_wg_conf_full(path)
    return data.get("private_key", ""), data.get("addresses", "")


def parse_wg_conf_full(path: str) -> Dict[str, str]:
    """Parse a Proton/Gluetun WireGuard ini file."""
    out: Dict[str, str] = {}
    section = ""
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].lower()
                continue
            if "=" not in line:
                continue
            key, val = (p.strip() for p in line.split("=", 1))
            lk = key.lower()
            if section == "interface" and lk == "privatekey":
                out["private_key"] = val
            elif section == "interface" and lk == "address":
                out["addresses"] = val
            elif section == "peer" and lk == "publickey":
                out["public_key"] = val
            elif section == "peer" and lk == "presharedkey":
                out["preshared_key"] = val
            elif section == "peer" and lk == "endpoint":
                host, _, port = val.partition(":")
                out["endpoint_host"] = host
                out["endpoint_port"] = port or "51820"
    return out


def install_wg_conf_file(stack: str, conf_path: str) -> str:
    """Copy Proton .conf into the Gluetun volume as wg0.conf."""
    dest_dir = f"{stack}/gluetun/wireguard"
    dest = f"{dest_dir}/wg0.conf"
    os.makedirs(dest_dir, mode=0o700, exist_ok=True)
    with open(conf_path, encoding="utf-8") as src, open(dest, "w", encoding="utf-8") as dst:
        dst.write(src.read())
    os.chmod(dest, 0o600)
    return dest


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


def fix_compose_interpolation(compose: str) -> str:
    """${{VAR:-x}} (template artifact) → ${VAR:-x} for docker compose."""
    return re.sub(r"\$\{\{([^}]+)\}\}", r"${\1}", compose)


def patch_compose_proton(compose: str, *, vpn_type: str = "openvpn") -> str:
    compose = fix_compose_interpolation(compose)
    compose = re.sub(
        r"VPN_SERVICE_PROVIDER=\$\{\{VPN_SERVICE_PROVIDER:-mullvad\}\}",
        "VPN_SERVICE_PROVIDER=${VPN_SERVICE_PROVIDER:-protonvpn}",
        compose,
    )
    compose = re.sub(
        r"VPN_TYPE=\$\{VPN_TYPE:-wireguard\}",
        f"VPN_TYPE=${{VPN_TYPE:-{vpn_type}}}",
        compose,
        count=1,
    )
    if "OPENVPN_USER" not in compose:
        compose = re.sub(
            r"(^  gluetun:\n(?:  [^\n]*\n)*?      - VPN_TYPE=.*\n)",
            r"\1      - OPENVPN_USER=${OPENVPN_USER:-}\n"
            r"      - OPENVPN_PASSWORD=${OPENVPN_PASSWORD:-}\n",
            compose,
            count=1,
            flags=re.M,
        )
    if "VPN_PORT_FORWARDING" not in compose:
        compose = compose.replace(
            "      - FIREWALL_OUTBOUND_SUBNETS=192.168.1.0/24",
            "      - VPN_PORT_FORWARDING=${VPN_PORT_FORWARDING:-on}\n"
            "      - VPN_PORT_FORWARDING_PROVIDER=${VPN_PORT_FORWARDING_PROVIDER:-protonvpn}\n"
            "      - PORT_FORWARD_ONLY=${PORT_FORWARD_ONLY:-on}\n"
            "      - FIREWALL_INPUT_PORTS=${FIREWALL_INPUT_PORTS:-8091}\n"
            "      - FIREWALL_OUTBOUND_SUBNETS=192.168.1.0/24,172.16.0.0/12",
            1,
        )
    elif "FIREWALL_INPUT_PORTS" not in compose:
        compose = re.sub(
            r"(^  gluetun:\n(?:  [^\n]*\n)*?    environment:\n)",
            r"\1      - FIREWALL_INPUT_PORTS=${FIREWALL_INPUT_PORTS:-8091}\n",
            compose,
            count=1,
            flags=re.M,
        )
    return fix_compose_interpolation(compose)


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


def parse_credentials_env(path: str) -> Tuple[str, str]:
    """Parse Proton OpenVPN creds file (userid/password or OPENVPN_USER=)."""
    user, password = "", ""
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = (p.strip() for p in line.split("=", 1))
            elif ":" in line:
                key, val = (p.strip() for p in line.split(":", 1))
            else:
                continue
            lk = key.lower()
            if lk in ("userid", "user", "username", "openvpn_user"):
                user = val
            elif lk in ("password", "openvpn_password"):
                password = val
    return user, password


def find_credentials_env(stack: str) -> str:
    candidates = [
        os.environ.get("PROTON_CREDENTIALS_ENV", "").strip(),
        os.environ.get("PROTON_OPENVPN_ENV", "").strip(),
        "/tmp/wg.env",
        f"{stack}/gluetun/proton-credentials.env",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return ""


def install_credentials_env(stack: str, src_path: str) -> str:
    dest = f"{stack}/gluetun/proton-credentials.env"
    os.makedirs(os.path.dirname(dest), mode=0o700, exist_ok=True)
    with open(src_path, encoding="utf-8") as src, open(dest, "w", encoding="utf-8") as dst:
        dst.write(src.read())
    os.chmod(dest, 0o600)
    return dest


def openvpn_user_for_proton(user: str) -> str:
    """Append +pmp for port-forwarding when enabled (Proton OpenVPN convention)."""
    user = user.strip()
    if not user or "+pmp" in user:
        return user
    if os.environ.get("VPN_PORT_FORWARDING", "on").lower() in ("1", "on", "true", "yes"):
        return f"{user}+pmp"
    return user


def country_from_sources(existing_env: Dict[str, str], conf: str) -> str:
    if conf and os.path.isfile(conf):
        inferred = infer_country_from_wg_conf(conf)
        if inferred:
            return inferred
    return normalize_proton_country(
        os.environ.get("SERVER_COUNTRIES", "")
        or existing_env.get("SERVER_COUNTRIES", "")
        or "Switzerland"
    )


def resolve_gluetun_settings(
    stack: str, existing_env: Dict[str, str]
) -> Tuple[Dict[str, str], str, str]:
    """Return (.env updates, vpn_type, detail path/message)."""
    conf = os.environ.get("PROTON_WG_CONF", "").strip()
    if not conf and on_floor2():
        conf = find_tmp_wg_conf()
    creds_path = find_credentials_env(stack)
    vpn_mode = os.environ.get("GLUETUN_VPN_TYPE", "").strip().lower()
    country = country_from_sources(existing_env, conf)

    if creds_path and vpn_mode != "wireguard":
        user, password = parse_credentials_env(creds_path)
        if not user or not password:
            log(f"ERROR: {creds_path} needs userid + password (OpenVPN creds from account.proton.me)")
            sys.exit(1)
        stored = install_credentials_env(stack, creds_path)
        updates = dict(PROTON_OPENVPN_ENV)
        updates["OPENVPN_USER"] = openvpn_user_for_proton(user)
        updates["OPENVPN_PASSWORD"] = password
        updates["SERVER_COUNTRIES"] = country
        updates["FIREWALL_INPUT_PORTS"] = os.environ.get("FIREWALL_INPUT_PORTS", "8091")
        updates["FIREWALL_OUTBOUND_SUBNETS"] = "192.168.1.0/24,172.16.0.0/12"
        if os.environ.get("FREE_ONLY", "").strip():
            updates["FREE_ONLY"] = os.environ["FREE_ONLY"].strip()
        log(f"mode: protonvpn + openvpn (country={country})")
        log(f"OpenVPN creds: {stored} (mode 0600)")
        if conf:
            log(f"country from WireGuard conf: {conf}")
        return updates, "openvpn", stored

    if conf and os.path.isfile(conf) and vpn_mode != "openvpn":
        dest = install_wg_conf_file(stack, conf)
        log(f"installed WireGuard config: {dest}")
        log("mode: VPN_SERVICE_PROVIDER=custom (wg0.conf)")
        updates = dict(CUSTOM_WG_ENV)
        updates["FIREWALL_INPUT_PORTS"] = os.environ.get("FIREWALL_INPUT_PORTS", "8091")
        updates["FIREWALL_OUTBOUND_SUBNETS"] = "192.168.1.0/24,172.16.0.0/12"
        for stale in (
            "WIREGUARD_PRIVATE_KEY",
            "WIREGUARD_ADDRESSES",
            "WIREGUARD_PUBLIC_KEY",
            "WIREGUARD_ENDPOINT_IP",
            "WIREGUARD_ENDPOINT_PORT",
            "OPENVPN_USER",
            "OPENVPN_PASSWORD",
        ):
            updates[stale] = ""
        return updates, "wireguard", dest

    wg_key = os.environ.get("WIREGUARD_PRIVATE_KEY", "").strip() or existing_env.get(
        "WIREGUARD_PRIVATE_KEY", ""
    ).strip()
    wg_addr = os.environ.get("WIREGUARD_ADDRESSES", "").strip() or existing_env.get(
        "WIREGUARD_ADDRESSES", ""
    ).strip()
    if conf and os.path.isfile(conf):
        ckey, caddr = parse_wg_conf(conf)
        wg_key = wg_key or ckey
        wg_addr = wg_addr or caddr
    updates = dict(PROTON_WG_ENV)
    updates["SERVER_COUNTRIES"] = country
    if wg_key:
        updates["WIREGUARD_PRIVATE_KEY"] = wg_key
    if wg_addr:
        updates["WIREGUARD_ADDRESSES"] = wg_addr
    log(f"mode: protonvpn + wireguard (country={country})")
    return updates, "wireguard", ""


def resolve_wireguard_settings(existing_env: Dict[str, str]) -> Tuple[Dict[str, str], str]:
    stack = detect_stack()
    updates, vpn_type, detail = resolve_gluetun_settings(stack, existing_env)
    return updates, detail if vpn_type == "wireguard" and detail else ""


def resolve_wireguard_key(existing_env: Dict[str, str]) -> Tuple[str, str, str]:
    updates, conf_dest = resolve_wireguard_settings(existing_env)
    if conf_dest:
        data = parse_wg_conf_full(
            os.environ.get("PROTON_WG_CONF", "").strip() or find_tmp_wg_conf() or conf_dest
        )
        return (
            data.get("private_key", ""),
            data.get("addresses", ""),
            infer_country_from_wg_conf(conf_dest) or "Switzerland",
        )
    return (
        updates.get("WIREGUARD_PRIVATE_KEY", ""),
        updates.get("WIREGUARD_ADDRESSES", ""),
        updates.get("SERVER_COUNTRIES", "United States"),
    )


def run_compose_fix(stack: str) -> int:
    fix_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "floor2-fix-compose.py")
    if not os.path.isfile(fix_py):
        return 0
    env = {**os.environ, "FLOOR2_STACK": stack}
    cp = subprocess.run([sys.executable, fix_py], env=env)
    return cp.returncode


def main() -> int:
    stack = detect_stack()
    env_path = f"{stack}/.env"
    compose_path = f"{stack}/docker-compose.yml"

    log("floor2 Gluetun → ProtonVPN + WireGuard")
    log(f"stack: {stack}")

    if on_floor2():
        existing = read_env_file(env_path)
        updates, vpn_type, detail = resolve_gluetun_settings(stack, existing)
        if detail:
            log(f"detail: {detail}")
        if vpn_type == "openvpn":
            log("using Proton OpenVPN creds + country from wg .conf")
        elif not updates.get("WIREGUARD_PRIVATE_KEY") and vpn_type != "openvpn":
            log("ERROR: no config — set PROTON_CREDENTIALS_ENV=/tmp/wg.env and/or PROTON_WG_CONF")
            return 1
        text = open(env_path, encoding="utf-8").read() if os.path.isfile(env_path) else ""
        open(env_path, "w", encoding="utf-8").write(upsert_env_text(text, updates))
        if os.path.isfile(compose_path):
            body = open(compose_path, encoding="utf-8").read()
            open(compose_path, "w", encoding="utf-8").write(
                patch_compose_proton(body, vpn_type=vpn_type)
            )
        subprocess.run(
            ["bash", "-c", f"cd {stack} && docker compose up -d gluetun qbittorrent"],
            check=False,
        )
        for i in range(30):
            cp = subprocess.run(
                ["bash", "-c", f"cd {stack} && docker compose ps gluetun"],
                capture_output=True,
                text=True,
            )
            if "Up" in cp.stdout and "Restarting" not in cp.stdout:
                log("Gluetun is up")
                break
            time.sleep(2)
        else:
            log("WARN: Gluetun not healthy yet — check: docker compose logs --tail=40 gluetun")
        subprocess.run(
            ["bash", "-c", f"cd {stack} && docker compose logs --tail=30 gluetun"],
            check=False,
        )
    else:
        # Ship key/conf to remote without echoing in process list when possible
        local_env = {}
        conf = os.environ.get("PROTON_WG_CONF", "").strip()
        country = normalize_proton_country(os.environ.get("SERVER_COUNTRIES", ""))
        if conf and os.path.isfile(conf):
            k, a = parse_wg_conf(conf)
            if k:
                local_env["WIREGUARD_PRIVATE_KEY"] = k
            if a:
                local_env["WIREGUARD_ADDRESSES"] = a
            inferred = infer_country_from_wg_conf(conf)
            if inferred:
                country = inferred
        if country:
            local_env["SERVER_COUNTRIES"] = country
        if os.environ.get("WIREGUARD_PRIVATE_KEY"):
            local_env["WIREGUARD_PRIVATE_KEY"] = os.environ["WIREGUARD_PRIVATE_KEY"].strip()
        if os.environ.get("WIREGUARD_ADDRESSES"):
            local_env["WIREGUARD_ADDRESSES"] = os.environ["WIREGUARD_ADDRESSES"].strip()

        b64_updates = base64.b64encode(
            "\n".join(f"{k}={v}" for k, v in {**PROTON_WG_ENV, **local_env}.items()).encode()
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
FIX_PY={repr(os.path.join(os.path.dirname(os.path.abspath(__file__)), "floor2-fix-compose.py"))}
[[ -f "$FIX_PY" ]] && python3 "$FIX_PY" || true
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

    run_compose_fix(stack)

    log("")
    log("Gluetun configured:")
    log("  OpenVPN: set PROTON_CREDENTIALS_ENV=/tmp/wg.env (userid + password from account.proton.me/vpn/OpenVPN)")
    log("  WireGuard: set PROTON_WG_CONF=/tmp/your.conf (country inferred for OpenVPN)")
    log("  Prefer OpenVPN when wg.env creds exist — more stable than custom wg0.conf on floor2")
    log("")
    log(f"  ssh {FLOOR2_USER}@{FLOOR2_HOST} 'cd {stack} && docker compose logs --tail=50 gluetun'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
