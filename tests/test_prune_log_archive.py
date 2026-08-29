"""Unit tests for scripts/utilities/prune_log_archive.py.

260728: logs/archive/ grew unbounded (archive_session.py only ever moves
files in, never deletes) — this covers the age-based deletion logic and its
config-bounded retention loader.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "utilities"))

import prune_log_archive as pla  # noqa: E402


def _touch(path: Path, age_days: float) -> None:
    path.write_text("log line\n", encoding="utf-8")
    stamp = time.time() - age_days * 86400
    os.utime(path, (stamp, stamp))


def test_find_stale_files_respects_retention_window(tmp_path: Path) -> None:
    old = tmp_path / "hrt-closing-odds_260101_1200.log"
    recent = tmp_path / "hrt-closing-odds_260726_1200.log"
    _touch(old, age_days=45)
    _touch(recent, age_days=2)

    stale = pla.find_stale_files(tmp_path, retention_days=30)

    assert stale == [old]


def test_find_stale_files_missing_dir_returns_empty(tmp_path: Path) -> None:
    assert pla.find_stale_files(tmp_path / "does-not-exist", retention_days=30) == []


def test_find_stale_files_never_touches_dotfiles(tmp_path: Path) -> None:
    """260728 incident: the first version of this script deleted the
    git-tracked logs/archive/.keep sentinel on its very first real run —
    .gitignore whitelists it specifically so the directory survives a fresh
    clone despite `logs/*` being ignored."""
    keep = tmp_path / ".keep"
    gitkeep = tmp_path / ".gitkeep"
    _touch(keep, age_days=999)
    _touch(gitkeep, age_days=999)

    assert pla.find_stale_files(tmp_path, retention_days=30) == []


def test_find_stale_files_ignores_subdirectories(tmp_path: Path) -> None:
    sub = tmp_path / "nested"
    sub.mkdir()
    _touch(sub / "old.log", age_days=99)
    # only the subdirectory itself is old enough; it must not be treated as a file
    os.utime(sub, (time.time() - 99 * 86400, time.time() - 99 * 86400))

    assert pla.find_stale_files(tmp_path, retention_days=30) == []


def test_prune_dry_run_deletes_nothing(tmp_path: Path) -> None:
    old = tmp_path / "old.log"
    _touch(old, age_days=45)

    result = pla.prune(tmp_path, retention_days=30, execute=False)

    assert result == {"candidates": 1, "deleted": 0, "failed": 0}
    assert old.exists()


def test_prune_execute_deletes_stale_only(tmp_path: Path) -> None:
    old = tmp_path / "old.log"
    recent = tmp_path / "recent.log"
    _touch(old, age_days=45)
    _touch(recent, age_days=2)

    result = pla.prune(tmp_path, retention_days=30, execute=True)

    assert result == {"candidates": 1, "deleted": 1, "failed": 0}
    assert not old.exists()
    assert recent.exists()


def test_load_retention_days_default_when_config_missing(tmp_path: Path) -> None:
    assert pla._load_retention_days(tmp_path / "nope.yaml") == pla._DEFAULT_RETENTION_DAYS


def test_load_retention_days_reads_config(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("logging:\n  archive_retention_days: 60\n", encoding="utf-8")

    assert pla._load_retention_days(config) == 60


def test_load_retention_days_out_of_bounds_falls_back(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("logging:\n  archive_retention_days: 1\n", encoding="utf-8")

    assert pla._load_retention_days(config) == pla._DEFAULT_RETENTION_DAYS


def test_load_retention_days_non_numeric_falls_back(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("logging:\n  archive_retention_days: 'soon'\n", encoding="utf-8")

    assert pla._load_retention_days(config) == pla._DEFAULT_RETENTION_DAYS
