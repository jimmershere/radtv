#!/usr/bin/env python3
"""B@Dtv build helpers.

Currently:

    build-repo.py rename-zip-root <zip> <old-prefix> <new-prefix>

Kodi addon zips must extract to a top-level directory named exactly the
addon id. `make repo` uses `zip` with the working tree dir name as the
prefix, then calls this helper to rewrite it.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipfile


def rename_zip_root(zip_path: str, old_prefix: str, new_prefix: str) -> None:
    if old_prefix == new_prefix:
        return
    if not os.path.isfile(zip_path):
        sys.exit(f"zip not found: {zip_path}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp_path = tmp.name

    with zipfile.ZipFile(zip_path, "r") as src, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            name = info.filename
            if name == f"{old_prefix}/" or name.startswith(f"{old_prefix}/"):
                new_name = new_prefix + name[len(old_prefix):]
            else:
                new_name = name
            data = src.read(info.filename)
            new_info = zipfile.ZipInfo(filename=new_name, date_time=info.date_time)
            new_info.compress_type = zipfile.ZIP_DEFLATED
            new_info.external_attr = info.external_attr
            dst.writestr(new_info, data)

    shutil.move(tmp_path, zip_path)
    print(f"  renamed zip root {old_prefix}/ -> {new_prefix}/ in {zip_path}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "rename-zip-root":
        if len(argv) != 5:
            sys.exit("usage: build-repo.py rename-zip-root <zip> <old-prefix> <new-prefix>")
        rename_zip_root(argv[2], argv[3], argv[4])
        return 0
    sys.exit(f"unknown command: {cmd}")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
