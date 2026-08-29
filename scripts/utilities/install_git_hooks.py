"""
scripts/utilities/install_git_hooks.py
======================================

Point this repository's git hooks at the TRACKED hook directory
(``scripts/hooks``) by setting ``core.hooksPath``.

Why a script rather than a documented one-liner: ``core.hooksPath`` is *local*
repository config, so it does not survive a fresh clone and cannot be committed.
Without an installer the push-cost guard silently does not exist on a new machine
-- and **a guard that is silently absent is worse than no guard**, because
everyone assumes it is running. That is the same failure shape as the incident
AGENTS 8 exists to prevent, where CI itself was dark for days while being relied
on: "not running" and "running and passing" are indistinguishable unless
something checks.

Idempotent. Safe to run repeatedly. Run from anywhere inside the repo::

    .venv/Scripts/python.exe scripts/utilities/install_git_hooks.py
    .venv/Scripts/python.exe scripts/utilities/install_git_hooks.py --check

``--check`` exits non-zero if the hooks are NOT installed, so it can be used as
a gate without mutating anything.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HOOKS_DIR_REL = "scripts/hooks"
EXPECTED_HOOKS = ("pre-push", "pre-commit")


def _git(*args: str, cwd: Path) -> str:
    """Run a git command and return stripped stdout, or raise with context."""
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        # Explicit codec, never text=True: the locale codec (cp1252 on Windows) has no
        # mapping for five byte values, and what comes back here is a filesystem PATH
        # (rev-parse --show-toplevel, core.hooksPath) plus git's stderr. Under a project
        # folder named outside cp1252, text=True does not raise here -- capture_output
        # decodes on reader threads, the error is swallowed, and stdout comes back None,
        # so the installer dies on the .strip() below instead. Either way it dies, and an
        # uninstalled push guard is silently absent rather than loudly broken
        # (AGENTS 8, 5.5.1).
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def repo_root() -> Path:
    """The repository root, resolved via git rather than assumed from __file__."""
    here = Path(__file__).resolve().parent
    return Path(_git("rev-parse", "--show-toplevel", cwd=here))


def current_hooks_path(root: Path) -> str | None:
    """The configured core.hooksPath, or None when unset."""
    try:
        return _git("config", "--get", "core.hooksPath", cwd=root) or None
    except RuntimeError:
        # `--get` exits 1 when the key is absent; that is not an error here.
        return None


def missing_hooks(root: Path) -> list[str]:
    """Hook files named in EXPECTED_HOOKS that are absent from the tracked dir."""
    hooks_dir = root / HOOKS_DIR_REL
    return [name for name in EXPECTED_HOOKS if not (hooks_dir / name).is_file()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report status and exit non-zero if hooks are not installed; change nothing",
    )
    args = parser.parse_args()

    root = repo_root()
    configured = current_hooks_path(root)
    absent = missing_hooks(root)

    if absent:
        # Fail loudly rather than pointing git at a directory lacking the hook
        # it is supposed to run (AGENTS 5.5.1: never no-op into a green result).
        print(
            f"ERROR: {HOOKS_DIR_REL}/ is missing expected hook(s): {', '.join(absent)}",
            file=sys.stderr,
        )
        return 2

    installed = configured == HOOKS_DIR_REL

    if args.check:
        if installed:
            print(f"OK: core.hooksPath = {configured}")
            return 0
        print(
            "NOT INSTALLED: core.hooksPath = "
            f"{configured!r} (expected {HOOKS_DIR_REL!r}). "
            "Run this script without --check to install.",
            file=sys.stderr,
        )
        return 1

    if installed:
        print(f"Already installed: core.hooksPath = {configured}")
        return 0

    if configured:
        # Do not silently clobber a different hooks directory someone chose.
        print(
            f"REFUSING: core.hooksPath is already set to {configured!r}, not "
            f"{HOOKS_DIR_REL!r}. Resolve by hand -- core.hooksPath replaces ALL "
            "hooks, so overwriting it could disable hooks you rely on.",
            file=sys.stderr,
        )
        return 3

    _git("config", "core.hooksPath", HOOKS_DIR_REL, cwd=root)
    print(f"Installed: core.hooksPath = {HOOKS_DIR_REL}")
    print(f"Active hooks: {', '.join(EXPECTED_HOOKS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
