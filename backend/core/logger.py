"""
Centralized structured logging (structlog) with automatic log archiving.

Implements the Log Archiving Protocol defined in AGENTS.md § 4.5 and the
Telemetry rules in _bmad-output/project-context.md § 5.6:

* Two log streams:
    1. Pipeline processing log  -> ``<prefix>_YYMMDD_HHMM.log``
    2. Hardware performance log -> ``<prefix>_hardware_YYMMDD_HHMM.log``
* File output is JSON lines (one JSON object per line: ``timestamp``
  ISO-8601, ``level``, ``event``, plus any bound key-values). Console
  output is human-readable plain ASCII.
* On every ``initialize_logging`` call the logger sweeps any pre-existing
  ``*.log`` files out of the active ``logs/`` directory into
  ``logs/archive/`` BEFORE opening the new timestamped log file. This
  guarantees the active ``logs/`` directory only ever contains log files
  from the current run. Archive name collisions are resolved with a
  monotonic counter suffix (``name_001.log``, ``name_002.log``, ...).
* A NAMED logger hierarchy (``neon.<prefix>``) is used with
  ``propagate=False``; the root logger's handlers and level are never
  touched, so pytest capture and host applications are unaffected.
  Re-initialization in the same process closes previously-owned handlers
  first (no duplicate handlers, no leaked file descriptors).

Paths are resolved from ``config.yaml`` (``paths.logs_dir`` and
``paths.log_archive_dir``). PyYAML is used when available; otherwise a
minimal built-in parser extracts just those two values so the logger
remains functional during bootstrap or in constrained environments.
``psutil`` is optional: if missing, the hardware stream logs a single
warning to the pipeline log and becomes a no-op.

The module is import-safe: importing it has no side effects.

Public API:
    initialize_logging(prefix="pipeline", level=logging.INFO,
                       config_path=None, console=True)
        -> structlog.stdlib.BoundLogger
    start_hardware_log(interval_sec=30.0) -> bool
    stop_hardware_log() -> None
    hardware_log(interval_sec=30.0)   # context manager wrapping the above
    shutdown_logging() -> None
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import IO, Any

import structlog
from structlog.typing import Processor

try:
    import psutil
except ImportError:  # pragma: no cover - exercised via monkeypatch in tests
    psutil = None  # type: ignore[assignment]

# --- Defaults (used when config.yaml is missing or unreadable) ---
_DEFAULT_LOGS_DIR = "logs"
_DEFAULT_ARCHIVE_DIR = "logs/archive"
_DEFAULT_CONFIG_PATH = "config.yaml"

# Namespace for the stdlib loggers this module owns. Everything lives
# under "neon.*" so the root logger is never configured or touched.
_LOGGER_NAMESPACE = "neon"

# --- Module state (pipeline stream) ---
_state_lock = threading.RLock()
_state: dict[str, Any] = {
    "stdlib_logger": None,  # logging.Logger we attached handlers to
    "handlers": [],  # handlers owned by this module
    "bound_logger": None,  # last BoundLogger returned by initialize_logging
    "prefix": None,
    "timestamp": None,  # YYMMDD_HHMM stamp of the current run
    "logs_dir": None,
    "psutil_warned": False,
}

# --- Module state (hardware stream) ---
_hw_lock = threading.RLock()
_hw_thread: threading.Thread | None = None
_hw_stop_event: threading.Event | None = None
_hw_file: IO[str] | None = None


def _project_root() -> Path:
    """Return the project root: parent of `backend/`."""
    return Path(__file__).resolve().parent.parent.parent


def _parse_paths_with_yaml(config_path: Path) -> tuple[str, str] | None:
    """Try PyYAML; return (logs_dir, archive_dir) or None if PyYAML unavailable."""
    try:
        import yaml
    except ImportError:
        return None
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        paths = data.get("paths", {}) or {}
        logs_dir = paths.get("logs_dir", _DEFAULT_LOGS_DIR)
        archive_dir = paths.get("log_archive_dir", _DEFAULT_ARCHIVE_DIR)
        return str(logs_dir), str(archive_dir)
    except Exception:
        return None


def _parse_paths_fallback(config_path: Path) -> tuple[str, str]:
    """
    Minimal hand-rolled parser for the two `paths:` values we care about.
    Used when PyYAML is unavailable or config.yaml fails to load via yaml.

    Recognises the simple YAML pattern:
        paths:
          logs_dir: "logs/"
          log_archive_dir: "logs/archive/"
    """
    logs_dir = _DEFAULT_LOGS_DIR
    archive_dir = _DEFAULT_ARCHIVE_DIR
    if not config_path.exists():
        return logs_dir, archive_dir

    try:
        text = config_path.read_text(encoding="utf-8")
    except Exception:
        return logs_dir, archive_dir

    in_paths_block = False
    # Capture top-level "paths:" mapping; stop at next top-level key.
    for raw_line in text.splitlines():
        # Strip inline comments and trailing whitespace, keep leading indent.
        line = re.sub(r"\s+#.*$", "", raw_line).rstrip()
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            # Top-level key. Enter paths block iff key is `paths:`.
            in_paths_block = line.strip().rstrip(":") == "paths"
            continue
        if not in_paths_block:
            continue
        m = re.match(r"\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip().strip('"').strip("'")
        if key == "logs_dir" and value:
            logs_dir = value
        elif key == "log_archive_dir" and value:
            archive_dir = value
    return logs_dir, archive_dir


def _resolve_log_paths(config_path: Path | None = None) -> tuple[Path, Path]:
    """Resolve absolute paths for logs/ and logs/archive/ from config (with fallbacks)."""
    root = _project_root()
    cfg = config_path or (root / _DEFAULT_CONFIG_PATH)

    parsed = _parse_paths_with_yaml(cfg) if cfg.exists() else None
    if parsed is None:
        logs_str, archive_str = _parse_paths_fallback(cfg)
    else:
        logs_str, archive_str = parsed

    logs_dir = Path(logs_str)
    archive_dir = Path(archive_str)
    if not logs_dir.is_absolute():
        logs_dir = (root / logs_dir).resolve()
    if not archive_dir.is_absolute():
        archive_dir = (root / archive_dir).resolve()
    return logs_dir, archive_dir


def _archive_stale_logs(logs_dir: Path, archive_dir: Path) -> int:
    """
    Sweep all pre-existing `*.log` files from `logs_dir` into `archive_dir`.

    Returns the count of files moved. Subdirectories (including the archive
    folder itself) are not touched. Archive name collisions are resolved
    with a monotonic counter suffix (`name_001.log`, `name_002.log`, ...)
    so rapid successive sweeps never overwrite an archived file. Silently
    skips files that cannot be moved (e.g. locked by another process) and
    prints a single warning to stderr per failure so the new run can still
    start.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    for entry in logs_dir.iterdir():
        if not entry.is_file() or entry.suffix.lower() != ".log":
            continue
        try:
            dest = archive_dir / entry.name
            counter = 1
            while dest.exists():
                dest = archive_dir / f"{entry.stem}_{counter:03d}{entry.suffix}"
                counter += 1
            shutil.move(str(entry), str(dest))
            moved += 1
        except Exception as exc:  # pragma: no cover - defensive
            sys.stderr.write(f"[logger] WARNING: could not archive {entry.name}: {exc}\n")
    return moved


