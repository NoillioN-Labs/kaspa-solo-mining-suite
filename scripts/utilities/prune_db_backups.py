"""
scripts/utilities/prune_db_backups.py
======================================

Tiered (grandfather-father-son) retention for generated database backups.

WHY THIS IS NOT prune_log_archive.py
Logs are a COUNT problem: thousands of small files, and an old log is worthless,
so a pure age cutoff (config.yaml logging.archive_retention_days) is the right
shape. Database backups are a SIZE problem: tens of files, hundreds of MB each,
and **an age cutoff is the wrong shape entirely** -- a backup's value is being a
restore point, and a restore point does not expire on a calendar.

The naive policies both fail. "Keep the last N" has no recovery rationale and
grows without bound in BYTES as the database itself grows. "Delete older than D
days" throws away your only monthly restore point. Grandfather-father-son
expresses the actual question -- *how far back can I restore?* -- as
"1 per day for the recent window, then 1 per week for the window before that".

CONFIGURATION (config.yaml `database_backups`), because a template cannot know
your naming convention::

    database_backups:
      backup_dir: ".data/backups"   # relative to repo root, or absolute
      filename_prefix: "backup"     # matches <prefix>_<YYYYMMDD>_<HHMMSS>.db
      daily_count: 7                # keep 1/day for the most recent 7 days that HAVE one
      weekly_count: 4               # then 1/week for the following 4 distinct ISO weeks

Scope is deliberately narrow, mirroring prune_log_archive.py: only files matching
`<prefix>_<YYYYMMDD>_<HHMMSS>.db` are candidates. **Manually-named snapshots
living in the same folder are never touched** -- ad-hoc snapshots have no naming
convention to key on, which is exactly why they accumulate, and automating their
deletion is how you lose the one someone was keeping on purpose. Triage those by
hand, tracing each to the story or incident that produced it.

Dry-run by default (AGENTS 5.1): reports what would be deleted and writes nothing
until --execute.

Usage
-----
    python scripts/utilities/prune_db_backups.py
    python scripts/utilities/prune_db_backups.py --execute
    python scripts/utilities/prune_db_backups.py --daily-count 7 --weekly-count 4 --execute
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

_DEFAULT_DAILY_COUNT = 7
_DEFAULT_WEEKLY_COUNT = 4
_COUNT_BOUNDS = (1, 90)
_DEFAULT_BACKUP_DIR = ".data/backups"
_DEFAULT_PREFIX = "backup"
_DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def _filename_re(prefix: str) -> re.Pattern[str]:
    """Match `<prefix>_<YYYYMMDD>_<HHMMSS>.db`, prefix escaped so it cannot inject."""
    return re.compile(rf"^{re.escape(prefix)}_(\d{{8}})_(\d{{6}})\.db$")


def _parse_backup_date(path: Path, pattern: re.Pattern[str]) -> date | None:
    """The calendar date from a backup's FILENAME, never its mtime.

    Same rationale as archive_session.py's continuation detection: git checkouts
    and cloud-sync clients rewrite mtimes for reasons unrelated to when the backup
    was taken, and keying retention on a rewritable timestamp is how you delete
    the wrong file with total confidence.
    """
    match = pattern.match(path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None  # e.g. 20261332 -- shaped right, not a real date


def _load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Read the `database_backups` block. Bounded; warns and falls back on nonsense."""
    import yaml  # lazy, per project convention

    path = config_path or _DEFAULT_CONFIG_PATH
    block: dict[str, Any] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        raw = loaded.get("database_backups")
        if isinstance(raw, dict):
            block = raw
    except OSError as exc:
        print(
            f"[WARN] database_backups: could not read {path} ({exc}); "
            f"using defaults {_DEFAULT_DAILY_COUNT}/day + {_DEFAULT_WEEKLY_COUNT}/week."
        )

    lo, hi = _COUNT_BOUNDS

    def _count(key: str, default: int) -> int:
        raw_value = block.get(key, default)
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            print(f"[WARN] database_backups.{key}={raw_value!r} is not numeric; using default {default}.")
            return default
        if not (lo <= value <= hi):
            print(f"[WARN] database_backups.{key}={value} outside [{lo}, {hi}]; using default {default}.")
            return default
        return value

    return {
        "daily_count": _count("daily_count", _DEFAULT_DAILY_COUNT),
        "weekly_count": _count("weekly_count", _DEFAULT_WEEKLY_COUNT),
        "backup_dir": str(block.get("backup_dir") or _DEFAULT_BACKUP_DIR),
        "filename_prefix": str(block.get("filename_prefix") or _DEFAULT_PREFIX),
        "db_path": str(block.get("db_path") or ""),  # read by backup_db.py (the producer)
    }


