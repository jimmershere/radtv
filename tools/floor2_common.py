"""Shared helpers for floor2 repair scripts (SSH target, stack paths)."""
from __future__ import annotations

import os
import re
import subprocess
from typing import Tuple

FLOOR2_IP_DEFAULT = "192.168.1.206"
FLOOR2_USER_DEFAULT = "floor2"
FLOOR2_HOST_ALIAS = "floor2"

STACK_CANDIDATES = (
    "/datapool/preserved/badtv-arr",
    "/datapool/preserved/radtv-arr",
)


def floor2_ip() -> str:
    return os.environ.get("FLOOR2_IP", FLOOR2_IP_DEFAULT)


def floor2_user() -> str:
    return os.environ.get("FLOOR2_USER", FLOOR2_USER_DEFAULT)


def floor2_host() -> str:
    """Logical host for URLs/NFS — prefer short name once /etc/hosts is set."""
    return os.environ.get("FLOOR2_HOST", FLOOR2_HOST_ALIAS)


def ssh_config_has_floor2() -> bool:
    cfg = os.path.expanduser("~/.ssh/config")
    if not os.path.isfile(cfg):
        return False
    try:
        with open(cfg, encoding="utf-8") as fh:
            return bool(re.search(r"(?m)^Host\s+floor2\b", fh.read()))
    except OSError:
        return False


def ssh_destination() -> str:
    """OpenSSH target.

    Prefer the ``floor2`` Host alias when present in ~/.ssh/config so
    ``ssh floor2`` works (User + HostName + keys from config).
    Fallback: floor2@192.168.1.206
    """
    if os.environ.get("FLOOR2_SSH"):
        return os.environ["FLOOR2_SSH"]
    if ssh_config_has_floor2():
        return FLOOR2_HOST_ALIAS
    return f"{floor2_user()}@{floor2_ip()}"


def run_remote(script: str, *, log_cmd: bool = True) -> Tuple[int, str, str]:
    dest = ssh_destination()
    cmd = ["ssh", "-o", "ConnectTimeout=15", dest, "bash", "-s"]
    if log_cmd:
        print(f"  $ ssh {dest}", flush=True)
    cp = subprocess.run(cmd, input=script, text=True, capture_output=True)
    if cp.stdout:
        print(cp.stdout, end="" if cp.stdout.endswith("\n") else "\n")
    if cp.stderr:
        print(cp.stderr, end="" if cp.stderr.endswith("\n") else "\n", file=__import__("sys").stderr)
    return cp.returncode, cp.stdout, cp.stderr


def on_floor2() -> bool:
    return os.path.isdir("/datapool/preserved")


def ssh_preflight() -> bool:
    """Return True if SSH to floor2 works from this machine."""
    dest = ssh_destination()
    cp = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", dest, "true"],
        capture_output=True,
        text=True,
    )
    return cp.returncode == 0
