#!/usr/bin/env python3
"""B@Dtv host-side bootstrap wizard.

Single command, terminal TUI, walks the user from a fresh Linux box (or a
laptop with Kodi already installed) all the way to a working Kodi launched
in kiosk mode on the attached display.

Usage:
    ./badtv setup           # full guided run
    ./badtv setup --resume  # pick up where the last run failed
    ./badtv status          # show which steps are done
    ./badtv launch          # just launch Kodi
    ./badtv repair <step>   # re-run one specific step

Idempotent: every step records itself in ~/.config/badtv/state.json so
re-runs skip what's done. Verbose log at ~/.config/badtv/setup.log.

Designed to use ONLY Python stdlib so a fresh box can run it before any
pip is installed. The wizard apt-installs python3-yaml itself if it needs
to parse YAML (the IPTV source list).
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET


# --- constants ---------------------------------------------------------------

VERSION = "2.3.0"
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.expanduser("~/.config/badtv")
STATE_PATH = os.path.join(STATE_DIR, "state.json")
LOG_PATH = os.path.join(STATE_DIR, "setup.log")

KODI_USERDATA = os.path.expanduser("~/.kodi/userdata")
KODI_ADDONS = os.path.expanduser("~/.kodi/addons")
KODI_MIRROR = "https://mirrors.kodi.tv/addons/nexus"

DEBIAN_PKGS = [
    "kodi",
    "kodi-inputstream-adaptive",
    "kodi-inputstream-rtmp",
    "kodi-inputstream-ffmpegdirect",
    "kodi-pvr-iptvsimple",
    "kodi-vfs-libarchive",
    "mpv",                # for the stream test step
    "wireguard-tools",    # used by the WireGuard VPN path
    "nftables",           # kill-switch for the WireGuard path
    "curl",
    "ca-certificates",
    "python3-yaml",       # used internally and by tools/refresh-scrapers.py
]

# Addons confirmed present in mirrors.kodi.tv/addons/nexus (verified live).
# Anything community-only (Tubi, A4K Subtitles, Umbrella, etc.) needs its
# upstream repo zip and is installed by step_grey_addons below.
#
# Dropped 2026-05-24: plugin.video.crackle (upstream marked
# <lifecyclestate type="broken"> + <platform>android</platform>, so Kodi
# silently refuses to register it on desktop Linux anyway).
OFFICIAL_ADDONS = [
    "plugin.video.youtube",
    "plugin.video.plutotv",
    "script.plexmod",
    "skin.arctic.zephyr.mod",
]

# --- Grey-area scraper stack (Real-Debrid / Trakt / AllDebrid driven) ------
#
# Each entry is a Kodi repository served as a single zip at the root of a
# GitHub Pages site (or similar). The bootstrap downloads the wrapper repo
# zip, extracts the inner `repository.<name>` addon, parses its addon.xml,
# picks the <dir> block matching this host's Kodi major (Nexus 20 = nexus,
# Omega 21 = omega, Matrix 19 = matrix), then resolves and installs the
# named `plugins` plus their full dependency tree.
#
# Live verified 2026-05-24. If a URL rots, the in-Kodi wizard's catalog
# refresh and `tools/refresh-scrapers.py` will flag it; the canonical list
# lives in addons/scraper-catalog.json and is reproduced here for the
# pre-Kodi bootstrap which can't talk to the wizard yet.
GREY_REPOS: List[Dict[str, Any]] = [
    {
        "name": "ResolveURL",
        # No wrapper repo zip -- the addons.xml is served directly.
        "repo_zip_url": None,
        "addons_xml": {
            "nexus":  "https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml",
            "omega":  "https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml",
            "matrix": "https://raw.githubusercontent.com/Gujal00/smrzips/master/addons.xml",
        },
        "datadir":  "https://raw.githubusercontent.com/Gujal00/smrzips/master/zips/",
        "plugins":  ["script.module.resolveurl"],
    },
    {
        "name": "CocoScrapers",
        "repo_zip_url": "https://cocojoe2411.github.io/repository.cocoscrapers-1.0.1.zip",
        "plugins": ["script.module.cocoscrapers"],
    },
    {
        "name": "Umbrella",
        "repo_zip_url": "https://umbrellaplug.github.io/repository.umbrella-2.2.6.zip",
        "plugins": ["plugin.video.umbrella"],
    },
    {
        "name": "The Crew",
        "repo_zip_url": "https://team-crew.github.io/repository.thecrew-0.3.8.zip",
        "plugins": ["plugin.video.thecrew"],
    },
    {
        "name": "Seren",
        "repo_zip_url": "https://nixgates.github.io/packages/repository.nixgates-2.2.0.zip",
        "plugins": ["plugin.video.seren"],
    },
    {
        "name": "POV",
        "repo_zip_url": "https://kodifitzwell.github.io/repo/repository.kodifitzwell-0.0.1.zip",
        "plugins": ["plugin.video.pov"],
    },
]

# Apt-managed binary addons -- their metadata lives under /usr/share/kodi
# and there's no zip in any mirror to fall back on. Dep resolver must
# stop on these instead of 404'ing.
DEBIAN_PROVIDED = {
    "inputstream.adaptive", "inputstream.rtmp", "inputstream.ffmpegdirect",
    "pvr.iptvsimple", "pvr.hts", "vfs.libarchive",
}
SKIN_ID = "skin.arctic.zephyr.mod"
SKIN_THEME_NAME = "badtv"
SKIN_OVERRIDE_DIR_NAME = "arctic-zephyr-mod"

# OAuth client ids -- these are public app identifiers used by the addons
# themselves, baked into their default settings. We use the same ones so
# the device-code flow writes a token the addon recognises on first load.
TRAKT_CLIENT_ID = "90901c6be3b2de5a4fa0edf9ab5c75e9144a3c5cf2e8e5f4f5b5e7fbe1f4d4e7"
TRAKT_DEVICE_URL = "https://api.trakt.tv/oauth/device/code"
TRAKT_TOKEN_URL  = "https://api.trakt.tv/oauth/device/token"
REALDEBRID_CLIENT_ID = "X245A4XAIBGVM"   # public RD client id used by URLResolver
REALDEBRID_DEVICE_URL = "https://api.real-debrid.com/oauth/v2/device/code"
REALDEBRID_CREDS_URL  = "https://api.real-debrid.com/oauth/v2/device/credentials"
REALDEBRID_TOKEN_URL  = "https://api.real-debrid.com/oauth/v2/token"

USER_AGENT = f"B@Dtv-bootstrap/{VERSION}"
HTTP_TIMEOUT = 20


# --- TUI primitives ---------------------------------------------------------

class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    AMBER   = "\033[38;5;214m"
    BRICK   = "\033[38;5;124m"
    GREEN   = "\033[38;5;71m"
    GREY    = "\033[38;5;245m"
    PARCH   = "\033[38;5;230m"


def cprint(text: str, *, color: str = "", bold: bool = False, end: str = "\n") -> None:
    prefix = (Color.BOLD if bold else "") + color
    suffix = Color.RESET if (color or bold) else ""
    print(f"{prefix}{text}{suffix}", end=end, flush=True)


def header(text: str) -> None:
    bar = "─" * max(2, 78 - len(text))
    print()
    cprint(f"━━ {text} {bar}", color=Color.AMBER, bold=True)


def section(text: str) -> None:
    cprint(f"\n{text}", color=Color.PARCH, bold=True)


def info(text: str) -> None:
    cprint(f"  · {text}", color=Color.GREY)
    log(f"info: {text}")


def ok(text: str) -> None:
    cprint(f"  ✓ {text}", color=Color.GREEN)
    log(f"ok:   {text}")


def warn(text: str) -> None:
    cprint(f"  ! {text}", color=Color.AMBER, bold=True)
    log(f"warn: {text}")


def err(text: str) -> None:
    cprint(f"  ✗ {text}", color=Color.BRICK, bold=True)
    log(f"err:  {text}")


def banner() -> None:
    cprint(r"""
   ____   _____ _____      _
  | __ ) / _ \ |_   _|_   _| |
  |  _ \| | | | | || \ \ / / |    Hell's Kitchen-grade Kodi
  | |_) | |_| | | || |\ V /|_|       host-side bootstrap
  |____/ \___/  |_||_| \_/ (_)
