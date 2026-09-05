"""
Unit tests for backend.core.logger (structured logging + log archiving).

All tests run against a temporary logs directory (tmp_path) via a
per-test config.yaml override; the repository's real logs/ folder is
never touched.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure the project root is importable when pytest inserts tests/ only.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.core import logger as logger_mod  # noqa: E402

_LOG_NAME_RE = re.compile(r"^[a-z]+_\d{6}_\d{4}\.log$")


def _read_json_lines(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@pytest.fixture()
def log_env(tmp_path: Path) -> Iterator[SimpleNamespace]:
    """Isolated logs/archive dirs plus a config.yaml pointing at them."""
    logs_dir = tmp_path / "logs"
    archive_dir = logs_dir / "archive"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "paths:\n"
        f'  logs_dir: "{logs_dir.as_posix()}"\n'
        f'  log_archive_dir: "{archive_dir.as_posix()}"\n',
        encoding="utf-8",
    )
    try:
        yield SimpleNamespace(
            logs_dir=logs_dir,
            archive_dir=archive_dir,
            config_path=config_path,
        )
    finally:
        logger_mod.shutdown_logging()


def test_sweep_moves_stale_logs_to_archive(log_env: SimpleNamespace) -> None:
    log_env.logs_dir.mkdir(parents=True)
    (log_env.logs_dir / "old_run.log").write_text("stale one", encoding="utf-8")
    (log_env.logs_dir / "older_run.log").write_text("stale two", encoding="utf-8")
    (log_env.logs_dir / "not_a_log.txt").write_text("keep me", encoding="utf-8")

    logger_mod.initialize_logging("sweeptest", config_path=log_env.config_path)

    # Stale .log files moved into archive/; non-.log files untouched.
    assert not (log_env.logs_dir / "old_run.log").exists()
    assert not (log_env.logs_dir / "older_run.log").exists()
    assert (log_env.archive_dir / "old_run.log").read_text(encoding="utf-8") == "stale one"
    assert (log_env.archive_dir / "older_run.log").read_text(encoding="utf-8") == "stale two"
    assert (log_env.logs_dir / "not_a_log.txt").exists()

    # Exactly one fresh timestamped log file remains in the active dir.
    live_logs = list(log_env.logs_dir.glob("*.log"))
    assert len(live_logs) == 1
    assert _LOG_NAME_RE.match(live_logs[0].name), live_logs[0].name
    assert live_logs[0].name.startswith("sweeptest_")

    # The init event records the sweep count.
    records = _read_json_lines(live_logs[0])
    init_events = [r for r in records if r["event"] == "logger_initialized"]
    assert len(init_events) == 1
    assert init_events[0]["archived_stale_files"] == 2


def test_archive_collisions_get_unique_counter_suffixes(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    archive_dir = logs_dir / "archive"
    archive_dir.mkdir(parents=True)
    (archive_dir / "run.log").write_text("first", encoding="utf-8")
    (archive_dir / "run_001.log").write_text("second", encoding="utf-8")
    (logs_dir / "run.log").write_text("third", encoding="utf-8")

    moved = logger_mod._archive_stale_logs(logs_dir, archive_dir)

    assert moved == 1
    # Existing archived files are never overwritten...
    assert (archive_dir / "run.log").read_text(encoding="utf-8") == "first"
    assert (archive_dir / "run_001.log").read_text(encoding="utf-8") == "second"
    # ...and the colliding file lands under the next counter suffix.
    assert (archive_dir / "run_002.log").read_text(encoding="utf-8") == "third"
    assert not (logs_dir / "run.log").exists()


def test_file_output_is_json_lines_with_expected_keys(
    log_env: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    log = logger_mod.initialize_logging("jsontest", config_path=log_env.config_path)
    log.info("plain_event", foo="bar", answer=42)
    log.bind(run_id="abc123").warning("bound_event")
    log.info("percent style %s and %d", "text", 7)  # stdlib-style args still work

    log_file = next(log_env.logs_dir.glob("jsontest_*.log"))
    records = _read_json_lines(log_file)
    assert len(records) == 4  # init + 3 emitted above

    for record in records:
        assert {"timestamp", "level", "event"} <= set(record)
        datetime.fromisoformat(record["timestamp"])  # ISO-8601 parseable

    by_event = {r["event"]: r for r in records}
    assert by_event["plain_event"]["foo"] == "bar"
    assert by_event["plain_event"]["answer"] == 42
    assert by_event["plain_event"]["level"] == "info"
    assert by_event["bound_event"]["run_id"] == "abc123"
    assert by_event["bound_event"]["level"] == "warning"
    assert by_event["percent style text and 7"]["level"] == "info"

    # Console output is human-readable (not JSON) and pure ASCII.
    out = capsys.readouterr().out
    assert "plain_event" in out
    assert not out.lstrip().startswith("{")
    out.encode("ascii")  # raises UnicodeEncodeError if non-ASCII


def test_reinitialization_does_not_duplicate_handlers_or_leak_fds(
    log_env: SimpleNamespace,
) -> None:
    logger_mod.initialize_logging("reinit", config_path=log_env.config_path)
    stdlib_logger = logging.getLogger("neon.reinit")
    first_handlers = list(stdlib_logger.handlers)
    assert len(first_handlers) == 2  # file + console
    first_file_handler = next(h for h in first_handlers if isinstance(h, logging.FileHandler))

    log2 = logger_mod.initialize_logging("reinit", config_path=log_env.config_path)

    # Same handler count, and all old handlers were replaced (not stacked).
    assert len(stdlib_logger.handlers) == 2
    assert all(h not in first_handlers for h in stdlib_logger.handlers)
    # The first file handler's stream was closed (no FD leak)...
    assert first_file_handler.stream is None or first_file_handler.stream.closed
    # ...which is proven by the sweep: the first run's file was movable
    # (not locked) and now lives in archive/, leaving exactly one live log.
    assert len(list(log_env.logs_dir.glob("reinit_*.log"))) == 1
    assert len(list(log_env.archive_dir.glob("reinit_*.log"))) >= 1

    # A message after re-init is emitted exactly once (no duplicates).
    log2.info("after_reinit")
    live = next(log_env.logs_dir.glob("reinit_*.log"))
    events = [r["event"] for r in _read_json_lines(live)]
    assert events.count("after_reinit") == 1


def test_root_logger_is_untouched(log_env: SimpleNamespace) -> None:
    root = logging.getLogger()
    handlers_before = list(root.handlers)
    level_before = root.level

    log = logger_mod.initialize_logging("roottest", config_path=log_env.config_path)
    log.info("root_check")
    logger_mod.shutdown_logging()

    assert list(root.handlers) == handlers_before
    assert root.level == level_before
    # The named logger never propagates into the root/pytest handlers.
    assert logging.getLogger("neon.roottest").propagate is False


@pytest.mark.skipif(logger_mod.psutil is None, reason="psutil not installed")
def test_hardware_log_writes_json_snapshots(log_env: SimpleNamespace) -> None:
    logger_mod.initialize_logging("hwtest", config_path=log_env.config_path)

    with logger_mod.hardware_log(interval_sec=0.05) as started:
        assert started is True
        # Idempotent while running.
        assert logger_mod.start_hardware_log(interval_sec=0.05) is True
        time.sleep(0.3)

    hw_files = list(log_env.logs_dir.glob("hwtest_hardware_*.log"))
    assert len(hw_files) == 1
    assert re.fullmatch(r"hwtest_hardware_\d{6}_\d{4}\.log", hw_files[0].name)

    records = _read_json_lines(hw_files[0])
    assert records, "expected at least one hardware snapshot"
    for record in records:
        assert record["event"] == "hardware_snapshot"
        assert record["level"] == "info"
        datetime.fromisoformat(record["timestamp"])
        assert isinstance(record["cpu_percent"], (int, float))
        assert isinstance(record["memory_percent"], (int, float))

    # stop is idempotent.
    logger_mod.stop_hardware_log()


def test_hardware_log_noops_without_psutil(
    log_env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger_mod.initialize_logging("nopsutil", config_path=log_env.config_path)
    monkeypatch.setattr(logger_mod, "psutil", None)
    monkeypatch.setitem(logger_mod._state, "psutil_warned", False)

    assert logger_mod.start_hardware_log(interval_sec=0.01) is False
    logger_mod.stop_hardware_log()  # harmless no-op

    # No hardware file was created.
    assert list(log_env.logs_dir.glob("nopsutil_hardware_*.log")) == []

    # Exactly one warning went to the pipeline log (even on repeat attempts).
    assert logger_mod.start_hardware_log(interval_sec=0.01) is False
    pipeline_file = next(log_env.logs_dir.glob("nopsutil_*.log"))
    records = _read_json_lines(pipeline_file)
    warnings = [r for r in records if r["event"] == "hardware_log_unavailable"]
    assert len(warnings) == 1
    assert warnings[0]["level"] == "warning"
