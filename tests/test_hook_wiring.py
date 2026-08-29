"""A registered governance hook must actually be able to execute.

The defect this guards against has no symptom. `.claude/settings.json` registered
`.venv\\Scripts\\python.exe .claude\\hooks\\write_guard.py`; the hook host runs that
string through a POSIX shell, which consumes `\\S` and `\\h` as escape sequences, so
the command becomes `.venvScriptspython.exe`, is not found, and the process exits
**127**. A PreToolUse hook blocks only on exit **2** -- every other status is treated
as allow. The guard therefore failed open on every single invocation, silently.

Measured 2026-08-16: 5 of 6 governed projects, including this master template, were
wired this way. Since `bootstrap_project.ps1` copies `.claude/` verbatim, every project
stamped from the master inherited inert guards on day one -- one defect copied N times,
not N mistakes.

No unit test of `write_boundary_check` could ever have caught this, because the rule
was never wrong. The wiring was, and wiring is not something a rule's tests can see.

Every test below builds its own configuration in `tmp_path`. **None reads this repo's
own adapter**, so a future adapter change cannot silently neuter them -- and equally,
these tests keep working in a clone whose adapter looks nothing like ours.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "utilities"))

import governance_lint  # noqa: E402


def _write_config(root: Path, command: str, *, directory: str = ".claude") -> Path:
    """Write a vendor hook configuration registering a single PreToolUse command."""
    config_dir = root / directory
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "settings.json"
    path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": command}]}
                    ]
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _errors(result: governance_lint.CheckResult) -> list[str]:
    return [f.message for f in result.findings if f.severity == governance_lint.SEVERITY_ERROR]


def test_a_backslash_command_is_an_error(tmp_path: Path) -> None:
    """The defect itself: the shell eats the separators and the hook never runs."""
    _write_config(tmp_path, ".venv\\Scripts\\python.exe .claude\\hooks\\write_guard.py")
    errors = _errors(governance_lint.check_hook_wiring(tmp_path))
    assert len(errors) == 1
    assert "backslash" in errors[0] and "127" in errors[0]


def test_a_forward_slash_command_is_clean(tmp_path: Path) -> None:
    """The fix. Windows accepts forward slashes throughout, so this is portable."""
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks" / "write_guard.py").write_text("", encoding="utf-8")
    _write_config(tmp_path, ".venv/Scripts/python.exe .claude/hooks/write_guard.py")
    assert _errors(governance_lint.check_hook_wiring(tmp_path)) == []


def test_a_missing_script_is_an_error(tmp_path: Path) -> None:
    """Correct separators are not enough; the script has to be there."""
    _write_config(tmp_path, "python .claude/hooks/does_not_exist.py")
    errors = _errors(governance_lint.check_hook_wiring(tmp_path))
    assert len(errors) == 1
    assert "does not exist" in errors[0]


def test_an_absent_venv_interpreter_is_not_an_error(tmp_path: Path) -> None:
    """The stated exemption (AGENTS 5.5.1), and it is load-bearing on CI.

    Environment directories are git-ignored and platform-specific: a Windows
    `.venv/Scripts/python.exe` is legitimately absent on a Linux runner. Checking it
    would fail the gate for a reason that is not the defect -- and a gate that cries
    wolf is one people learn to wave through.
    """
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks" / "write_guard.py").write_text("", encoding="utf-8")
    _write_config(tmp_path, ".venv/Scripts/python.exe .claude/hooks/write_guard.py")
    assert not (tmp_path / ".venv").exists(), "the interpreter must genuinely be absent"
    assert _errors(governance_lint.check_hook_wiring(tmp_path)) == []


def test_an_unparseable_command_is_an_error(tmp_path: Path) -> None:
    """Unbalanced quoting means the shell never runs it at all."""
    _write_config(tmp_path, "python 'unclosed .claude/hooks/write_guard.py")
    errors = _errors(governance_lint.check_hook_wiring(tmp_path))
    assert len(errors) == 1
    assert "cannot be parsed" in errors[0]


def test_invalid_json_errors_and_does_not_report_itself_as_skipped(tmp_path: Path) -> None:
    """A report that contradicts its own findings is worse than no report.

    Reporting `[SKIP] ... registers no hooks` while an ERROR has already been emitted
    is exactly the shape that lets a broken gate read as an inactive one.
    """
    config_dir = tmp_path / ".claude"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.json").write_text("{ not json", encoding="utf-8")
    result = governance_lint.check_hook_wiring(tmp_path)
    assert len(_errors(result)) == 1
    assert result.skipped is False, "an ERROR was emitted; this cannot also be a SKIP"


def test_no_adapter_and_an_adapter_without_hooks_both_skip(tmp_path: Path) -> None:
    """Two genuinely-nothing-to-say cases, each skipping with a reason."""
    empty = governance_lint.check_hook_wiring(tmp_path)
    assert empty.skipped is True and "no vendor hook configuration" in empty.skip_reason

    vscode = tmp_path / ".vscode"
    vscode.mkdir()
    (vscode / "settings.json").write_text(json.dumps({"python.defaultInterpreter": "x"}), encoding="utf-8")
    hookless = governance_lint.check_hook_wiring(tmp_path)
    assert hookless.skipped is True and "registers no hooks" in hookless.skip_reason


def test_every_broken_hook_is_flagged_not_just_the_first(tmp_path: Path) -> None:
    """Reporting one of three teaches that fixing one is enough."""
    config_dir = tmp_path / ".claude"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {"hooks": [{"type": "command", "command": "a\\b.py"}]},
                        {"hooks": [{"type": "command", "command": "c\\d.py"}]},
                    ],
                    "Stop": [{"hooks": [{"type": "command", "command": "e\\f.py"}]}],
                }
            }
        ),
        encoding="utf-8",
    )
    assert len(_errors(governance_lint.check_hook_wiring(tmp_path))) == 3


def test_single_quoted_backslashes_are_allowed_but_double_quoted_are_not(tmp_path: Path) -> None:
    r"""Inside single quotes a backslash is literal; inside double quotes it is not.

    A shell-pipeline hook running `grep -qE '\.env'` is CORRECT and must not be failed
    -- hard-failing it is how a check gets disabled. A double-quoted Windows path is
    still the defect, because POSIX sh keeps the backslash special there.
    """
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks" / "guard.sh").write_text("", encoding="utf-8")
    _write_config(tmp_path, ".claude/hooks/guard.sh | grep -qE '\\.env'")
    assert _errors(governance_lint.check_hook_wiring(tmp_path)) == []

    _write_config(tmp_path, 'python ".venv\\Scripts\\python.exe"')
    errors = _errors(governance_lint.check_hook_wiring(tmp_path))
    assert len(errors) == 1 and "backslash" in errors[0]


def test_a_bare_script_name_is_still_existence_checked(tmp_path: Path) -> None:
    """The fail-open, hiding inside its own remedy.

    The hook host runs from the project root, so a bare `guard.py` IS a real
    repo-relative path. Checking only tokens containing "/" would wave through
    `python guard_missing.py` -- a hook that exits non-zero and fails open, passing a
    check written to catch exactly that.
    """
    _write_config(tmp_path, "python guard_missing.py")
    errors = _errors(governance_lint.check_hook_wiring(tmp_path))
    assert len(errors) == 1 and "does not exist" in errors[0]

    # ...while a bare PATH command with no script suffix is correctly left alone.
    _write_config(tmp_path, "ruff check .")
    assert _errors(governance_lint.check_hook_wiring(tmp_path)) == []


def test_a_posix_absolute_interpreter_does_not_error_on_windows(tmp_path: Path) -> None:
    """`Path("/usr/bin/python3").is_absolute()` is FALSE on Windows.

    Without the explicit POSIX-form test the token would be joined onto the repo root,
    ERRORing on a dev machine while passing on a Linux runner -- a check whose verdict
    depends on where it runs.
    """
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks" / "write_guard.py").write_text("", encoding="utf-8")
    _write_config(tmp_path, "/usr/bin/python3 .claude/hooks/write_guard.py")
    assert _errors(governance_lint.check_hook_wiring(tmp_path)) == []