""", color=Color.AMBER, bold=True)
    cprint(f"  v{VERSION}   ·   docs: github.com/jimmershere/badtv\n",
           color=Color.GREY)


def ask(prompt: str, default: Optional[str] = None,
        choices: Optional[List[str]] = None) -> str:
    """Free-text prompt with optional default and choices validation."""
    while True:
        hint = ""
        if choices:
            hint = f" [{'/'.join(choices)}]"
        elif default is not None:
            hint = f" [{default}]"
        cprint(f"  ? {prompt}{hint}: ", color=Color.AMBER, bold=True, end="")
        try:
            raw = input().strip()
        except EOFError:
            print()
            return default or ""
        if not raw and default is not None:
            return default
        if choices:
            for c in choices:
                if raw.lower() == c.lower():
                    return c
            err(f"please pick one of: {', '.join(choices)}")
            continue
        return raw


def confirm(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        cprint(f"  ? {prompt} [{suffix}]: ",
               color=Color.AMBER, bold=True, end="")
        try:
            raw = input().strip().lower()
        except EOFError:
            print()
            return default
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        err("please answer y or n")


def menu(title: str, items: List[str], multiselect: bool = False) -> List[int]:
    cprint(f"\n  {title}", color=Color.PARCH, bold=True)
    for idx, item in enumerate(items, 1):
        cprint(f"    {idx}. {item}", color=Color.PARCH)
    while True:
        if multiselect:
            raw = ask("pick numbers (comma-separated)")
            try:
                picks = [int(x.strip()) for x in raw.split(",") if x.strip()]
                if all(1 <= p <= len(items) for p in picks):
                    return [p - 1 for p in picks]
            except ValueError:
                pass
            err("invalid selection")
        else:
            raw = ask("pick a number")
            try:
                p = int(raw)
                if 1 <= p <= len(items):
                    return [p - 1]
            except ValueError:
                pass
            err("invalid selection")


# --- state + logging --------------------------------------------------------

def _ensure_state_dir() -> None:
    os.makedirs(STATE_DIR, exist_ok=True)


def log(msg: str) -> None:
    _ensure_state_dir()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(f"{ts}  {msg}\n")


def load_state() -> Dict[str, Any]:
    if not os.path.isfile(STATE_PATH):
        return {"version": VERSION, "steps": {}, "vars": {}}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"version": VERSION, "steps": {}, "vars": {}}


def save_state(state: Dict[str, Any]) -> None:
    _ensure_state_dir()
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
    os.replace(tmp, STATE_PATH)


def mark_done(state: Dict[str, Any], step_id: str, **vars_: Any) -> None:
    state.setdefault("steps", {})[step_id] = {
        "done": True,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if vars_:
        state.setdefault("vars", {}).update(vars_)
    save_state(state)


def is_done(state: Dict[str, Any], step_id: str) -> bool:
    return bool(state.get("steps", {}).get(step_id, {}).get("done"))


# --- subprocess wrappers ----------------------------------------------------

def run(cmd: List[str], *, check: bool = True, capture: bool = False,
        env: Optional[Dict[str, str]] = None, input_text: Optional[str] = None,
        timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    log(f"run: {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        env=env or os.environ.copy(),
        input=input_text,
        timeout=timeout,
    )


def run_ok(cmd: List[str], **kw) -> bool:
    try:
        run(cmd, check=True, capture=True, **kw)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def http_get(url: str, *, timeout: int = HTTP_TIMEOUT) -> bytes:
    log(f"http GET {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        data = resp.read()
        # Decompress when EITHER the server sets Content-Encoding gzip OR
        # the URL ends in .gz (kodi.tv mirror does the latter -- ships
        # gzipped files as application/octet-stream with no encoding hint).
        # Also catch the case where the first two bytes are gzip magic
        # (1f 8b) regardless of headers / extension.
        looks_gzipped = (
            resp.headers.get("Content-Encoding") == "gzip"
            or url.lower().endswith(".gz")
            or data[:2] == b"\x1f\x8b"
        )
        if looks_gzipped:
            data = gzip.decompress(data)
            log(f"  decompressed gzip -> {len(data)} bytes")
        return data


def http_post(url: str, data: Dict[str, str], *,
              timeout: int = HTTP_TIMEOUT) -> Dict[str, Any]:
    payload = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    log(f"http POST {url}")
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        body = resp.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"_raw": body}


def http_get_json(url: str, *, timeout: int = HTTP_TIMEOUT) -> Dict[str, Any]:
    body = http_get(url, timeout=timeout).decode("utf-8")
    return json.loads(body)


# --- sudo cache -------------------------------------------------------------

def ensure_sudo() -> bool:
    """Refresh / acquire sudo timestamp. Returns True if available."""
    if os.geteuid() == 0:
        return True
    info("This wizard will need sudo (apt installs, VPN setup, kill-switch).")
    info("Asking for your password once -- it gets cached for the run.")
    try:
        run(["sudo", "-v"], capture=False)
        return True
    except subprocess.CalledProcessError:
        err("sudo not available; cannot continue")
        return False


def sudo_keepalive_loop_start() -> subprocess.Popen:
    """Run `sudo -v` every 60s in the background to keep the ticket alive."""
    return subprocess.Popen(
        ["bash", "-c", "while true; do sudo -n -v 2>/dev/null || exit; sleep 60; done"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# === STEPS ==================================================================

def step_disclaimer(state: Dict[str, Any]) -> bool:
    header("Step 1 / 14  ·  Legal disclaimer")
    if is_done(state, "disclaimer"):
        ok("already accepted on a prior run")
        return True
    print(open(os.path.join(REPO_ROOT, "DISCLAIMER.md"), "r").read()
          if os.path.isfile(os.path.join(REPO_ROOT, "DISCLAIMER.md"))
          else "(DISCLAIMER.md not bundled)")
    print()
    if not confirm("Type 'yes' to accept and continue", default=False):
        err("disclaimer not accepted")
        return False
    mark_done(state, "disclaimer")
    return True


def step_apt(state: Dict[str, Any]) -> bool:
    header("Step 2 / 14  ·  System packages (apt)")
    if not shutil.which("apt-get"):
        warn("not on a Debian/Ubuntu box -- skipping. Install Kodi + binary "
             "addons + mpv + wireguard-tools + nftables manually for your distro.")
        mark_done(state, "apt", apt_skipped=True)
        return True

    info("Checking which Debian packages are missing...")
    missing = []
    for pkg in DEBIAN_PKGS:
        cp = subprocess.run(["dpkg", "-l", pkg], capture_output=True, text=True)
        installed = any(l.startswith("ii") for l in cp.stdout.splitlines())
        if not installed:
            missing.append(pkg)

    if not missing:
        ok("all required packages already installed")
        mark_done(state, "apt")
        return True

    info(f"will install {len(missing)} package(s): {', '.join(missing)}")
    if not confirm("Proceed?", default=True):
        err("apt step declined")
        return False

    if not ensure_sudo():
        return False
    try:
        run(["sudo", "apt-get", "update", "-qq"])
        run(["sudo", "apt-get", "install", "-y"] + missing)
    except subprocess.CalledProcessError as exc:
        err(f"apt failed: {exc}")
        return False

    ok(f"installed {len(missing)} packages")
    mark_done(state, "apt", apt_installed=missing)
    return True


def step_kodi_userdata(state: Dict[str, Any]) -> bool:
    header("Step 3 / 14  ·  Bootstrap Kodi userdata")
    os.makedirs(KODI_USERDATA, exist_ok=True)
    os.makedirs(KODI_ADDONS, exist_ok=True)
    os.makedirs(os.path.join(KODI_USERDATA, "addon_data"), exist_ok=True)
    info(f"userdata: {KODI_USERDATA}")
    info(f"addons:   {KODI_ADDONS}")

    advanced = os.path.join(KODI_USERDATA, "advancedsettings.xml")
    if not os.path.isfile(advanced):
        with open(advanced, "w", encoding="utf-8") as fh:
            fh.write("""<advancedsettings>
  <network>
    <buffermode>1</buffermode>
    <readbufferfactor>4.0</readbufferfactor>
    <cachemembuffersize>157286400</cachemembuffersize>
  </network>
  <video>
    <ignoresecondsatstart>180</ignoresecondsatstart>
    <ignorepercentatend>8</ignorepercentatend>
  </video>
  <pvr>
    <minvideocachelevel>5</minvideocachelevel>
    <minaudiocachelevel>5</minaudiocachelevel>
  </pvr>
