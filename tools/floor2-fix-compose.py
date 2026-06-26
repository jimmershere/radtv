#!/usr/bin/env python3
"""Fix invalid docker-compose ${{VAR}} interpolation on floor2 stacks.

Some deploy paths left bootstrap template braces literally in
docker-compose.yml (e.g. VPN_TYPE=${{VPN_TYPE:-wireguard}}). Docker Compose
requires ${VAR:-default} — one brace pair.

Run on floor2:
    python3 tools/floor2-fix-compose.py
    ./radtv repair fix-compose
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

STACK_CANDIDATES = (
    "/datapool/preserved/badtv-arr",
    "/datapool/preserved/radtv-arr",
)

# ${{NAME:-default}} or ${{NAME}} → ${NAME:-default} / ${NAME}
_BAD_INTERP = re.compile(r"\$\{\{([^}]+)\}\}")


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


def fix_compose_interpolation(text: str) -> str:
    return _BAD_INTERP.sub(r"${\1}", text)


def patch_compose_file(path: str) -> bool:
    body = open(path, encoding="utf-8").read()
    fixed = fix_compose_interpolation(body)
    if fixed == body:
        return False
    open(path, "w", encoding="utf-8").write(fixed)
    return True


def main() -> int:
    stack = detect_stack()
    compose_path = f"{stack}/docker-compose.yml"
    if not os.path.isfile(compose_path):
        log(f"ERROR: missing {compose_path}")
        return 1

    log(f"stack: {stack}")
    if patch_compose_file(compose_path):
        log(f"fixed ${{...}} interpolation in {compose_path}")
    else:
        log("compose interpolation already OK")

    log("validating docker compose config...")
    cp = subprocess.run(
        ["docker", "compose", "config"],
        cwd=stack,
        capture_output=True,
        text=True,
    )
    if cp.returncode != 0:
        log(f"ERROR: docker compose config failed:\n{cp.stderr[:800]}")
        return cp.returncode
    log("docker compose config OK")

    if on_floor2():
        log("restarting gluetun + qbittorrent...")
        subprocess.run(
            ["docker", "compose", "up", "-d", "gluetun", "qbittorrent"],
            cwd=stack,
            check=False,
        )
        subprocess.run(
            ["docker", "compose", "ps", "gluetun", "qbittorrent"],
            cwd=stack,
            check=False,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
