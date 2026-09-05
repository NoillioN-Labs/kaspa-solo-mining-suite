"""Vendor adapter hook (AGENTS.md #2): governance gate at session stop.

Stop hook: runs scripts/utilities/governance_lint.py and blocks the stop once
per violation set (exit 2) so the agent resolves governance ERRORs before
finishing. Warnings never block. Honors stop_hook_active to avoid loops.
Stdlib only.
"""

from __future__ import annotations

import json
import os
import subprocess
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
        payload = {}
    if payload.get("stop_hook_active"):
        return 0  # already blocked once this stop; don't loop

    root = project_root()
    lint = root / "scripts" / "utilities" / "governance_lint.py"
    if not lint.is_file():
        return 0

    result = subprocess.run(
        [sys.executable, str(lint), "--json"],
        cwd=str(root),
        capture_output=True,
        # Explicit codec, never text=True: text=True decodes with the locale codec (cp1252
        # on Windows) and it decodes stderr too, which this hook never reads -- so a child
        # traceback carrying a byte cp1252 lacks silently turns BOTH streams into None
        # (capture_output decodes on reader threads and swallows the error). The gate does
        # not stop gating -- json.loads(None) raises TypeError, which the except below
        # already catches, so the hook still blocks -- but it blocks with the useless
        # generic message instead of naming the errors. Decode explicitly and keep the
        # diagnosis (AGENTS 5.5.1).
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if result.returncode == 0:
        return 0

    errors: list[str] = []
    try:
        findings = json.loads(result.stdout)
        errors = [f["message"] for f in findings if f.get("severity") == "ERROR"][:5]
    except (json.JSONDecodeError, ValueError, KeyError, TypeError):
        pass

    detail = "; ".join(errors) if errors else "run scripts/utilities/governance_lint.py for details"
    sys.stderr.write(
        f"governance_lint found ERRORs — resolve before finishing: {detail}"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