</advancedsettings>
""")
        ok("wrote advancedsettings.xml (buffering + pvr tuning)")
    else:
        ok("advancedsettings.xml already present, leaving alone")

    mark_done(state, "kodi_userdata")
    return True


def step_vpn(state: Dict[str, Any]) -> bool:
    header("Step 4 / 14  ·  VPN")
    if is_done(state, "vpn"):
        ok("already configured on a prior run "
           f"(provider: {state.get('vars', {}).get('vpn_provider', '?')})")
        if not confirm("Re-run VPN setup?", default=False):
            return True

    picks = menu("VPN provider", [
        "ExpressVPN (proprietary CLI)",
        "Mullvad / ProtonVPN / IVPN (WireGuard)",
        "Generic WireGuard .conf import",
        "Skip VPN (use real IP)",
    ])
    choice = picks[0]
    provider = ["expressvpn", "wg-provider", "wg-generic", "skip"][choice]
    info(f"chose: {provider}")

    if provider == "expressvpn":
        ok_ = vpn_expressvpn(state)
    elif provider == "wg-provider":
        ok_ = vpn_wg_provider(state)
    elif provider == "wg-generic":
        ok_ = vpn_wg_generic(state)
    else:
        warn("skipping VPN -- your real IP will be visible to every stream.")
        ok_ = True

    if ok_:
        verify_exit_ip()
        mark_done(state, "vpn", vpn_provider=provider)
    return ok_


def _expressvpn_status() -> Tuple[bool, bool, str]:
    """Return (installed, activated, status_text). Probes `expressvpn status`."""
    if not shutil.which("expressvpn"):
        return False, False, ""
    try:
        cp = subprocess.run(["expressvpn", "status"],
                            capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True, False, ""
    text = (cp.stdout + cp.stderr).lower()
    activated = ("not activated" not in text and
                 "please activate" not in text and
                 "expressvpn activate" not in text)
    return True, activated, cp.stdout.strip()


def vpn_expressvpn(state: Dict[str, Any]) -> bool:
    installed, activated, status_text = _expressvpn_status()

    # --- install (only if missing) -----------------------------------------
    if not installed:
        info("ExpressVPN CLI not installed.")
        info("ExpressVPN's download page is JS-rendered behind a login, so")
        info("there's no public URL we can fetch. Download the .deb yourself:")
        info("")
        info("  1. Log in at https://www.expressvpn.com/setup")
        info("  2. Linux tab > Ubuntu 64-bit > Download")
        info("  3. Note where it landed (probably ~/Downloads)")
        info("")
        while True:
            path = ask("Local path to the downloaded .deb (or 'skip' to skip VPN)")
            if path.lower() == "skip":
                warn("ExpressVPN install skipped")
                return False
            path = os.path.expanduser(path)
            if os.path.isfile(path) and path.endswith(".deb"):
                break
            err(f"not a .deb file: {path}")

        if not ensure_sudo():
            return False
        info(f"installing {os.path.basename(path)}...")
        # dpkg -i may complain about missing deps; the apt-get install -f
        # right after pulls them in. Both can produce non-zero exits during
        # normal operation; we only fail if `expressvpn` isn't on PATH after.
        subprocess.run(["sudo", "dpkg", "-i", path],
                       check=False, capture_output=True)
        subprocess.run(["sudo", "apt-get", "install", "-f", "-y"],
                       check=False, capture_output=True)
        if not shutil.which("expressvpn"):
            err("install completed but `expressvpn` not on PATH")
            err("Try: sudo apt-get install -f -y    then re-run `./badtv repair vpn`")
            return False
        ok("ExpressVPN CLI installed")
        installed, activated, status_text = _expressvpn_status()
    else:
        ok("ExpressVPN CLI already installed")

    # --- activate (only if needed) -----------------------------------------
    if not activated:
        info("ExpressVPN is not activated.")
        info("Get your activation code at: https://www.expressvpn.com/setup")
        info("")
        info("We'll hand the terminal to `expressvpn activate` -- type your")
        info("code when it prompts, then answer 'n' to the two diagnostic")
        info("questions. Returns control here when done.")
        info("")
        ask("press Enter when ready", default="")
        try:
            subprocess.run(["expressvpn", "activate"], check=True)
        except subprocess.CalledProcessError as exc:
            err(f"activation failed (exit {exc.returncode}); "
                "you can try `expressvpn activate` by hand then re-run "
                "`./badtv repair vpn`")
            return False
        ok("activated")
    else:
        ok("ExpressVPN already activated")

    # --- connect (only if not already connected) ---------------------------
    _, _, status_text = _expressvpn_status()
    if "connected to" in status_text.lower():
        location = status_text.split("Connected to", 1)[-1].strip().splitlines()[0]
        ok(f"already connected: {location}")
    else:
        info("Connecting to the 'smart' location...")
        try:
            run(["expressvpn", "connect", "smart"], check=True, timeout=60)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            err(f"connect failed: {exc}")
            err("Try: `expressvpn connect smart` by hand, then "
                "`./badtv repair vpn` to verify")
            return False
        ok("ExpressVPN connected")
    return True


def vpn_wg_provider(state: Dict[str, Any]) -> bool:
    info("This path uses our WireGuard helper + nftables kill-switch.")
    info("Get a WireGuard .conf from your provider's dashboard:")
    info("  Mullvad:   https://mullvad.net/account/wireguard-config")
    info("  ProtonVPN: https://account.protonvpn.com/downloads (WireGuard tab)")
    info("  IVPN:      https://www.ivpn.net/account/wireguard")
    path = ask("path to the .conf file you downloaded")
    return _run_wg_setup(path)


def vpn_wg_generic(state: Dict[str, Any]) -> bool:
    path = ask("path to your WireGuard .conf")
    return _run_wg_setup(path)


def _run_wg_setup(path: str) -> bool:
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        err(f"not found: {path}")
        return False
    helper = os.path.join(REPO_ROOT, "tools", "network", "setup-wireguard.sh")
    if not os.path.isfile(helper):
        err(f"helper missing: {helper}")
        return False
    try:
        run(["sudo", "bash", helper, path], check=True)
    except subprocess.CalledProcessError as exc:
        err(f"WireGuard setup failed: {exc}")
        return False
    ok("WireGuard tunnel up + kill-switch installed")
    return True


def verify_exit_ip() -> None:
    info("Verifying public IP...")
    helper = os.path.join(REPO_ROOT, "tools", "network", "vpn-status.sh")
    if os.path.isfile(helper):
        run([helper], check=False)
    else:
        warn("vpn-status.sh not present, skipping verification")


def step_install_repo_addon(state: Dict[str, Any]) -> bool:
    """Install the B@Dtv repository addon and wizard addon from local zips."""
    header("Step 5 / 14  ·  B@Dtv addons (repository + wizard)")
    # Auto-discover the current built zips so we don't have to chase
    # version-string bumps in two places.
    dist = os.path.join(REPO_ROOT, "dist")
    candidates = []
    for prefix in ("repository.badtv-", "script.badtv.wizard-"):
        matches = sorted(p for p in os.listdir(dist)
                         if p.startswith(prefix) and p.endswith(".zip")) \
                  if os.path.isdir(dist) else []
        if matches:
            candidates.append(matches[-1])  # newest by string sort
    if len(candidates) < 2:
        warn("repository / wizard zips not built locally; running `make repo`")
        try:
            run(["make", "-C", REPO_ROOT, "repo"], check=True)
        except subprocess.CalledProcessError:
            err("make repo failed")
            return False
        candidates = []
        for prefix in ("repository.badtv-", "script.badtv.wizard-"):
            matches = sorted(p for p in os.listdir(dist)
                             if p.startswith(prefix) and p.endswith(".zip"))
            if matches:
                candidates.append(matches[-1])

    for name in candidates:
        local = os.path.join(dist, name)
        info(f"extracting {name} -> {KODI_ADDONS}")
        with zipfile.ZipFile(local) as zf:
            zf.extractall(KODI_ADDONS)
    ok("B@Dtv repository + wizard addons installed")
    mark_done(state, "badtv_addons")
    return True


def step_install_official(state: Dict[str, Any]) -> bool:
    """Download Kodi-official addons directly from mirrors.kodi.tv."""
    header("Step 6 / 14  ·  Kodi-official addons")

    # If the addons already exist on disk from a prior run, the only thing
    # left to do is make sure they're enabled in Addons33.db. Skip the
    # network fetch entirely when nothing needs installing -- this keeps
    # `./badtv repair install_official` working in the field even if
    # mirrors.kodi.tv is unreachable.
    missing = [a for a in OFFICIAL_ADDONS
               if not os.path.isdir(os.path.join(KODI_ADDONS, a))]
    if not missing:
        ok("all official addons already present on disk")
        _kodi_db_enable(list(OFFICIAL_ADDONS) + ["service.iptv.manager"])
        mark_done(state, "install_official")
        return True

    info("Fetching addons.xml.gz from mirrors.kodi.tv ...")
    try:
        body = http_get(f"{KODI_MIRROR}/addons.xml.gz", timeout=60)
    except Exception as exc:
        err(f"could not fetch addons.xml.gz: {exc}")
        # Best-effort: still flip enable on whatever IS on disk.
        present = [a for a in OFFICIAL_ADDONS
                   if os.path.isdir(os.path.join(KODI_ADDONS, a))]
        if present:
            _kodi_db_enable(present + ["service.iptv.manager"])
            warn(f"enabled the {len(present)} addons that were already on disk")
        return False
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        err(f"could not parse addons.xml: {exc}")
        return False
    versions: Dict[str, str] = {}
    for addon in root.findall("addon"):
        aid = addon.get("id")
        ver = addon.get("version")
        if aid and ver:
            versions[aid] = ver
    info(f"mirror lists {len(versions)} addons")

    # DEBIAN_PROVIDED: module-level constant -- addons shipped as apt
    # packages whose metadata lives under /usr/share/kodi instead of
    # ~/.kodi/addons. Skip during dep resolution to avoid spurious 404s.
    failed = []
    for aid in OFFICIAL_ADDONS:
        if aid not in versions:
            warn(f"{aid}: not in nexus mirror, skipping")
            continue
        if os.path.isdir(os.path.join(KODI_ADDONS, aid)):
            ok(f"{aid}: already installed")
            continue
        ver = versions[aid]
        url = f"{KODI_MIRROR}/{aid}/{aid}-{ver}.zip"
        info(f"downloading {aid} v{ver}")
        try:
            data = http_get(url, timeout=120)
        except Exception as exc:
            err(f"{aid}: download failed: {exc}")
            failed.append(aid)
            continue
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(KODI_ADDONS)
        ok(f"{aid} v{ver} installed")

    # Best-effort: install transitive dependencies. Resolve required imports
    # from each addon's addon.xml; install ones we don't already have.
    info("Resolving dependencies...")
    pending = set(OFFICIAL_ADDONS)
    seen = set()
    while pending:
        aid = pending.pop()
        if aid in seen:
            continue
        seen.add(aid)
        addon_xml = os.path.join(KODI_ADDONS, aid, "addon.xml")
        if not os.path.isfile(addon_xml):
            continue
        try:
            r = ET.parse(addon_xml).getroot()
        except ET.ParseError:
            continue
        for imp in r.findall(".//requires/import"):
            dep = imp.get("addon")
            if not dep or dep.startswith("xbmc."):
                continue
            if dep in DEBIAN_PROVIDED:
                # Installed via apt in Step 2; metadata lives under
                # /usr/share/kodi/addons, not ~/.kodi/addons.
                continue
            if os.path.isdir(os.path.join(KODI_ADDONS, dep)):
                continue
            if dep not in versions:
                continue
            ver = versions[dep]
            url = f"{KODI_MIRROR}/{dep}/{dep}-{ver}.zip"
            try:
                data = http_get(url, timeout=120)
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    zf.extractall(KODI_ADDONS)
                ok(f"dep {dep} v{ver} installed")
                pending.add(dep)
            except Exception as exc:
                warn(f"dep {dep} failed: {exc}")

    if failed:
        warn(f"failed: {', '.join(failed)} (re-run `./badtv repair install_official` later)")

    # Pre-enable everything in OFFICIAL_ADDONS + the deps we just installed.
    # Same logic as step_grey_addons: Kodi 19+ disables third-party-repo
    # additions by default, and even Kodi-official ones occasionally land
    # in the installed table with disabledReason=1 because they weren't
    # part of the initial first-launch scan.
    _kodi_db_enable(sorted(set(OFFICIAL_ADDONS) | seen))

    mark_done(state, "install_official")
    return True


# --- generic Kodi-repo chain installer --------------------------------------
#
# Each scraper repo we ship serves a single "wrapper" zip at its github.io
# root. That wrapper extracts to ~/.kodi/addons/repository.<something>/, whose
# addon.xml lists version-keyed addons.xml URLs for the actual addon zips.
# This function automates the whole chain so the user never sees
# Files-Manager-add-source > Install-from-zip > Install-from-repository.

def _kodi_major_tag() -> str:
    """Return a tag matching the <dir minversion=.../> blocks in repo
    addon.xmls. 19=matrix, 20=nexus, 21=omega, 22=piers."""
    try:
        cp = subprocess.run(["kodi", "--version"], capture_output=True,
                            text=True, timeout=5)
        m = re.search(r'\b(\d+)\.\d+', cp.stdout)
        if m:
            major = int(m.group(1))
            return {19: "matrix", 20: "nexus", 21: "omega",
                    22: "piers"}.get(major, "nexus")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return "nexus"  # safest default for Ubuntu LTS Kodi


def _all_dir_blocks(repo_addon_xml: ET.Element, major_tag: str) -> List[Tuple[str, str]]:
    """Walk every <dir minversion/maxversion> block in the repo addon.xml
    and return EACH one that matches this Kodi major. Many repos ship
    multiple mirrors (e.g. The Crew lists 4 fallback URLs); we keep all
    matches so the dep resolver can try them in order until one has the
    addon we want."""
    target = {"matrix": (19, 0, 0), "nexus": (20, 0, 0),
              "omega":  (21, 0, 0), "piers": (22, 0, 0)}.get(major_tag, (20, 0, 0))

    def _parse(v: str) -> Tuple[int, int, int]:
        try:
            parts = (v + ".0.0.0").split(".")[:3]
            return tuple(int(re.match(r"\d+", p).group(0)) for p in parts)  # type: ignore[return-value]
        except Exception:
            return (0, 0, 0)

    out: List[Tuple[str, str]] = []
    for d in repo_addon_xml.findall(".//extension/dir"):
        minv = _parse(d.get("minversion", "0.0.0"))
        maxv_raw = d.get("maxversion")
        maxv = _parse(maxv_raw) if maxv_raw else (99, 99, 99)
        if minv <= target <= maxv:
            info_el = d.find("info")
            data_el = d.find("datadir")
            if info_el is not None and data_el is not None:
                out.append((info_el.text or "", data_el.text or ""))
    # Some repos (slyguy) use a flat <info>/<datadir> directly under
    # <extension>, no <dir> wrapper. Fall back to those.
    if not out:
        info_el = repo_addon_xml.find(".//extension/info")
        data_el = repo_addon_xml.find(".//extension/datadir")
        if info_el is not None and data_el is not None:
            out.append((info_el.text or "", data_el.text or ""))
    return out


def _harvest_repo_addons_xml(info_url: str) -> Dict[str, str]:
    """Fetch and parse a repo's addons.xml. Returns {addon_id: version}."""
    try:
        body = http_get(info_url, timeout=60)
        root = ET.fromstring(body)
    except Exception as exc:
        warn(f"  could not fetch {info_url}: {exc}")
        return {}
    return {a.get("id"): a.get("version") for a in root.findall("addon")
            if a.get("id") and a.get("version")}


def _zip_url(datadir: str, aid: str, ver: str) -> str:
    """Build the canonical zip URL from a repo's datadir.
    Kodi convention: <datadir>/<addon_id>/<addon_id>-<version>.zip."""
    base = datadir if datadir.endswith("/") else datadir + "/"
    return f"{base}{aid}/{aid}-{ver}.zip"


def _install_addon_zip(aid: str, ver: str, url: str) -> bool:
    """Download and extract a single addon zip into KODI_ADDONS."""
    try:
        data = http_get(url, timeout=180)
    except Exception as exc:
        warn(f"  {aid} v{ver}: download failed ({exc})")
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(KODI_ADDONS)
    except zipfile.BadZipFile:
        warn(f"  {aid} v{ver}: not a valid zip")
        return False
    ok(f"  installed {aid} v{ver}")
    return True