def _build_pre_chain() -> list[Processor]:
    """Shared structlog processors applied before rendering (both streams/handlers)."""
    return [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def _detach_owned_handlers() -> None:
    """Close and detach every handler this module previously attached."""
    stdlib_logger: logging.Logger | None = _state.get("stdlib_logger")
    for handler in list(_state.get("handlers", [])):
        if stdlib_logger is not None:
            stdlib_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # pragma: no cover - defensive
            pass
    _state["handlers"] = []


def initialize_logging(
    prefix: str = "pipeline",
    level: int = logging.INFO,
    config_path: Path | None = None,
    console: bool = True,
) -> structlog.stdlib.BoundLogger:
    """
    Initialize the structured pipeline logger for the current execution.

    1. Resolves `logs_dir` and `log_archive_dir` from config.yaml (with
       safe defaults).
    2. Sweeps stale `*.log` files from `logs_dir` into `log_archive_dir`
       (collision-safe via a monotonic counter suffix).
    3. Opens a fresh timestamped JSON-lines log file
       `<prefix>_YYMMDD_HHMM.log` and attaches a file handler (JSON) and
       an optional console handler (human-readable, ASCII) to the NAMED
       logger `neon.<prefix>`. The root logger is never modified.

    Re-initialization in the same process closes the previously-owned
    handlers first, so no handlers are duplicated and no file descriptors
    leak. Any running hardware log is stopped first so its file can be
    swept into the archive.

    Args:
        prefix: Stem for the new log file (e.g. "pipeline_smoke_test").
        level: Logging level for the named logger and its handlers.
        config_path: Optional override for config.yaml location (mainly tests).
        console: Attach a human-readable stdout handler (default True).

    Returns:
        A `structlog` BoundLogger. Supports both structured calls
        (`log.info("event", key=value)`) and stdlib-style %-formatting
        (`log.info("msg %s", arg)`), plus `.bind(**kv)` for context.
    """
    with _state_lock:
        # Release the hardware log file handle (if any) so the sweep below
        # can move it; a fresh hardware stream can be started afterwards.
        stop_hardware_log()

        logs_dir, archive_dir = _resolve_log_paths(config_path)
        archived_count = _archive_stale_logs(logs_dir, archive_dir)

        timestamp = datetime.now().strftime("%y%m%d_%H%M")
        log_file = logs_dir / f"{prefix}_{timestamp}.log"

        # Drop handlers from any previous initialization (same or different
        # prefix) BEFORE attaching new ones: no duplicates, no leaked FDs.
        _detach_owned_handlers()

        stdlib_logger = logging.getLogger(f"{_LOGGER_NAMESPACE}.{prefix}")
        stdlib_logger.setLevel(level)
        stdlib_logger.propagate = False  # never bubble to the root logger

        pre_chain = _build_pre_chain()

        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(default=str),
                ],
                foreign_pre_chain=pre_chain,
            )
        )
        handlers: list[logging.Handler] = [file_handler]

        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(
                structlog.stdlib.ProcessorFormatter(
                    processors=[
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        structlog.dev.ConsoleRenderer(colors=False),
                    ],
                    foreign_pre_chain=pre_chain,
                )
            )
            handlers.append(console_handler)

        for handler in handlers:
            stdlib_logger.addHandler(handler)

        bound: structlog.stdlib.BoundLogger = structlog.wrap_logger(
            stdlib_logger,
            processors=[*pre_chain, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
            wrapper_class=structlog.stdlib.BoundLogger,
        ).bind()

        _state.update(
            stdlib_logger=stdlib_logger,
            handlers=handlers,
            bound_logger=bound,
            prefix=prefix,
            timestamp=timestamp,
            logs_dir=logs_dir,
        )

        bound.info(
            "logger_initialized",
            log_file=str(log_file),
            archived_stale_files=archived_count,
            archive_dir=str(archive_dir),
        )
        return bound


def shutdown_logging() -> None:
    """
    Stop the hardware stream and close/detach all owned handlers.

    Safe to call multiple times. Mainly useful for tests and orderly
    process shutdown; a fresh `initialize_logging` call performs the same
    cleanup implicitly.
    """
    with _state_lock:
        stop_hardware_log()
        _detach_owned_handlers()
        _state.update(
            stdlib_logger=None,
            bound_logger=None,
            prefix=None,
            timestamp=None,
            logs_dir=None,
        )


# ---------------------------------------------------------------------------
# Hardware performance log (second stream)
# ---------------------------------------------------------------------------


def _warn_psutil_missing() -> None:
    """Log a single warning (per process) that hardware telemetry is disabled."""
    if _state.get("psutil_warned"):
        return
    _state["psutil_warned"] = True
    bound = _state.get("bound_logger")
    message = "psutil is not installed; hardware telemetry disabled"
    if bound is not None:
        bound.warning("hardware_log_unavailable", reason=message)
    else:  # pragma: no cover - defensive
        sys.stderr.write(f"[logger] WARNING: {message}\n")


def _hardware_snapshot() -> dict[str, Any]:
    """Collect one cheap psutil snapshot as a JSON-serializable dict."""
    snapshot: dict[str, Any] = {
        "timestamp": datetime.now().astimezone().isoformat(),
        "level": "info",
        "event": "hardware_snapshot",
    }
    try:
        snapshot["cpu_percent"] = psutil.cpu_percent(interval=None)
        snapshot["memory_percent"] = psutil.virtual_memory().percent
    except Exception as exc:  # pragma: no cover - defensive
        snapshot["error"] = str(exc)
    try:
        io_counters = psutil.disk_io_counters()
        if io_counters is not None:
            snapshot["disk_read_bytes"] = io_counters.read_bytes
            snapshot["disk_write_bytes"] = io_counters.write_bytes
    except Exception:  # pragma: no cover - not available on all platforms
        pass
    return snapshot


def _hardware_worker(log_file: IO[str], stop_event: threading.Event, interval_sec: float) -> None:
    """Daemon-thread loop: write one JSON snapshot line per interval."""
    try:
        psutil.cpu_percent(interval=None)  # prime the CPU counter
    except Exception:  # pragma: no cover - defensive
        pass
    while True:
        try:
            log_file.write(json.dumps(_hardware_snapshot(), default=str) + "\n")
            log_file.flush()
        except ValueError:  # pragma: no cover - file closed underneath us
            break
        if stop_event.wait(interval_sec):
            break


def start_hardware_log(interval_sec: float = 30.0) -> bool:
    """
    Start the hardware performance log stream (second telemetry stream).

    Writes periodic psutil snapshots (cpu %, mem %, disk io counters) as
    JSON lines to `<prefix>_hardware_YYMMDD_HHMM.log` in the same logs
    directory as the pipeline log, via a daemon thread. The first snapshot
    is written immediately; subsequent ones every `interval_sec` seconds.

    Uses the prefix/timestamp/logs_dir from the most recent
    `initialize_logging` call (falling back to "pipeline" and config.yaml
    resolution if logging was never initialized). Idempotent: calling
    while already running is a no-op that returns True.

    Returns:
        True if the stream is running; False if psutil is unavailable
        (a single warning is logged to the pipeline log in that case).
    """
    global _hw_thread, _hw_stop_event, _hw_file
    with _hw_lock:
        if _hw_thread is not None and _hw_thread.is_alive():
            return True
        if psutil is None:
            _warn_psutil_missing()
            return False

        logs_dir: Path = _state.get("logs_dir") or _resolve_log_paths()[0]
        prefix: str = _state.get("prefix") or "pipeline"
        timestamp: str = _state.get("timestamp") or datetime.now().strftime("%y%m%d_%H%M")
        logs_dir.mkdir(parents=True, exist_ok=True)
        hw_path = logs_dir / f"{prefix}_hardware_{timestamp}.log"

        _hw_file = hw_path.open("a", encoding="utf-8")
        _hw_stop_event = threading.Event()
        _hw_thread = threading.Thread(
            target=_hardware_worker,
            args=(_hw_file, _hw_stop_event, interval_sec),
            name="neon-hardware-log",
            daemon=True,
        )
        _hw_thread.start()
        return True


def stop_hardware_log() -> None:
    """
    Stop the hardware performance log stream and close its file handle.

    Safe to call multiple times / when the stream was never started.
    """
    global _hw_thread, _hw_stop_event, _hw_file
    with _hw_lock:
        if _hw_stop_event is not None:
            _hw_stop_event.set()
        if _hw_thread is not None:
            _hw_thread.join(timeout=5.0)
        if _hw_file is not None:
            try:
                _hw_file.close()
            except Exception:  # pragma: no cover - defensive
                pass
        _hw_thread = None
        _hw_stop_event = None
        _hw_file = None


@contextmanager
def hardware_log(interval_sec: float = 30.0) -> Iterator[bool]:
    """
    Context manager wrapping `start_hardware_log` / `stop_hardware_log`.

    Yields True if the stream started (psutil available), False otherwise.
    """
    started = start_hardware_log(interval_sec)
    try:
        yield started
    finally:
        stop_hardware_log()
