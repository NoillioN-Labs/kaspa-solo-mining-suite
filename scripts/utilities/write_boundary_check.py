#!/usr/bin/env python3
"""Cross-project write boundary rule (AGENTS 9), vendor-neutral.

Sibling projects are read-only, except a sibling's own `docs/upgrades/` folder --
upgrade-pack dissemination is the single permitted cross-project write.

WHY THIS IS NOT IN THE HOOK. The rule used to live inside the vendor adapter
(`.claude/hooks/write_guard.py`), which violates AGENTS 2: adapters are "thin,
regenerable" and "contain zero rules", because bootstrap recreates them and
**losing an adapter must never lose information**. With the rule inside, a
regenerated adapter silently takes the project's only enforcement of AGENTS 9
with it -- and nothing fails, which is the whole problem. Vendor hooks are now
thin translators: payload in, verdict out.

Usage::

    python scripts/utilities/write_boundary_check.py --target <path> [--project-root <path>]

Exit codes: 0 allowed, 1 blocked. Prints {"allowed": bool, "reason": str} either
way, so a non-Python vendor adapter can shell out and parse the verdict.

Pure function over path strings; stdlib only, no network, no external tools.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[2]

#: The one sub-path of a sibling project that may be written to (AGENTS 9).
PERMITTED_SIBLING_SUBPATH: tuple[str, ...] = ("docs", "upgrades")


def check_write_boundary(target: Path, project_root: Path) -> tuple[bool, str]:
    """Return ``(allowed, reason)``; ``reason`` is empty when allowed.

    Deliberately DEFERS (returns allowed) rather than blocking whenever it cannot
    positively identify a cross-project write: unresolvable paths, locations
    outside the fleet directory, and siblings with no `AGENTS.md` (a shared skills
    registry, a scratch folder) are all somebody else's decision. This guard exists
    to stop one specific, well-defined mistake -- not to become the permission
    system, which still runs either way.
    """
    root = project_root.resolve()
    try:
        resolved_target = target.resolve()
    except (OSError, ValueError):
        return True, ""  # unresolvable: defer to the caller's own checks

    if resolved_target == root or root in resolved_target.parents:
        return True, ""  # inside this project

    fleet_parent = root.parent
    if fleet_parent not in resolved_target.parents:
        return True, ""  # unrelated location

    try:
        sibling = resolved_target.relative_to(fleet_parent).parts[0]
        rel_within = resolved_target.relative_to(fleet_parent / sibling).parts
    except (ValueError, IndexError):
        return True, ""

    # A sibling without AGENTS.md is not a governed project (e.g. the shared skills
    # registry). Writes there are the permission system's call, not this rule's.
    if not (fleet_parent / sibling / "AGENTS.md").is_file():
        return True, ""

    if tuple(rel_within[: len(PERMITTED_SIBLING_SUBPATH)]) == PERMITTED_SIBLING_SUBPATH:
        return True, ""  # permitted: upgrade-pack dissemination

    reason = (
        f"writes into sibling project '{sibling}' are read-only except its "
        "docs/upgrades/ folder (AGENTS 9). Output instructions for the user "
        "instead, or use apply_upgrade.py disseminate."
    )
    return False, reason


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="Path being written to")
    parser.add_argument(
        "--project-root",
        default=str(REPO_ROOT),
        help="This project's root (default: inferred from this script's location)",
    )
    args = parser.parse_args(argv)

    allowed, reason = check_write_boundary(Path(args.target), Path(args.project_root))
    print(json.dumps({"allowed": allowed, "reason": reason}))
    return 0 if allowed else 1


if __name__ == "__main__":
    sys.exit(main())