def _resolve_and_install(plugin_id: str,
                         catalogs: List[Tuple[Dict[str, str], str]],
                         kodi_mirror_versions: Dict[str, str],
                         visited: Optional[set] = None) -> List[str]:
    """Install plugin_id and walk its requires graph.

    catalogs is an ordered list of (id->version, datadir) tuples to search
    for each dep. Falls back to mirrors.kodi.tv if not found in any catalog.
    Returns a list of failures (empty == success)."""
    if visited is None:
        visited = set()
    failures: List[str] = []
    if plugin_id in visited:
        return failures
    visited.add(plugin_id)
    if plugin_id.startswith("xbmc.") or plugin_id in DEBIAN_PROVIDED:
        return failures
    addon_dir = os.path.join(KODI_ADDONS, plugin_id)
    if os.path.isdir(addon_dir):
        ok(f"  {plugin_id}: already installed")
    else:
        # Find a catalog that has it.
        found = False
        for vers, datadir in catalogs:
            if plugin_id in vers:
                ver = vers[plugin_id]
                if _install_addon_zip(plugin_id, ver,
                                      _zip_url(datadir, plugin_id, ver)):
                    found = True
                break
        if not found and plugin_id in kodi_mirror_versions:
            ver = kodi_mirror_versions[plugin_id]
            url = f"{KODI_MIRROR}/{plugin_id}/{plugin_id}-{ver}.zip"
            found = _install_addon_zip(plugin_id, ver, url)
        if not found:
            warn(f"  {plugin_id}: not in any known catalog -- "
                 "leaving for the user to install by hand")
            failures.append(plugin_id)
            return failures

    # Recurse into requires.
    addon_xml = os.path.join(KODI_ADDONS, plugin_id, "addon.xml")
    if not os.path.isfile(addon_xml):
        return failures
    try:
        root = ET.parse(addon_xml).getroot()
    except ET.ParseError:
        return failures
    for imp in root.findall(".//requires/import"):
        dep = imp.get("addon")
        if not dep:
            continue
        if imp.get("optional", "false").lower() == "true":
            # Skip optional deps -- many "optional" deps in scraper addons
            # are alternate URL resolvers we don't need.
            continue
        failures.extend(_resolve_and_install(
            dep, catalogs, kodi_mirror_versions, visited))
    return failures


def step_grey_addons(state: Dict[str, Any]) -> bool:
    """Install the grey-area scraper stack (Umbrella, The Crew, Seren, POV,
    CocoScrapers, ResolveURL) automatically. This is what makes Real-Debrid
    actually useful inside Kodi -- without these, the in-Kodi browser is
    limited to whatever the official mirror serves."""
    header("Step 7 / 14  ·  Grey-area scrapers (Umbrella / Crew / Seren / POV)")

    major_tag = _kodi_major_tag()
    info(f"Kodi major: {major_tag}")

    # Pull Kodi-mirror catalog once for dep fallback.
    info("Fetching Kodi mirror catalog for dep resolution...")
    try:
        body = http_get(f"{KODI_MIRROR}/addons.xml.gz", timeout=60)
        mirror_root = ET.fromstring(body)
        mirror_versions = {a.get("id"): a.get("version")
                           for a in mirror_root.findall("addon")
                           if a.get("id") and a.get("version")}
        info(f"  mirror has {len(mirror_versions)} addons")
    except Exception as exc:
        warn(f"  could not fetch mirror catalog: {exc} -- deps may fail")
        mirror_versions = {}

    # Resolve each grey repo's addons.xml + datadir, harvest the catalog.
    catalogs: List[Tuple[Dict[str, str], str]] = []
    for repo in GREY_REPOS:
        name = repo["name"]
        section(f"Repo: {name}")

        info_url: Optional[str]
        datadir: Optional[str]

        if repo.get("repo_zip_url"):
            # Wrapper zip pattern: download, extract, parse inner addon.xml.
            try:
                info(f"  downloading wrapper zip: {repo['repo_zip_url']}")
                data = http_get(repo["repo_zip_url"], timeout=60)
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    zf.extractall(KODI_ADDONS)
                    # Find the extracted repository.<x> dir.
                    repo_dir_name = zf.namelist()[0].split("/")[0]
            except Exception as exc:
                warn(f"  {name}: wrapper download failed: {exc}")
                continue
            wrapper_xml = os.path.join(KODI_ADDONS, repo_dir_name, "addon.xml")
            if not os.path.isfile(wrapper_xml):
                warn(f"  {name}: wrapper has no addon.xml at {wrapper_xml}")
                continue
            try:
                wrapper = ET.parse(wrapper_xml).getroot()
            except ET.ParseError as exc:
                warn(f"  {name}: bad wrapper addon.xml: {exc}")
                continue
            mirrors = _all_dir_blocks(wrapper, major_tag)
            if not mirrors:
                warn(f"  {name}: no <dir> block matched Kodi {major_tag}")
                continue
            ok(f"  wrapper installed; trying {len(mirrors)} mirror(s)")
        else:
            # Direct addons.xml mode -- no wrapper. Used for ResolveURL via
            # Gujal00/smrzips (no Kodi-repository addon, just the catalog).
            mirrors = [(repo["addons_xml"].get(major_tag)
                        or repo["addons_xml"].get("nexus"),
                        repo["datadir"])]

        # Try every mirror -- merge all reachable catalogs so a plugin
        # missing from the first URL can still be found via a fallback.
        for info_url, datadir in mirrors:
            vers = _harvest_repo_addons_xml(info_url)
            if vers:
                info(f"    +{len(vers)} addons from {info_url}")
                catalogs.append((vers, datadir))
        if not any(info_url for info_url, _ in mirrors):
            warn(f"  {name}: no mirror produced a usable catalog")

    # Install the named plugins from each repo, sharing all harvested
    # catalogs for cross-repo dep resolution.
    overall_failures: List[str] = []
    visited: set = set()
    for repo in GREY_REPOS:
        for plugin_id in repo["plugins"]:
            section(f"Installing {plugin_id}")
            failures = _resolve_and_install(
                plugin_id, catalogs, mirror_versions, visited)
            overall_failures.extend(failures)

    if overall_failures:
        warn(f"unresolved addons: {', '.join(sorted(set(overall_failures)))}")
        warn("re-run `./badtv repair grey_addons` if upstream comes back, "
             "or install by hand from the in-Kodi wizard.")
    else:
        ok("grey-area scraper stack installed in full")

    # Pre-enable everything we just dropped on disk. Kodi defaults
    # third-party (non-official-repo) addons to disabled with
    # disabledReason=1 ("user has not yet allowed unknown sources / this
    # particular addon"). Pre-seeding Addons33.db with enabled=1 means
    # the user opens Kodi and the scrapers are already live -- no
    # twenty-clicks-into-Settings approval round.
    to_enable = list(visited)  # all plugins + deps we just installed
    for repo in GREY_REPOS:
        to_enable.extend(repo["plugins"])
    # Wrapper repos: each one's directory name often != its addon id
    # (e.g. dir `repository.umbrellaplug.github.io` declares
    # `id="repository.umbrella"`). Read every repo dir's addon.xml to
    # get the canonical id Kodi will index it under.
    for dirname in os.listdir(KODI_ADDONS):
        if not dirname.startswith("repository."):
            continue
        addon_xml = os.path.join(KODI_ADDONS, dirname, "addon.xml")
        if not os.path.isfile(addon_xml):
            continue
        try:
            aid = ET.parse(addon_xml).getroot().get("id")
        except ET.ParseError:
            continue
        if aid:
            to_enable.append(aid)
    _kodi_db_enable(sorted(set(to_enable)))

    # Post-install addon patches. Seren 2.1.9 hard-codes a Kodi -> MyVideos
    # DB-version map that stops at Kodi 19; on Kodi 20+ it raises
    # KeyError("Unsupported kodi version") on every startup, which kills
    # the addon's service. Patch its globals.py to know about 20/21/22+.
    _patch_seren_kodi_compat()

    # Wire CocoScrapers into Umbrella, POV, and The Crew as their external
    # source provider. Without this, the addons ship with internal
    # scraping disabled AND no external provider configured, so every
    # `play_Item` returns "no sources" and Kodi logs the title as
    # "unplayable." This is the one missing puzzle-piece that turns
    # "scrapers are installed" into "scrapers actually scrape."
    _wire_cocoscrapers_into_scrapers()

    mark_done(state, "grey_addons", grey_failures=sorted(set(overall_failures)))
    return True


def _wire_cocoscrapers_into_scrapers() -> None:
    """Set each scraper's "external provider" to CocoScrapers and enable
    cross-cutting source aggregation. Idempotent."""
    # Umbrella + POV use the same setting names.
    for addon in ("plugin.video.umbrella", "plugin.video.pov"):
        if os.path.isdir(os.path.join(KODI_ADDONS, addon)):
            _patch_addon_settings(addon, {
                "provider.external.enabled":    "true",
                "external_provider.name":       "cocoscrapers",  # lowercase: Umbrella does `import_module(name)` and the python package is `cocoscrapers`
                "external_provider.module":     "script.module.cocoscrapers",
                "umbrella.externalWarning":     "false",       # umbrella-only no-op for pov
                "externalProvider.notification": "false",      # pov-only no-op for umbrella
            })
            ok(f"  {addon}: external provider = CocoScrapers")
    # The Crew has its own knob.
    if os.path.isdir(os.path.join(KODI_ADDONS, "plugin.video.thecrew")):
        _patch_addon_settings("plugin.video.thecrew", {
            "cocoscrapers.enabled": "true",
        })
        ok("  plugin.video.thecrew: cocoscrapers.enabled = true")


def _patch_seren_kodi_compat() -> None:
    """Seren 2.1.9 (the version on nixgates as of 2026-05) doesn't know
    about Kodi 20+ DB schemas. Append the missing rows so the addon
    actually loads. Idempotent: skips if already patched."""
    path = os.path.join(KODI_ADDONS, "plugin.video.seren",
                        "resources", "lib", "modules", "globals.py")
    if not os.path.isfile(path):
        return
    body = open(path, encoding="utf-8").read()
    needle = ('        elif self.KODI_VERSION == 19:\n'
              '            return "119"\n\n'
              '        raise KeyError("Unsupported kodi version")')
    if 'self.KODI_VERSION == 20' in body:
        info("  seren: kodi-20 patch already present")
        return
    if needle not in body:
        info("  seren: patch needle not found -- upstream may have changed format")
        return
    replacement = ('        elif self.KODI_VERSION == 19:\n'
                   '            return "119"\n'
                   '        elif self.KODI_VERSION == 20:\n'
                   '            return "121"\n'
                   '        elif self.KODI_VERSION == 21:\n'
                   '            return "131"\n'
                   '        elif self.KODI_VERSION >= 22:\n'
                   '            return "131"  # future-default; bump when Piers ships\n\n'
                   '        raise KeyError("Unsupported kodi version")')
    open(path, "w", encoding="utf-8").write(body.replace(needle, replacement))
    ok("  seren: patched globals.py to recognise Kodi 20 (MyVideos121) + 21 + 22+")


