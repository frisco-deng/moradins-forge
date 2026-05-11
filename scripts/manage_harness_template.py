"""Compatibility wrapper for the old template management entrypoint.

The canonical entrypoint is now ``scripts/manage_moradin_payload.py``. Keep this
module for one compatibility window so existing tests, Make targets, and user
commands keep working while operator-facing language moves to Moradin payloads.
"""

from __future__ import annotations

from scripts.manage_moradin_payload import *  # noqa: F403
from scripts.manage_moradin_payload import main


if __name__ == "__main__":
    raise SystemExit(main())
