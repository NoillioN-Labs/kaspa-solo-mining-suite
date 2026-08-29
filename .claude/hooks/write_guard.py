"""Vendor adapter (AGENTS 2): translates this tool's hook protocol to the shared rule.

PreToolUse hook for file-writing tools. Reads the tool call as JSON on stdin and
delegates the actual decision to the vendor-neutral
`scripts/utilities/write_boundary_check.py` (AGENTS 9).

**This file must contain ZERO rules.** It is regenerable by bootstrap, and AGENTS 2
requires that losing an adapter never loses information. If you find yourself
adding a path condition here, it belongs in the shared checker instead.

Exit 0 = allow / defer. Exit 2 = block (stderr is shown to the agent).
Stdlib only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def project_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return 0  # malformed input: defer to the permission system

    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not file_path:
        return 0

    root = project_root()

    # Import the shared rule rather than shelling out: one import beats spawning a
    # subprocess on every single file write, and the adapter stays just as thin.
    sys.path.insert(0, str(root / "scripts" / "utilities"))
    try:
        from write_boundary_check import check_write_boundary
    except ImportError:
        return 0  # shared rule unavailable: defer to the permission system

    allowed, reason = check_write_boundary(Path(file_path), root)
    if allowed:
        return 0

    sys.stderr.write(f"BLOCKED by AGENTS 9: {reason}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