def _kodi_db_enable(addon_ids: List[str]) -> None:
    """Force-enable the given addon IDs in Kodi's Addons33.db so they're
    live on first launch instead of waiting in disabled-purgatory."""
    if not addon_ids:
        return
    db = os.path.join(KODI_USERDATA, "Database", "Addons33.db")
    os.makedirs(os.path.dirname(db), exist_ok=True)
    if _is_kodi_running():
        warn("Kodi is running -- can't safely patch Addons33.db. "
             "Close Kodi and re-run `./badtv repair grey_addons`.")
        return
    try:
        import sqlite3
    except ImportError:
        warn("Python sqlite3 unavailable; can't pre-enable addons")
        return
    info(f"  pre-enabling {len(addon_ids)} addons in Kodi DB ...")
    con = sqlite3.connect(db)
    try:
        cur = con.cursor()
        # Ensure schema exists (fresh-install case: Kodi hasn't been launched yet).
        cur.execute("""CREATE TABLE IF NOT EXISTS installed (
            id INTEGER PRIMARY KEY,
            addonID TEXT UNIQUE,
            enabled BOOLEAN,
            installDate TEXT,
            lastUpdated TEXT,
            lastUsed TEXT,
            origin TEXT NOT NULL DEFAULT '',
            disabledReason INTEGER NOT NULL DEFAULT 0)""")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for aid in addon_ids:
            cur.execute("""INSERT INTO installed
                (addonID, enabled, installDate, lastUpdated, origin, disabledReason)
                VALUES (?, 1, ?, ?, '', 0)
                ON CONFLICT(addonID) DO UPDATE SET
                    enabled=1, disabledReason=0,
                    lastUpdated=excluded.lastUpdated""",
                (aid, now, now))
        con.commit()
        ok(f"  enabled {len(addon_ids)} addons in Addons33.db")
    finally:
        con.close()


# --- floor2 NAS mount (SSHFS) + Elementum torrent stack ---------------------
#
# Defaults match the canonical TheClawFirm floor2 layout: ZFS pool `datapool`
# with `/datapool/media/{movies,tv,music,downloads}`. Override via env
# (FLOOR2_HOST, FLOOR2_USER, FLOOR2_REMOTE_PATH, FLOOR2_MOUNTPOINT) or by
# editing config/badtv.conf before running setup.

FLOOR2_DEFAULT_HOST = "192.168.1.206"
FLOOR2_DEFAULT_USER = "floor2"
FLOOR2_DEFAULT_REMOTE = "/datapool/media"
FLOOR2_DEFAULT_MOUNTPOINT = os.path.expanduser("~/floor2-media")
FLOOR2_KEY = os.path.expanduser("~/.ssh/floor2_mount")
FLOOR2_SSH_ALIAS = "floor2-mount"

ELEMENTUM_REPO_URL    = "https://github.com/ElementumOrg/repository.elementumorg/releases/download/v0.0.7/repository.elementumorg-0.0.7.zip"
ELEMENTUM_BURST_URL   = "https://github.com/elgatito/script.elementum.burst/releases/download/v0.0.98/script.elementum.burst-0.0.98.zip"
# Plugin URL is arch-specific; resolved at install time.
ELEMENTUM_PLUGIN_BASE = "https://github.com/elgatito/plugin.video.elementum/releases/download/v0.1.113/plugin.video.elementum-0.1.113"

# Jacktook -- newer torrent/meta-aggregator using Stremio's Comet /
# MediaFusion / Torrentio addons (cloud-hosted indexers that pre-aggregate
# from everywhere). Plays much better with RD than scraping individual
# torrent sites does -- works even when 1337x / yts / torrentgalaxy are
# DPI-blocked on the user's network.
JACKTOOK_REPO_URL    = "https://sam-max.github.io/repository.jacktook/repository.jacktook-0.0.5.zip"
JACKTOOK_DATADIR     = "https://raw.githubusercontent.com/Sam-Max/repository.jacktook/master/repo/zips"
JACKTOOK_PLUGINS     = [
    ("plugin.video.jacktook", "1.13.0"),
    ("script.jacktook.burst", "0.0.92"),
]


def step_floor2_mount(state: Dict[str, Any]) -> bool:
    """Mount the floor2 ZFS media dataset over SSHFS so Elementum can write
    downloads there AND Kodi can scan its library scrapers against the
    same paths. Idempotent. Sets up:
      - dedicated SSH key (~/.ssh/floor2_mount) authorized on floor2
      - SSH config alias `floor2-mount`
      - systemd --user unit for auto-mount on login
      - immediate sshfs mount if not already mounted
      - Kodi sources.xml entries for movies / tv / downloads / music"""
    header("Step 8 / 14  ·  floor2 NAS mount (SSHFS)")

    host    = os.environ.get("FLOOR2_HOST", FLOOR2_DEFAULT_HOST)
    user    = os.environ.get("FLOOR2_USER", FLOOR2_DEFAULT_USER)
    remote  = os.environ.get("FLOOR2_REMOTE_PATH", FLOOR2_DEFAULT_REMOTE)
    mnt     = os.environ.get("FLOOR2_MOUNTPOINT", FLOOR2_DEFAULT_MOUNTPOINT)

    info(f"floor2: {user}@{host}:{remote}  ->  {mnt}")

    # 1. sshfs installed?
    if not shutil.which("sshfs"):
        info("installing sshfs (apt)...")
        if not ensure_sudo():
            warn("can't install sshfs without sudo; skipping mount")
            return True
        try:
            run(["sudo", "apt-get", "install", "-y", "sshfs"], capture=True)
        except subprocess.CalledProcessError as exc:
            warn(f"sshfs install failed: {exc}; skipping")
            return True
        ok("sshfs installed")
    else:
        ok("sshfs already installed")

    # 2. dedicated ed25519 keypair for the mount
    if not os.path.isfile(FLOOR2_KEY):
        info("generating mount keypair ~/.ssh/floor2_mount")
        run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C",
             f"kodi-mount@{socket.gethostname()}", "-f", FLOOR2_KEY, "-q"])
    else:
        ok("mount keypair already exists")
    pub_path = FLOOR2_KEY + ".pub"
    pub_key  = open(pub_path).read().strip()

    # 3. authorize key on floor2 (assumes user already has SOME working ssh to floor2)
    info(f"authorizing public key on {user}@{host}...")
    auth_cmd = (
        f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
        f"chmod 600 ~/.ssh/authorized_keys && grep -qF '{pub_key}' "
        f"~/.ssh/authorized_keys || echo '{pub_key}' >> ~/.ssh/authorized_keys"
    )
    try:
        run(["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
             f"{user}@{host}", auth_cmd], capture=True)
        ok("public key authorized on floor2")
    except subprocess.CalledProcessError as exc:
        warn(f"could not authorize key on {host}: {exc}")
        warn("manually copy ~/.ssh/floor2_mount.pub to "
             f"{user}@{host}:~/.ssh/authorized_keys, then re-run "
             "`./badtv repair floor2`")
        return True   # non-blocking

    # 4. SSH config rule for the dedicated key
    _patch_ssh_config(host, user)
    ok(f"ssh config alias: {FLOOR2_SSH_ALIAS} -> {user}@{host}")

    # 5. systemd --user unit for auto-mount
    _install_floor2_systemd_unit(mnt, remote)
    ok("systemd --user unit installed: floor2-media.service")

    # 6. mount NOW if not already mounted
    if not os.path.ismount(mnt):
        os.makedirs(mnt, exist_ok=True)
        try:
            run([
                "sshfs", f"{FLOOR2_SSH_ALIAS}:{remote}", mnt,
                "-o", "reconnect",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "follow_symlinks",
                "-o", "idmap=user",
                "-o", "cache=yes",
                "-o", "kernel_cache",
                "-o", "compression=no",
                "-o", "auto_cache",
                "-o", f"IdentityFile={FLOOR2_KEY}",
                "-o", "BatchMode=yes",
            ], capture=True)
            ok(f"mounted: {mnt}")
        except subprocess.CalledProcessError as exc:
            warn(f"mount failed: {exc.stderr[:200] if hasattr(exc, 'stderr') and exc.stderr else exc}")
            warn("re-run `./badtv repair floor2` once floor2 is reachable")
            return True
    else:
        ok(f"already mounted: {mnt}")

    # 7. write-test
    test_path = os.path.join(mnt, "downloads", ".badtv-write-test")
    try:
        os.makedirs(os.path.dirname(test_path), exist_ok=True)
        with open(test_path, "w") as fh:
            fh.write("ok")
        os.remove(test_path)
        ok("write test passed")
    except Exception as exc:
        warn(f"write test failed: {exc} -- check permissions on remote dataset")

    # 8. add Kodi sources.xml entries pointing at the mount
    _patch_kodi_sources_xml(mnt)
    ok("Kodi sources.xml updated (Movies / TV Shows / Downloads / Music)")

    mark_done(state, "floor2", floor2_host=host, floor2_mount=mnt)
    return True


def _patch_ssh_config(host: str, user: str) -> None:
    """Add a Host floor2-mount alias to ~/.ssh/config if missing."""
    cfg = os.path.expanduser("~/.ssh/config")
    rule = (
        f"\nHost {FLOOR2_SSH_ALIAS}\n"
        f"  HostName {host}\n"
        f"  User {user}\n"
        f"  IdentityFile {FLOOR2_KEY}\n"
        f"  IdentitiesOnly yes\n"
        f"  ServerAliveInterval 30\n"
        f"  ServerAliveCountMax 3\n"
    )
    body = open(cfg).read() if os.path.isfile(cfg) else ""
    if f"Host {FLOOR2_SSH_ALIAS}" in body:
        return
    os.makedirs(os.path.dirname(cfg), exist_ok=True)
    with open(cfg, "a") as fh:
        fh.write(rule)
    os.chmod(cfg, 0o600)


def _install_floor2_systemd_unit(mnt: str, remote: str) -> None:
    """Drop a systemd --user unit so the SSHFS mount auto-reconnects on
    login + restarts on failure."""
    unit_dir = os.path.expanduser("~/.config/systemd/user")
    os.makedirs(unit_dir, exist_ok=True)
    unit = f"""[Unit]
Description=SSHFS mount of floor2:{remote} at {mnt}
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
ExecStartPre=/bin/mkdir -p {mnt}
ExecStart=/usr/bin/sshfs {FLOOR2_SSH_ALIAS}:{remote} {mnt} \\
  -o reconnect \\
  -o ServerAliveInterval=30 \\
  -o ServerAliveCountMax=3 \\
  -o follow_symlinks \\
  -o idmap=user \\
  -o cache=yes \\
  -o kernel_cache \\
  -o compression=no \\
  -o auto_cache \\
  -o IdentityFile={FLOOR2_KEY} \\
  -o BatchMode=yes
ExecStop=/usr/bin/fusermount3 -u {mnt}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
"""
    with open(os.path.join(unit_dir, "floor2-media.service"), "w") as fh:
        fh.write(unit)
    run_ok(["systemctl", "--user", "daemon-reload"])
    run_ok(["systemctl", "--user", "enable", "floor2-media.service"])


