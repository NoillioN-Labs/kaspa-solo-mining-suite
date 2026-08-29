"""No tracked text file carries a stray C0 control character (AGENTS 5.5.1).

Origin: Nineteen, five occurrences in one repository, one inside a governance
check. A lost escaping level turns a written ``\\b`` into an invisible backspace
byte (0x08) in source: the regex still compiles, matches nothing, and reports
green -- so the guard that carries the byte becomes a PASS caused by the defect
(AGENTS 4.1 axis 7). Editors render nothing at the site; only bytes tell.

The pack that delivered this guard supplied a fixture that itself carried the
defect class in reverse (a double-escaped ``\\\\n`` in its line-counting snippet),
so this implementation was rebuilt from the description and proven against a
deliberately planted byte below -- a malformed guard needs a malformed fixture.

Allowed: TAB (0x09), LF (0x0A), CR (0x0D). Everything else in 0x00-0x1F is a
finding. Binary files are excluded by a null-byte probe, never by extension
allow-lists (which grow blind spots for every new binary type).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_ALLOWED = {0x09, 0x0A, 0x0D}


def _stray_controls(data: bytes) -> list[tuple[int, int]]:
    """(line_number, byte_value) for every stray C0 byte in *data*."""
    findings: list[tuple[int, int]] = []
    line = 1
    for byte in data:
        if byte == 0x0A:
            line += 1
            continue
        if byte < 0x20 and byte not in _ALLOWED:
            findings.append((line, byte))
    return findings


def _tracked_files() -> list[str]:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files"],
        cwd=REPO,
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdout is not None, "git ls-files produced no stdout"
    return [ln for ln in proc.stdout.split("\n") if ln.strip()]


def test_no_tracked_text_file_carries_a_stray_control_character() -> None:
    files = _tracked_files()
    assert files, "git ls-files returned nothing - the check is inspecting nothing"

    offenders: list[str] = []
    examined = 0
    for rel in files:
        path = REPO / rel
        try:
            data = path.read_bytes()
        except OSError:
            continue  # deleted-but-staged etc.; not this check's business
        if b"\x00" in data[:8192]:
            continue  # binary, by content -- never by extension list
        examined += 1
        for line, byte in _stray_controls(data):
            offenders.append(f"{rel}:{line}: 0x{byte:02X}")

    assert examined > 0, "every tracked file read as binary - the probe is broken"
    assert not offenders, (
        "stray C0 control character(s) in tracked text - an invisible byte that "
        "compiles, matches nothing and reports green:\n  " + "\n  ".join(offenders)
    )


def test_the_guard_actually_fires_on_a_planted_byte(tmp_path: Path) -> None:
    """A malformed guard needs a malformed fixture: plant 0x08 and see it caught."""
    planted = b"PATTERN = re.compile(r'\x08oundary')\n"
    assert _stray_controls(planted) == [(1, 0x08)]


def test_legitimate_whitespace_is_not_a_finding() -> None:
    assert _stray_controls(b"a\tb\r\nnext line\n") == []


def test_line_numbers_are_computed_from_real_newlines() -> None:
    """The pack's own fixture failed here: a double-escaped newline made its
    line-counter count literal backslash-n sequences, not lines."""
    data = b"line one\nline two\x07\nline three\x1b\n"
    assert _stray_controls(data) == [(2, 0x07), (3, 0x1B)]


if __name__ == "__main__":
    sys.exit(0)
