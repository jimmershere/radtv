#!/usr/bin/env python3
"""B@Dtv Wizard entry point.

Kodi invokes this file when the user selects the wizard from
Programs / Add-ons / B@Dtv Wizard. All real work lives in
``resources/lib`` so it stays testable outside Kodi.
"""
import os
import sys

# Make `resources/` the import root so `lib/...` is a proper package and the
# relative imports inside it (`from . import actions`) resolve cleanly.
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, "resources"))

from lib.badtv_wizard import run  # noqa: E402


if __name__ == "__main__":
    sys.exit(run())