def _patch_kodi_sources_xml(mnt: str) -> None:
    """Idempotently merge floor2 movies/tv/downloads/music into Kodi's
    sources.xml, replacing any pre-existing 'floor2 *' entries or stale
    nfs:// floor2 references."""
    path = os.path.join(KODI_USERDATA, "sources.xml")
    if os.path.isfile(path):
        try:
            tree = ET.parse(path); root = tree.getroot()
        except ET.ParseError:
            root = ET.Element("sources"); tree = ET.ElementTree(root)
    else:
        root = ET.Element("sources"); tree = ET.ElementTree(root)
        for sec in ("programs", "video", "music", "pictures", "files", "games"):
            e = ET.SubElement(root, sec)
            ET.SubElement(e, "default", pathversion="1")

    # Strip every floor2-or-NFS-pointed source first
    for section_name in ("video", "music", "pictures", "files", "programs", "games"):
        sec = root.find(section_name)
        if sec is None: continue
        for s in list(sec.findall("source")):
            name = (s.findtext("name") or "").lower()
            spath = (s.findtext("path") or "").lower()
            if "floor2" in name or spath.startswith("nfs://"):
                sec.remove(s)

    desired = [
        ("video", "floor2 Movies",    os.path.join(mnt, "movies") + "/"),
        ("video", "floor2 TV Shows",  os.path.join(mnt, "tv") + "/"),
        ("video", "floor2 Downloads", os.path.join(mnt, "downloads") + "/"),
        ("music", "floor2 Music",     os.path.join(mnt, "music") + "/"),
    ]
    for section, name, src_path in desired:
        sec = root.find(section)
        if sec is None:
            sec = ET.SubElement(root, section)
            ET.SubElement(sec, "default", pathversion="1")
        s = ET.SubElement(sec, "source")
        ET.SubElement(s, "name").text = name
        ET.SubElement(s, "path", pathversion="1").text = src_path
        ET.SubElement(s, "allowsharing").text = "true"

    tree.write(path, encoding="UTF-8", xml_declaration=True)


def step_elementum(state: Dict[str, Any]) -> bool:
    """Install the Elementum torrent-streaming + download stack, point its
    download dir at the floor2 mount, and enable in Kodi DB.

    Elementum is the maintained fork of Quasar (which is dead since 2019).
    Architecture: Go-based daemon (bundled binary per platform) + Python
    plugin shell + the Burst provider that feeds it search results.
    Direct download mode writes finished files to the configured path
    (here: <floor2-mount>/downloads/) so they're SAFE on the ZFS pool
    rather than the laptop's tiny disk."""
    header("Step 9 / 14  ·  Elementum torrent stack")

    arch = _elementum_arch_tag()
    if arch is None:
        warn(f"unsupported architecture: {platform.machine()}; skipping Elementum")
        mark_done(state, "elementum", elementum="skipped_unsupported_arch")
        return True
    info(f"arch: {arch}")

    plugin_url = f"{ELEMENTUM_PLUGIN_BASE}.{arch}.zip"
    bundle = [
        ("repository.elementumorg", ELEMENTUM_REPO_URL),
        ("plugin.video.elementum",  plugin_url),
        ("script.elementum.burst",  ELEMENTUM_BURST_URL),
    ]
    failed = []
    for aid, url in bundle:
        if os.path.isdir(os.path.join(KODI_ADDONS, aid)):
            ok(f"{aid}: already installed")
            continue
        info(f"downloading {aid}")
        try:
            data = http_get(url, timeout=180)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extractall(KODI_ADDONS)
            ok(f"{aid} installed")
        except Exception as exc:
            warn(f"{aid} failed: {exc}")
            failed.append(aid)

    if "plugin.video.elementum" in failed:
        err("core Elementum plugin missing -- aborting")
        return True

    # Configure: download path goes to floor2 mount/downloads
    mnt = state.get("vars", {}).get("floor2_mount", FLOOR2_DEFAULT_MOUNTPOINT)
    dl  = os.path.join(mnt, "downloads")
    lib = mnt
    info(f"download_path: {dl}")
    info(f"library_path:  {lib}")

    _patch_addon_settings("plugin.video.elementum", {
        "download_storage":    "0",          # 0 = file (disk), 1 = memory
        "download_path":       dl,
        "library_path":        lib,
        "library_resume_jobs": "true",
        "background_handling": "true",
        "move_files":          "true",
        "completed_move_path": dl,
        "keep_files":          "false",
        "keep_originals":      "false",
        "download_file_strategy": "0",       # 0 = all files
        "first_run":           "false",
    })

    _kodi_db_enable([aid for aid, _ in bundle])
    ok("Elementum stack installed, configured, and enabled")

    # Also install Jacktook — same step makes sense because both are
    # torrent-first addons and share the "needs RD configured" story.
    # CocoScrapers/Burst-style scraping struggles when the user's network
    # blocks the legacy torrent indexers (1337x, yts, torrentgalaxy all
    # 403/blocked on Spectrum + most VPN exits). Jacktook talks to Stremio
    # meta-aggregators (Comet, MediaFusion) which are reliably reachable
    # and return RD-cached results.
    _install_jacktook(state)
    _kodi_db_enable(["repository.jacktook"] +
                    [aid for aid, _ in JACKTOOK_PLUGINS])

    mark_done(state, "elementum",
              elementum_arch=arch,
              elementum_download_path=dl)
    return True


def _install_jacktook(state: Dict[str, Any]) -> None:
    """Install Jacktook (repo + plugin + Burst) and pre-enable its
    Burst + external-scraper + Stremio search modes. Also pushes RD
    credentials into Jacktook's settings.xml (it uses its own key set:
    real_debrid_token, real_debrid_refresh_token, real_debrid_enabled,
    real_debrid_user)."""
    info("installing Jacktook (Stremio-style meta-aggregator)...")

    # 1. repo wrapper
    try:
        if not os.path.isdir(os.path.join(KODI_ADDONS, "repository.jacktook")):
            data = http_get(JACKTOOK_REPO_URL, timeout=60)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extractall(KODI_ADDONS)
            ok("  repository.jacktook installed")
        else:
            ok("  repository.jacktook already installed")
    except Exception as exc:
        warn(f"  jacktook repo download failed: {exc}")
        return

    # 2. plugin + burst
    for aid, ver in JACKTOOK_PLUGINS:
        if os.path.isdir(os.path.join(KODI_ADDONS, aid)):
            ok(f"  {aid}: already installed")
            continue
        url = f"{JACKTOOK_DATADIR}/{aid}/{aid}-{ver}.zip"
        try:
            data = http_get(url, timeout=120)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extractall(KODI_ADDONS)
            ok(f"  {aid} v{ver} installed")
        except Exception as exc:
            warn(f"  {aid}: {exc}")


def _configure_jacktook_rd(access: str, refresh: str, username: str) -> None:
    """Push RD creds + sensible defaults into Jacktook's settings.xml.
    Keys verified from plugin.video.jacktook/resources/settings.xml."""
    if not os.path.isdir(os.path.join(KODI_ADDONS, "plugin.video.jacktook")):
        return
    _patch_addon_settings("plugin.video.jacktook", {
        "real_debrid_enabled":       "true",
        "real_debrid_token":         access,
        "real_debrid_refresh_token": refresh,
        "real_debrid_user":          username,
        # Providers that work without separate accounts:
        "jacktookburst_enabled":     "true",   # Burst-bundled torrent indexers
        "external_scraper_enabled":  "true",   # uses CocoScrapers if installed
        "stremio_enabled":           "true",   # optional Stremio addon-URL support
    })
    ok("  jacktook: RD + Burst + external_scraper + Stremio enabled")


def _elementum_arch_tag() -> Optional[str]:
    """Return the Elementum release asset suffix for this host's architecture."""
    m = platform.machine().lower()
    sys_name = platform.system().lower()
    if sys_name == "linux":
        if m in ("x86_64", "amd64"):  return "linux_x64"
        if m in ("i386", "i686"):     return "linux_x86"
        if m == "aarch64":            return "linux_arm64"
        if m == "armv7l":             return "linux_armv7"
        if m == "armv6l":             return "linux_armv6"
    elif sys_name == "darwin":
        if m in ("x86_64", "amd64"):  return "darwin_x64"
        if m == "arm64":              return "darwin_arm64"
    elif sys_name == "windows":
        if m in ("amd64", "x86_64"):  return "windows_x64"
        if m in ("i386", "i686"):     return "windows_x86"
    return None


def step_pvr(state: Dict[str, Any]) -> bool:
    header("Step 10 / 14  ·  PVR IPTV Simple Client")
    pvr_dir = os.path.join(KODI_USERDATA, "addon_data", "pvr.iptvsimple")
    os.makedirs(pvr_dir, exist_ok=True)
    path = os.path.join(pvr_dir, "settings.xml")

    m3u = "https://raw.githubusercontent.com/jimmershere/badtv/main/iptv/dist/badtv.m3u"
    epg = "https://raw.githubusercontent.com/jimmershere/badtv/main/iptv/dist/badtv.xml"
    info(f"M3U: {m3u}")
    info(f"EPG: {epg}")

    desired = {
        "m3uPathType": "1", "m3uUrl": m3u, "m3uCache": "true",
        "epgPathType": "1", "epgUrl": epg, "epgCache": "true",
        "startNum": "1", "logoPathType": "1", "catchupEnabled": "true",
    }
    # Earlier versions of this step parsed the existing settings.xml and
    # appended new <setting> nodes, which combined with Kodi rewriting the
    # file on shutdown produced duplicate keys (every id present twice).
    # Always rebuild fresh from `desired`; that's the entire intended state.
    root = ET.Element("settings", version="2")
    for k, v in desired.items():
        ET.SubElement(root, "setting", id=k).text = v
    ET.ElementTree(root).write(path, encoding="UTF-8", xml_declaration=True)
    ok(f"wrote {path}")

    # Also enable the PVR manager in guisettings so the addon actually starts
    # populating channels on next launch instead of waiting for the user to
    # toggle TV > Channels > Enabled by hand.
    _patch_pvr_enabled(KODI_USERDATA)
    mark_done(state, "pvr")
    return True


