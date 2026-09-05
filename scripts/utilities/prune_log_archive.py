"""
scripts/utilities/prune_log_archive.py
=======================================

Delete rotated log files from ``logs/archive/`` once they age past
``logging.archive_retention_days`` (config.yaml; default 30).

``archive_session.py`` only ever MOVES timestamped files out of the live
``logs/`` directory into ``logs/archive/`` — nothing ever deleted them, so
that directory grows forever. The file COUNT is the real cost, not the disk space:
``backend.core.logger.initialize_logging()`` runs a directory sweep on every
single job start, and that scan slows down as the archive balloons.

Scope is deliberately narrow: ``logs/archive/`` only. ``docs/*/archive/``
folders hold git-tracked deliverables (chat backups, session logs, code
reviews) and must never be touched by this script.

Dry-run by default (AGENTS 5.1): reports what would be deleted and writes
nothing until ``--execute``.

Usage
-----
    python scripts/utilities/prune_log_archive.py
    python scripts/utilities/prune_log_archive.py --execute
    python scripts/utilities/prune_log_archive.py --older-than-days 60 --execute
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

_DEFAULT_RETENTION_DAYS = 30
_RETENTION_BOUNDS = (7, 365)
_DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def _load_retention_days(config_path: Path | None = None) -> int:
    """Bounded, warns and falls back on nonsense — mirrors the
    settings-loader pattern."""
    import yaml  # type: ignore  # lazy, per project convention

    path = config_path or _DEFAULT_CONFIG_PATH
    block: dict[str, Any] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        raw = loaded.get("logging")
        if isinstance(raw, dict):
            block = raw
    except OSError as exc:
        print(f"[WARN] logging: could not read {path} ({exc}); using default {_DEFAULT_RETENTION_DAYS}.")
        return _DEFAULT_RETENTION_DAYS

    raw_value = block.get("archive_retention_days", _DEFAULT_RETENTION_DAYS)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        print(
            f"[WARN] logging.archive_retention_days={raw_value!r} is not numeric; "
            f"using default {_DEFAULT_RETENTION_DAYS}."
        )
        return _DEFAULT_RETENTION_DAYS
    lo, hi = _RETENTION_BOUNDS
    if not (lo <= value <= hi):
        print(
            f"[WARN] logging.archive_retention_days={value} outside [{lo}, {hi}]; "
            f"using default {_DEFAULT_RETENTION_DAYS}."
        )
        return _DEFAULT_RETENTION_DAYS
    return value


def find_stale_files(archive_dir: Path, retention_days: int, *, now: datetime | None = None) -> list[Path]:
    """Files in ``archive_dir`` (non-recursive) older than ``retention_days``,
    by filesystem mtime."""
    if not archive_dir.is_dir():
        return []
    cutoff = (now or datetime.now(UTC)).timestamp() - retention_days * 86400
    stale = []
    for path in archive_dir.iterdir():
        if not path.is_file():
            continue
        # .keep / .gitkeep are git-tracked sentinels (.gitignore whitelists
        # them so logs/archive/ survives a fresh clone despite `logs/*` being
        # ignored) — never delete a dotfile here.
        if path.name.startswith("."):
            continue
        try:
            if path.stat().st_mtime < cutoff:
                stale.append(path)
        except OSError:
            continue
    return stale


def prune(archive_dir: Path, retention_days: int, *, execute: bool) -> dict[str, int]:
    stale = find_stale_files(archive_dir, retention_days)
    deleted = 0
    failed = 0
    for path in stale:
        if not execute:
            continue
        try:
            path.unlink()
            deleted += 1
        except OSError as exc:
            print(f"[WARN] could not delete {path}: {exc}")
            failed += 1
    return {"candidates": len(stale), "deleted": deleted, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--older-than-days", type=int, default=None,
        help="Override config.yaml's logging.archive_retention_days for this run.",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually delete. Without this flag, only reports what would be deleted.",
    )
    args = parser.parse_args()

    retention_days = args.older_than_days if args.older_than_days is not None else _load_retention_days()
    archive_dir = PROJECT_ROOT / "logs" / "archive"

    stale = find_stale_files(archive_dir, retention_days)
    if not stale:
        print(f"No files older than {retention_days} day(s) in {archive_dir}.")
        return 0

    total_bytes = sum(p.stat().st_size for p in stale if p.exists())
    verb = "Deleting" if args.execute else "[DRY-RUN] Would delete"
    print(
        f"{verb} {len(stale)} file(s) ({total_bytes / 1_048_576:.1f} MB) "
        f"older than {retention_days} day(s) from {archive_dir}"
    )

    result = prune(archive_dir, retention_days, execute=args.execute)
    if args.execute:
        print(f"Deleted {result['deleted']}, failed {result['failed']}.")
    else:
        print("Re-run with --execute to actually delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