def select_backups_to_prune(
    backup_dir: Path,
    *,
    daily_count: int = _DEFAULT_DAILY_COUNT,
    weekly_count: int = _DEFAULT_WEEKLY_COUNT,
    filename_prefix: str = _DEFAULT_PREFIX,
) -> list[Path]:
    """Grandfather-father-son selection.

    Keep 1 backup per day for the most recent `daily_count` days that HAVE one,
    then 1 per ISO week for the following `weekly_count` distinct weeks. Everything
    else -- extra same-day backups, and anything past the window -- is a candidate.

    Only files matching `<prefix>_<YYYYMMDD>_<HHMMSS>.db` are considered; anything
    else in backup_dir (manually-named snapshots) is left alone.

    **Adapts to gaps**: the windows are defined by which days actually HAVE a
    backup, not by calendar distance from today -- so a missed day does not
    silently shrink the number of restore points you keep. That distinction
    matters most precisely when the backup job has been failing.
    """
    if not backup_dir.is_dir():
        return []

    pattern = _filename_re(filename_prefix)
    dated: list[tuple[date, Path]] = []
    for path in backup_dir.iterdir():
        if not path.is_file():
            continue
        parsed = _parse_backup_date(path, pattern)
        if parsed is not None:
            dated.append((parsed, path))
    if not dated:
        return []

    by_day: dict[date, list[Path]] = {}
    for parsed, path in dated:
        by_day.setdefault(parsed, []).append(path)
    for paths in by_day.values():
        paths.sort(key=lambda p: p.name, reverse=True)  # [0] = day's newest, the one kept

    days_desc = sorted(by_day.keys(), reverse=True)

    keep: set[Path] = set()
    for day in days_desc[:daily_count]:
        keep.add(by_day[day][0])

    seen_weeks: set[tuple[int, int]] = set()
    for day in days_desc[daily_count:]:
        if len(seen_weeks) >= weekly_count:
            break
        week_key = day.isocalendar()[:2]  # (iso_year, iso_week)
        if week_key in seen_weeks:
            continue
        seen_weeks.add(week_key)
        keep.add(by_day[day][0])

    return [path for _, path in dated if path not in keep]


def prune(
    backup_dir: Path,
    *,
    daily_count: int,
    weekly_count: int,
    execute: bool,
    filename_prefix: str = _DEFAULT_PREFIX,
) -> dict[str, int]:
    candidates = select_backups_to_prune(
        backup_dir,
        daily_count=daily_count,
        weekly_count=weekly_count,
        filename_prefix=filename_prefix,
    )
    deleted = 0
    failed = 0
    for path in candidates:
        if not execute:
            continue
        try:
            path.unlink()
            deleted += 1
        except OSError as exc:
            print(f"[WARN] could not delete {path}: {exc}")
            failed += 1
    return {"candidates": len(candidates), "deleted": deleted, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--daily-count", type=int, default=None,
        help="Override config.yaml's database_backups.daily_count for this run.",
    )
    parser.add_argument(
        "--weekly-count", type=int, default=None,
        help="Override config.yaml's database_backups.weekly_count for this run.",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually delete. Without this flag, only reports what would be deleted.",
    )
    args = parser.parse_args()

    config = _load_config()
    daily_count = args.daily_count if args.daily_count is not None else config["daily_count"]
    weekly_count = args.weekly_count if args.weekly_count is not None else config["weekly_count"]
    prefix = config["filename_prefix"]

    configured_dir = Path(config["backup_dir"])
    backup_dir = configured_dir if configured_dir.is_absolute() else PROJECT_ROOT / configured_dir

    # Say so out loud rather than no-opping into a clean exit (AGENTS 5.5.1): a
    # project with no database should read "nothing here", not "pruned OK".
    if not backup_dir.is_dir():
        print(
            f"No backup directory at {backup_dir} -- nothing to prune. "
            "(Set database_backups.backup_dir in config.yaml if this is wrong.)"
        )
        return 0

    candidates = select_backups_to_prune(
        backup_dir, daily_count=daily_count, weekly_count=weekly_count, filename_prefix=prefix
    )
    policy = f"policy: {daily_count}/day + {weekly_count}/week, prefix '{prefix}'"
    if not candidates:
        print(f"No prune candidates in {backup_dir} ({policy}).")
        return 0

    total_bytes = sum(p.stat().st_size for p in candidates if p.exists())
    verb = "Deleting" if args.execute else "[DRY-RUN] Would delete"
    print(f"{verb} {len(candidates)} file(s) ({total_bytes / 1_048_576:.1f} MB) from {backup_dir} ({policy})")
    for path in sorted(candidates):
        print(f"  {path.name}")

    result = prune(
        backup_dir,
        daily_count=daily_count,
        weekly_count=weekly_count,
        execute=args.execute,
        filename_prefix=prefix,
    )
    if args.execute:
        print(f"Deleted {result['deleted']}, failed {result['failed']}.")
    else:
        print("Re-run with --execute to actually delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