def _patch_pvr_enabled(userdata: str) -> None:
    """Ensure guisettings has pvrmanager.enabled = true so PVR populates
    channels on the next Kodi launch automatically."""
    path = os.path.join(userdata, "guisettings.xml")
    if os.path.isfile(path):
        try:
            tree = ET.parse(path); root = tree.getroot()
        except ET.ParseError:
            return
    else:
        root = ET.Element("settings", version="2"); tree = ET.ElementTree(root)
    existing = {s.get("id"): s for s in root.findall("setting")}
    desired = {"pvrmanager.enabled": "true",
               "pvrmanager.startgroupchannelnumbersfromone": "true",
               "epg.daystodisplay": "3"}
    for k, v in desired.items():
        elem = existing.get(k)
        if elem is None:
            elem = ET.SubElement(root, "setting", id=k)
        elem.text = v
        if "default" in elem.attrib:
            del elem.attrib["default"]
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def step_skin(state: Dict[str, Any]) -> bool:
    """Drop the B@Dtv color override into every installed skin that we
    have a matching `colors/badtv.xml` for. Do NOT force-switch the active
    skin -- let the user pick whichever skin they prefer on their display."""
    header("Step 11 / 14  ·  B@Dtv color theme (skin-agnostic)")

    # Map skin_addon_id -> our override source dir name.
    skin_overrides = {
        "skin.arctic.zephyr.mod":       "arctic-zephyr-mod",
        "skin.arctic.zephyr.reloaded":  "arctic-zephyr-reloaded",
        "skin.estuary.modv2":           "estuary-mod-v2",
        "skin.estuary":                 "estuary",
    }
    applied = []
    for skin_id, override_dir_name in skin_overrides.items():
        skin_dir = os.path.join(KODI_ADDONS, skin_id)
        if not os.path.isdir(skin_dir):
            continue
        src = os.path.join(REPO_ROOT, "build", "wizard", "resources", "skin",
                           override_dir_name, "colors", "badtv.xml")
        if not os.path.isfile(src):
            continue
        dst_dir = os.path.join(skin_dir, "colors")
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copy2(src, os.path.join(dst_dir, "badtv.xml"))
        ok(f"copied B@Dtv color override into {skin_id}/colors/")
        applied.append(skin_id)

    if not applied:
        info("no matching skin found on disk -- B@Dtv color overrides only "
             "exist for Arctic Zephyr (MOD / Reloaded) and Estuary (stock / MOD v2).")
        info("Whatever skin you've selected (estouchy, estuary, anything else) "
             "will keep its own colors; nothing here breaks it.")

    info("not auto-switching the active skin -- whatever you've selected "
         "in Settings > Interface > Skin stays.")
    info("to use the B@Dtv colour theme: Settings > Skin > Colours > badtv "
         "(only available if you pick one of the supported skins above).")
    mark_done(state, "skin", skin_overrides_applied=applied)
    return True


def _is_kodi_running() -> bool:
    return run_ok(["pgrep", "-x", "kodi.bin"])


def _kill_kodi() -> None:
    subprocess.run(["pkill", "-TERM", "kodi.bin"], check=False)
    subprocess.run(["pkill", "-TERM", "-f", "^/bin/sh.*kodi$"], check=False)
    time.sleep(2)
    subprocess.run(["pkill", "-KILL", "kodi.bin"], check=False)
    subprocess.run(["pkill", "-KILL", "-f", "^/bin/sh.*kodi$"], check=False)
    time.sleep(1)


def _patch_guisettings(userdata: str) -> bool:
    path = os.path.join(userdata, "guisettings.xml")
    if not os.path.isfile(path):
        # Kodi hasn't been run yet; write a minimal skeleton so the launch
        # step picks up the right skin on first boot.
        root = ET.Element("settings", version="2")
        ET.SubElement(root, "setting", id="lookandfeel.skin").text = SKIN_ID
        ET.SubElement(root, "setting", id="lookandfeel.skincolors").text = SKIN_THEME_NAME
        ET.ElementTree(root).write(path, encoding="UTF-8", xml_declaration=True)
        return True
    try:
        tree = ET.parse(path); root = tree.getroot()
    except ET.ParseError:
        return False
    desired = {
        "lookandfeel.skin": SKIN_ID,
        "lookandfeel.skincolors": SKIN_THEME_NAME,
    }
    existing = {s.get("id"): s for s in root.findall("setting")}
    for k, v in desired.items():
        # NB: a child-less Element is falsy in Python, so explicit `is None`.
        elem = existing.get(k)
        if elem is None:
            elem = ET.SubElement(root, "setting", id=k)
        elem.text = v
        if "default" in elem.attrib:
            del elem.attrib["default"]
    tree.write(path, encoding="UTF-8", xml_declaration=True)
    return True


def step_realdebrid(state: Dict[str, Any]) -> bool:
    header("Step 12 / 14  ·  Real-Debrid (optional)")
    if not confirm("Authorize Real-Debrid now? (skip if no account)", default=True):
        info("skipped Real-Debrid")
        mark_done(state, "realdebrid", realdebrid="skipped")
        return True
    # RD device-code endpoint is GET (not POST) with client_id +
    # new_credentials in the query string.
    try:
        device_url = (
            f"{REALDEBRID_DEVICE_URL}"
            f"?client_id={REALDEBRID_CLIENT_ID}&new_credentials=yes"
        )
        device = http_get_json(device_url)
    except Exception as exc:
        warn(f"could not start RD device flow: {exc}")
        warn("you can re-run anytime with `./badtv repair realdebrid`")
        mark_done(state, "realdebrid", realdebrid="error")
        return True   # non-blocking
    code = device.get("user_code", "?")
    url = device.get("verification_url", "https://real-debrid.com/device")
    interval = int(device.get("interval", 5))
    dev_code = device.get("device_code", "")
    cprint(f"\n  Go to: {url}", color=Color.AMBER, bold=True)
    cprint(f"  Enter code: {code}\n", color=Color.AMBER, bold=True)
    info("Waiting for authorization (ctrl-C to skip)...")
    deadline = time.time() + int(device.get("expires_in", 600))
    while time.time() < deadline:
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print(); warn("skipped during wait")
            mark_done(state, "realdebrid", realdebrid="skipped")
            return True
        try:
            creds_url = f"{REALDEBRID_CREDS_URL}?client_id={REALDEBRID_CLIENT_ID}&code={dev_code}"
            creds = http_get_json(creds_url)
        except urllib.error.HTTPError:
            sys.stdout.write("."); sys.stdout.flush()
            continue
        client_id_real = creds.get("client_id")
        client_secret = creds.get("client_secret")
        if client_id_real and client_secret:
            print()
            ok("Real-Debrid authorized")
            try:
                token = http_post(REALDEBRID_TOKEN_URL, {
                    "client_id": client_id_real,
                    "client_secret": client_secret,
                    "code": dev_code,
                    "grant_type": "http://oauth.net/grant_type/device/1.0",
                })
                _write_rd_settings(token, client_id_real, client_secret)
                mark_done(state, "realdebrid", realdebrid="authorized")
                return True
            except Exception as exc:
                warn(f"token exchange failed: {exc}")
                mark_done(state, "realdebrid", realdebrid="error")
                return True   # non-blocking
    warn("Real-Debrid authorization timed out")
    mark_done(state, "realdebrid", realdebrid="timeout")
    return True   # non-blocking


