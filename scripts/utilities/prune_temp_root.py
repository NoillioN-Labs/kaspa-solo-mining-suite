"""
scripts/utilities/prune_temp_root.py
=====================================

Size-bounded retention for the test/scratch temp root (`testing.temp_root` in
config.yaml, defaulting to the `.data/tmp` that `backend/core/paths.py`'s
`project_temp_dir()` hands out).

THREE PRUNERS, THREE DIFFERENT SHAPES -- and the shape is the whole design:

* `prune_log_archive.py`  -- a COUNT problem. An old log is worthless, so an AGE
  cutoff is right.
* `prune_db_backups.py`   -- a RECOVERY-WINDOW problem. A backup's value is being
  a restore point, which does not expire on a calendar, so grandfather-father-son.
* this one              -- scratch output has zero recovery value at ANY age. The
  only thing worth bounding is how much disk it occupies at once, so: a SIZE
  ceiling, deleting oldest-first only until back under it.

**This is a backstop, not the fix.** It catches a regression -- an expensive
fixture that stopped being session-scoped, or a caller that stopped passing
`dir=`. The primary fix is callers routing through `project_temp_dir()` and bulk
read-only fixtures being session-scoped (AGENTS 5.7). Note also that pytest clears
an explicit `--basetemp` at session start, so an oversized root is a peak-per-run
symptom rather than accumulation: if this prunes regularly, fix the fixture.

Deletes oldest-first until under the ceiling rather than emptying the root: an
in-progress run's own scratch is the newest thing there, and wiping it wholesale
would break the very run that triggered the sweep.

Dry-run by default (AGENTS 5.1).

Usage
-----
    python scripts/utilities/prune_temp_root.py
    python scripts/utilities/prune_temp_root.py --execute
    python scripts/utilities/prune_temp_root.py --max-gb 1.0 --execute
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

_DEFAULT_MAX_GB = 2.0
_MAX_GB_BOUNDS = (0.1, 100.0)
_DEFAULT_TEMP_ROOT = ".data/tmp"
_DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"
_BYTES_PER_GB = 1_000_000_000  # decimal GB, matching how disks are sold


def _load_settings(config_path: Path | None = None) -> tuple[Path, float]:
    """Return (temp_root, max_gb). Bounded; warns and falls back on nonsense."""
    import yaml  # lazy, per project convention

    path = config_path or _DEFAULT_CONFIG_PATH
    block: dict[str, Any] = {}
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        raw = loaded.get("testing")
        if isinstance(raw, dict):
            block = raw
    except OSError as exc:
        print(f"[WARN] testing: could not read {path} ({exc}); using defaults.")

    configured = str(block.get("temp_root") or "").strip() or _DEFAULT_TEMP_ROOT
    temp_root = Path(configured)
    if not temp_root.is_absolute():
        temp_root = PROJECT_ROOT / temp_root

    raw_value = block.get("temp_root_max_gb", _DEFAULT_MAX_GB)
    try:
        max_gb = float(raw_value)
    except (TypeError, ValueError):
        print(f"[WARN] testing.temp_root_max_gb={raw_value!r} is not numeric; using {_DEFAULT_MAX_GB}.")
        return temp_root, _DEFAULT_MAX_GB
    lo, hi = _MAX_GB_BOUNDS
    if not (lo <= max_gb <= hi):
        print(f"[WARN] testing.temp_root_max_gb={max_gb} outside [{lo}, {hi}]; using {_DEFAULT_MAX_GB}.")
        return temp_root, _DEFAULT_MAX_GB
    return temp_root, max_gb


def _entry_size(path: Path) -> int:
    """Bytes owned by a top-level temp-root entry (file or directory)."""
    try:
        if path.is_file():
            return path.stat().st_size
        if not path.is_dir():
            return 0
    except OSError:
        return 0
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue  # a file vanishing mid-walk is normal in a temp tree
    return total


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def measure(temp_root: Path) -> int:
    """Total bytes currently under `temp_root` (0 when it does not exist)."""
    try:
        if not temp_root.is_dir():
            return 0
    except OSError:  # dangling link: is_dir() RAISES on Windows (AGENTS 5.5.1)
        return 0
    return sum(_entry_size(p) for p in temp_root.iterdir())


def prune(temp_root: Path, max_gb: float, *, execute: bool) -> dict[str, int]:
    """Delete oldest-mtime top-level entries until under `max_gb`.

    Scoped to exactly `temp_root`'s immediate children -- it never descends to
    delete, and never touches anything outside that directory. A sweep that
    guesses at "some temp dir" eventually deletes something it should not.
    """
    max_bytes = int(max_gb * _BYTES_PER_GB)
    try:
        if not temp_root.is_dir():
            return {"total_bytes": 0, "max_bytes": max_bytes, "deleted": 0, "deleted_bytes": 0}
    except OSError:
        return {"total_bytes": 0, "max_bytes": max_bytes, "deleted": 0, "deleted_bytes": 0}

    entries = [(p, _entry_size(p)) for p in temp_root.iterdir()]
    total_bytes = sum(size for _, size in entries)

    deleted = 0
    deleted_bytes = 0
    if total_bytes > max_bytes:
        entries.sort(key=lambda item: _mtime(item[0]))  # oldest first
        remaining = total_bytes
        for path, size in entries:
            if remaining <= max_bytes:
                break
            if execute:
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                except OSError as exc:
                    print(f"[WARN] could not delete {path}: {exc}")
                    continue
            deleted += 1
            deleted_bytes += size
            remaining -= size

    return {
        "total_bytes": total_bytes,
        "max_bytes": max_bytes,
        "deleted": deleted,
        "deleted_bytes": deleted_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-gb", type=float, default=None,
        help="Override config.yaml's testing.temp_root_max_gb for this run.",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually delete. Without this flag, only reports what would be deleted.",
    )
    args = parser.parse_args()

    temp_root, config_max_gb = _load_settings()
    max_gb = args.max_gb if args.max_gb is not None else config_max_gb

    result = prune(temp_root, max_gb, execute=False)
    if result["total_bytes"] <= result["max_bytes"]:
        print(
            f"{temp_root}: {result['total_bytes'] / _BYTES_PER_GB:.2f} GB, "
            f"under the {max_gb} GB ceiling. Nothing to prune."
        )
        return 0

    verb = "Deleting" if args.execute else "[DRY-RUN] Would delete"
    print(
        f"{verb} {result['deleted']} oldest entr(y/ies) "
        f"({result['deleted_bytes'] / _BYTES_PER_GB:.2f} GB) from {temp_root} "
        f"to bring it under {max_gb} GB (currently {result['total_bytes'] / _BYTES_PER_GB:.2f} GB)."
    )
    if args.execute:
        prune(temp_root, max_gb, execute=True)
    else:
        print("Re-run with --execute to actually delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
