"""
scripts/utilities/backup_db.py
==============================

Online SQLite backup, using the sqlite3 backup API so the database can be copied
**while it is being written to** -- a filesystem copy of a live SQLite file can
capture a torn page and produce a backup that only fails when you try to restore
it.

Produces `<prefix>_<YYYYMMDD>_<HHMMSS>.db` in the configured backup directory, then
applies the retention policy from `prune_db_backups.py`.

THE PRODUCER AND THE PRUNER SHARE ONE CONFIG BLOCK ON PURPOSE. Both read
`database_backups.filename_prefix`, so the convention the pruner keys on is the
convention the producer writes. Split them and you get a pruner that silently
matches nothing -- it reports "no candidates", looks healthy, and the directory
grows forever.

Inert until the project HAS a database: with `database_backups.db_path` unset or
missing, this reports that and exits non-zero rather than pretending to succeed.

Usage
-----
    python scripts/utilities/backup_db.py
    python scripts/utilities/backup_db.py --db-path .data/app.db --no-prune
"""

from __future__ import annotations

import argparse
import datetime
import logging
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prune_db_backups import _load_config  # noqa: E402
from prune_db_backups import prune as prune_backups  # noqa: E402


def _emit(message: str, logger: logging.Logger | None, level: str = "info") -> None:
    if logger:
        getattr(logger, level)(message)
    else:
        prefix = {"info": "", "warning": "Warning: ", "error": "Error: "}[level]
        print(f"{prefix}{message}")


def backup(
    db_path: Path | None = None,
    logger: logging.Logger | None = None,
    *,
    prune: bool = True,
) -> Path:
    """Create a timestamped online backup and return the path written.

    Returns the backup path rather than None so a caller can verify, stage or log
    the artefact it actually produced (AGENTS 4.1: the artifact produced is the
    artifact you claim).
    """
    config = _load_config()
    prefix = config["filename_prefix"]

    if db_path is None:
        configured = str(config.get("db_path") or "").strip()
        if not configured:
            raise ValueError(
                "database_backups.db_path is not set in config.yaml; nothing to back up. "
                "Set it, or pass --db-path."
            )
        db_path = Path(configured)
    db_path = Path(db_path)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path

    if not db_path.exists():
        message = f"Database file not found at {db_path}"
        _emit(message, logger, "error")
        raise FileNotFoundError(message)

    configured_dir = Path(config["backup_dir"])
    backup_dir = configured_dir if configured_dir.is_absolute() else PROJECT_ROOT / configured_dir
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"{prefix}_{stamp}.db"

    _emit(f"Starting online backup to {backup_file.name}...", logger)
    source = sqlite3.connect(str(db_path))
    try:
        destination = sqlite3.connect(str(backup_file))
        try:
            with destination:
                source.backup(destination)
        finally:
            destination.close()
    except Exception as exc:
        # Do not leave a half-written file that looks like a restore point.
        backup_file.unlink(missing_ok=True)
        _emit(f"Error during backup: {exc}", logger, "error")
        raise
    finally:
        source.close()

    _emit(f"Backup created successfully: {backup_file.name}", logger)

    if prune:
        # A prune failure must not invalidate a backup that already succeeded, but it
        # must be VISIBLE -- silently skipping retention is how a disk fills up.
        try:
            result = prune_backups(
                backup_dir,
                daily_count=config["daily_count"],
                weekly_count=config["weekly_count"],
                execute=True,
                filename_prefix=prefix,
            )
            if result["deleted"]:
                _emit(
                    f"Pruned {result['deleted']} old backup(s) under the "
                    f"{config['daily_count']}/day + {config['weekly_count']}/week policy.",
                    logger,
                )
            if result["failed"]:
                _emit(
                    f"{result['failed']} backup(s) could not be pruned; see warnings above.",
                    logger,
                    "warning",
                )
        except Exception as exc:  # noqa: BLE001 - retention must never lose a good backup
            _emit(f"Failed to prune old backups: {exc}", logger, "warning")

    return backup_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default=None, help="Override database_backups.db_path")
    parser.add_argument(
        "--no-prune", action="store_true", help="Create the backup without applying retention"
    )
    args = parser.parse_args(argv)

    try:
        written = backup(
            Path(args.db_path) if args.db_path else None,
            prune=not args.no_prune,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"[OK] {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