def _write_rd_settings(token: Dict[str, Any], client_id: str, client_secret: str) -> None:
    """Drop the RD credentials into every scraper that uses RD natively.

    Each scraper has its OWN key namespace and (worse) its OWN dedicated
    "is RD on?" boolean. Until v2.3.x we wrote vaguely-named keys like
    `realdebrid.token` that didn't match what any scraper actually
    reads -- every scraper kept showing the "No Debrid Account setup,
    account is required!" dialog because their on-disk slots were still
    empty.

    Exact keys come from grep of each addon's source 2026-05-25:

      Umbrella  -- plugin.video.umbrella/resources/lib/debrid/realdebrid.py
                   (`realdebridtoken` no dots, `realdebrid.clientid`,
                   `realdebridsecret`, `realdebridrefresh`,
                   `realdebridusername`) plus `realdebrid.enable=true`.

      Seren     -- plugin.video.seren/resources/lib/modules/globals.py:1190
                   (`realdebrid.enabled=true` AND `rd.auth=<token>`)
                   plus the rd.* family from real_debrid.py.

      POV       -- plugin.video.pov/resources/lib/debrids/real_debrid_api.py
                   (`rd.token`, `rd.refresh`, `rd.client_id`, `rd.secret`,
                   `rd.username`, `rd.expires`) plus `rd.enabled=true`.

      The Crew  -- script.module.thecrew/lib/.../debridcheck.py:20
                   reads from ResolveURL: `RealDebridResolver_enabled='true'`
                   AND `RealDebridResolver_token!=''`.
    """
    access  = token.get("access_token", "")
    refresh = token.get("refresh_token", "")
    # token.expires_in is seconds-from-now; addons store absolute epoch.
    expires = str(int(time.time()) + int(token.get("expires_in", 0) or 7689600))

    # Fetch username from RD API -- Umbrella + Seren + POV all key off it.
    # Non-fatal if the API is unreachable; addons will still work without it.
    username = ""
    try:
        req = urllib.request.Request(
            "https://api.real-debrid.com/rest/1.0/user",
            headers={"Authorization": f"Bearer {access}",
                     "User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            user = json.loads(resp.read().decode("utf-8"))
        username = user.get("username", "")
        info(f"  RD user: {username} ({user.get('type','?')}, "
             f"expires {user.get('expiration','?')[:10]})")
    except Exception as exc:
        warn(f"  could not fetch RD username: {exc}")

    # ResolveURL: used by The Crew (via debridcheck) and as a general
    # link resolver across the ecosystem. `_enabled=true` is what The
    # Crew explicitly checks.
    _patch_addon_settings("script.module.resolveurl", {
        "RealDebridResolver_enabled":       "true",
        "RealDebridResolver_login":         "true",   # hidden bool, defaults true
        "RealDebridResolver_client_id":     client_id,
        "RealDebridResolver_client_secret": client_secret,
        "RealDebridResolver_token":         access,
        "RealDebridResolver_refresh":       refresh,
    })

    # Umbrella -- exact keys from realdebrid.py
    _patch_addon_settings("plugin.video.umbrella", {
        "realdebrid.enable":   "true",
        "realdebridtoken":     access,
        "realdebridrefresh":   refresh,
        "realdebrid.clientid": client_id,
        "realdebridsecret":    client_secret,
        "realdebridusername":  username,
        "realdebrid.priority": "10",
    })

    # Seren -- needs BOTH `rd.auth` (token) AND `realdebrid.enabled=true`
    # for its globals.py check at line 1190.
    _patch_addon_settings("plugin.video.seren", {
        "realdebrid.enabled":  "true",
        "rd.auth":             access,
        "rd.refresh":          refresh,
        "rd.client_id":        client_id,
        "rd.secret":           client_secret,
        "rd.username":         username,
        "rd.expiry":           expires,
    })

    # POV -- `rd.enabled` defaults to true in its schema; we still write
    # it explicitly so a previously-cleared install lights back up.
    _patch_addon_settings("plugin.video.pov", {
        "rd.enabled":   "true",
        "rd.token":     access,
        "rd.refresh":   refresh,
        "rd.client_id": client_id,
        "rd.secret":    client_secret,
        "rd.username":  username,
        "rd.expires":   expires,
    })

    # Jacktook -- only set if the addon was already installed (it gets
    # installed in step_elementum, which runs BEFORE step_realdebrid).
    _configure_jacktook_rd(access, refresh, username)


def _patch_addon_settings(addon_id: str, desired: Dict[str, str]) -> None:
    """Idempotently merge `desired` into <addon_id>'s settings.xml. Safe
    to call even if the addon isn't installed yet -- we just create the
    file under addon_data so the addon picks it up on first launch."""
    d = os.path.join(KODI_USERDATA, "addon_data", addon_id)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "settings.xml")
    if os.path.isfile(path):
        try:
            tree = ET.parse(path); root = tree.getroot()
        except ET.ParseError:
            root = ET.Element("settings", version="2"); tree = ET.ElementTree(root)
    else:
        root = ET.Element("settings", version="2"); tree = ET.ElementTree(root)
    existing = {s.get("id"): s for s in root.findall("setting")}
    for k, v in desired.items():
        e = existing.get(k)
        if e is None:
            e = ET.SubElement(root, "setting", id=k)
        e.text = v
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def step_trakt(state: Dict[str, Any]) -> bool:
    header("Step 13 / 14  ·  Trakt")
    info("Trakt sync requires a registered Trakt OAuth app, which B@Dtv")
    info("doesn't ship one of (would require us to host client credentials).")
    info("")
    info("Easier path: when you install a scraper that supports Trakt")
    info("(Umbrella, Seren, FEN Light, ...), authorize Trakt inside THAT")
    info("addon's settings -- each addon ships its own registered client id")
    info("and walks you through the device code flow.")
    info("")
    info("If you don't use Trakt at all you can ignore this step.")
    mark_done(state, "trakt", trakt="defer_to_addon")
    return True
    # Below kept for reference; not reached. The placeholder client_id
    # below returns 403 from Trakt because it isn't a registered app.
    try:
        device = http_post(TRAKT_DEVICE_URL, {"client_id": TRAKT_CLIENT_ID})
    except Exception as exc:
        warn(f"could not start Trakt device flow: {exc}")
        warn("re-run later with `./badtv repair trakt`")
        mark_done(state, "trakt", trakt="error")
        return True   # non-blocking
    code = device.get("user_code", "?")
    url = device.get("verification_url", "https://trakt.tv/activate")
    interval = int(device.get("interval", 5))
    dev_code = device.get("device_code", "")
    cprint(f"\n  Go to: {url}", color=Color.AMBER, bold=True)
    cprint(f"  Enter code: {code}\n", color=Color.AMBER, bold=True)
    info("Waiting for authorization (ctrl-C to skip)...")
    deadline = time.time() + int(device.get("expires_in", 600))
    while time.time() < deadline:
        time.sleep(interval)
        try:
            token = http_post(TRAKT_TOKEN_URL, {
                "code": dev_code,
                "client_id": TRAKT_CLIENT_ID,
                "client_secret": TRAKT_CLIENT_ID,  # public flow
            })
        except urllib.error.HTTPError as exc:
            if exc.code == 400:
                sys.stdout.write("."); sys.stdout.flush()
                continue
            warn(f"Trakt token error: {exc}")
            mark_done(state, "trakt", trakt="error")
            return True   # non-blocking
        except KeyboardInterrupt:
            print(); warn("skipped during wait")
            mark_done(state, "trakt", trakt="skipped")
            return True
        if token.get("access_token"):
            print()
            ok("Trakt authorized")
            mark_done(state, "trakt", trakt_token=token.get("access_token"))
            return True
    warn("Trakt authorization timed out")
    mark_done(state, "trakt", trakt="timeout")
    return True


def step_stream_test(state: Dict[str, Any]) -> bool:
    header("Step 14 / 14  ·  Stream test (mpv)")
    if not shutil.which("mpv"):
        warn("mpv not installed; skipping stream test")
        mark_done(state, "stream_test", stream_test="skipped_no_mpv")
        return True
    try:
        m3u = http_get(
            "https://raw.githubusercontent.com/jimmershere/badtv/main/iptv/dist/badtv.m3u",
            timeout=30,
        ).decode("utf-8", errors="replace")
    except Exception as exc:
        warn(f"could not fetch playlist: {exc}")
        mark_done(state, "stream_test", stream_test="no_playlist")
        return True

    # Pick channels we expect to actually resolve from a US connection:
    # tvg-id ending in `.us@` (iptv-org's US channels), name containing
    # well-known US public-broadcaster patterns, or known-good MJH groups.
    # Skip MJH/Nz, MJH/Au, [Geo-blocked] markers, and any URL we already
    # know is regional-only.
    lines = m3u.splitlines()
    us_candidates: List[Tuple[str, str]] = []
    other_candidates: List[Tuple[str, str]] = []
    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF") or i + 1 >= len(lines):
            continue
        url = lines[i + 1].split("|", 1)[0].strip()
        if not url.startswith("http"):
            continue
        # Skip explicitly geo-blocked entries
        if "[Geo-blocked]" in line or "[Not 24/7]" in line:
            continue
        # Skip MJH NZ/AU which won't resolve from the US
        if "group-title=\"MJH / Nz\"" in line or "group-title=\"MJH / Au\"" in line:
            continue
        if 'group-title="Au"' in line or 'group-title="Nz"' in line:
            continue
        name_match = re.search(r',(.+)$', line)
        name = name_match.group(1) if name_match else "?"
        if re.search(r'tvg-id="[^"]*\.us@', line):
            us_candidates.append((name, url))
        else:
            other_candidates.append((name, url))
        if len(us_candidates) >= 8:
            break

    candidates = us_candidates[:8] or other_candidates[:5]
    info(f"trying {len(candidates)} US-region candidates ({len(us_candidates)} US-tagged in pool)")

    for idx, (name, url) in enumerate(candidates, 1):
        short = name[:50] if len(name) > 50 else name
        info(f"  {idx}/{len(candidates)}: {short}")
        try:
            cp = subprocess.run(
                ["mpv", "--no-video", "--ao=null", "--length=3",
                 "--quiet", "--no-terminal", url],
                timeout=10, capture_output=True, text=True,
            )
        except subprocess.TimeoutExpired:
            log(f"  timeout on {short}")
            continue
        if cp.returncode == 0:
            ok(f"PLAYED: {short}")
            ok("streams work from this network -- IPTV is going to work in Kodi")
            mark_done(state, "stream_test", working_channel=url, working_channel_name=name)
            return True
        log(f"  mpv exit {cp.returncode}: {cp.stderr[:150]}")

    warn(f"None of {len(candidates)} US-region candidates played.")
    warn("Most likely cause: Spectrum (your ISP) is DPI-blocking IPTV.")
    warn("Next step: ./badtv repair vpn   -- set up ExpressVPN to bypass.")
    mark_done(state, "stream_test", stream_test="all_failed")
    return True


def step_launch(state: Dict[str, Any]) -> bool:
    header("Done.  ·  Launching Kodi")
    if not shutil.which("kodi"):
        err("kodi binary not on PATH")
        return False
    info("Launching kodi --standalone -fs ...")
    info("(close Kodi with the on-screen power menu, or `pkill kodi.bin`)")
    if not confirm("Launch Kodi now?", default=True):
        info("Skipped launch. Run `./badtv launch` whenever you're ready.")
        return True
    try:
        subprocess.Popen(["kodi", "--standalone", "-fs"],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         start_new_session=True)
        ok("Kodi launched in standalone fullscreen.")
        info("First thing inside Kodi: Settings > Interface > Skin > "
             "Arctic Zephyr Reloaded, then Settings > Skin > Colours > badtv.")
    except Exception as exc:
        err(f"launch failed: {exc}")
        return False
    return True


# === wizard runner ===========================================================

STEPS: List[Tuple[str, Callable[[Dict[str, Any]], bool]]] = [
    ("disclaimer",          step_disclaimer),
    ("apt",                 step_apt),
    ("kodi_userdata",       step_kodi_userdata),
    ("vpn",                 step_vpn),
    ("badtv_addons",        step_install_repo_addon),
    ("install_official",    step_install_official),
    ("grey_addons",         step_grey_addons),
    ("floor2",              step_floor2_mount),
    ("elementum",           step_elementum),
    ("pvr",                 step_pvr),
    ("skin",                step_skin),
    ("realdebrid",          step_realdebrid),
    ("trakt",               step_trakt),
    ("stream_test",         step_stream_test),
    ("launch",              step_launch),
]


def cmd_setup(args: argparse.Namespace) -> int:
    banner()
    state = load_state()
    keepalive = None
    if shutil.which("sudo"):
        if ensure_sudo():
            keepalive = sudo_keepalive_loop_start()
    try:
        for step_id, fn in STEPS:
            if is_done(state, step_id) and not args.force:
                if step_id == "launch":
                    pass  # always offer to launch
                else:
                    ok(f"[{step_id}] already done -- skipping (use --force to re-run all)")
                    continue
            try:
                ok_ = fn(state)
            except KeyboardInterrupt:
                err(f"step {step_id} interrupted")
                return 130
            except Exception as exc:
                err(f"step {step_id} crashed: {exc}")
                log(f"step {step_id} crashed: {exc!r}")
                return 1
            if not ok_:
                err(f"step {step_id} reported failure -- stopping.")
                err("Resume after fixing with: ./badtv setup --resume")
                return 1
    finally:
        if keepalive is not None:
            keepalive.terminate()
    cprint("\n  All steps done. Enjoy B@Dtv.\n",
           color=Color.GREEN, bold=True)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state()
    cprint("B@Dtv setup status:", color=Color.AMBER, bold=True)
    print()
    for step_id, _ in STEPS:
        done = is_done(state, step_id)
        marker = "✓" if done else "·"
        col = Color.GREEN if done else Color.GREY
        at = state.get("steps", {}).get(step_id, {}).get("at", "")
        cprint(f"  {marker} {step_id:18}  {at}", color=col)
    print()
    for k, v in (state.get("vars") or {}).items():
        cprint(f"    {k} = {v}", color=Color.GREY)
    return 0


def cmd_launch(args: argparse.Namespace) -> int:
    return 0 if step_launch(load_state()) else 1


def cmd_repair(args: argparse.Namespace) -> int:
    step_id = args.step
    fn = dict(STEPS).get(step_id)
    if not fn:
        err(f"unknown step: {step_id}")
        err(f"available: {', '.join(s for s, _ in STEPS)}")
        return 1
    state = load_state()
    state.setdefault("steps", {}).pop(step_id, None)
    save_state(state)
    return 0 if fn(state) else 1


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="badtv", description="B@Dtv host-side wizard")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_setup = sub.add_parser("setup", help="run the full guided setup")
    sp_setup.add_argument("--force", action="store_true",
                          help="re-run every step (ignore prior completion)")
    sp_setup.add_argument("--resume", action="store_true",
                          help="continue from the last failed step (default behavior)")
    sp_setup.set_defaults(func=cmd_setup)

    sp_status = sub.add_parser("status", help="show step completion")
    sp_status.set_defaults(func=cmd_status)

    sp_launch = sub.add_parser("launch", help="launch Kodi standalone")
    sp_launch.set_defaults(func=cmd_launch)

    sp_repair = sub.add_parser("repair", help="re-run one specific step")
    sp_repair.add_argument("step", help="step id (see `./badtv status`)")
    sp_repair.set_defaults(func=cmd_repair)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
