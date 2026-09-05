"""The TEMPLATE must carry every capability a future project could need.

This repo is the Golden Image (AGENTS 11): projects are stamped from it, so a
mechanism absent here is absent from every project that will ever exist. That makes
"this repo does not currently need it" the WRONG test -- the right one is "could a
project stamped from this ever need it?".

These tests exist because that distinction was got wrong once. Four upgrade packs
were applied with a project lens ("no database in this repo, so skip the retention
script"), which would have shipped a template silently unable to handle a database,
an expensive CI suite, or an unscoped temp directory -- and every project cloned
from it would have inherited the hole.
"""

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "utilities"))
sys.path.insert(0, str(REPO))

import prune_db_backups  # noqa: E402

# ---------------------------------------------------------------------------
# Push-cost guard (github_actions_cost_controls S5.2 / S5.3)
# ---------------------------------------------------------------------------

HOOK = REPO / "scripts" / "hooks" / "pre-push"
ZERO = "0" * 40
SHA_A, SHA_B = "1" * 40, "2" * 40


def _run_hook(ref_line: str, env_extra: dict[str, str] | None = None) -> int:
    env = {"PATH": "/usr/bin:/bin"}
    env.update(env_extra or {})
    proc = subprocess.run(
        ["sh", str(HOOK)],
        input=ref_line,
        text=True,
        capture_output=True,
        cwd=str(REPO),
        env=env,
    )
    return proc.returncode


def test_push_guard_ships_with_its_installer() -> None:
    assert HOOK.is_file(), "the template must SHIP the push-cost guard, not just describe it"
    assert (REPO / "scripts" / "utilities" / "install_git_hooks.py").is_file(), (
        "core.hooksPath is LOCAL config that cannot be committed -- without an "
        "installer the guard is silently absent on every fresh clone, which is the "
        "same failure shape as the dark CI gate it exists to prevent"
    )


def test_push_guard_is_pure_ascii_and_parses_under_sh() -> None:
    """It runs under Git for Windows' sh; a stray non-ASCII byte is a lost afternoon."""
    assert all(b < 128 for b in HOOK.read_bytes()), "pre-push must be pure ASCII (AGENTS 5.5.1)"
    assert subprocess.run(["sh", "-n", str(HOOK)], capture_output=True).returncode == 0


def test_hooks_are_pinned_to_LF_line_endings() -> None:
    """git executes hooks DIRECTLY via their shebang, where a trailing CR is fatal.

    Under `core.autocrlf=true` git would check the hook out CRLF and the shebang
    becomes `/bin/sh^M` -- "bad interpreter" -- so the hook does not run at all and
    the guard is silently absent on someone else's clone. Invoking the same file as
    `sh <file>` tolerates the CRs, so this never reproduces in casual testing; only
    a .gitattributes pin prevents it.
    """
    assert b"\r" not in HOOK.read_bytes(), "the working-tree hook must be LF-only"
    attrs = (REPO / ".gitattributes").read_text(encoding="utf-8")
    assert "scripts/hooks/** text eol=lf" in attrs, (
        "without this pin git re-introduces CRLF on every fresh clone"
    )
    resolved = subprocess.run(
        ["git", "check-attr", "eol", "--", "scripts/hooks/pre-push"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    assert "eol: lf" in resolved.stdout, f"git disagrees: {resolved.stdout.strip()}"


@pytest.mark.parametrize(
    ("label", "ref_line", "env", "expected"),
    [
        ("push to master", f"refs/heads/master {SHA_A} refs/heads/master {SHA_B}", {}, 1),
        ("push to main", f"refs/heads/main {SHA_A} refs/heads/main {SHA_B}", {}, 1),
        (
            "documented override",
            f"refs/heads/master {SHA_A} refs/heads/master {SHA_B}",
            {"NEON_ALLOW_MASTER_PUSH": "1"},
            0,
        ),
        ("story branch", f"refs/heads/story/1-x {SHA_A} refs/heads/story/1-x {SHA_B}", {}, 0),
        ("branch deletion", f"refs/heads/master {ZERO} refs/heads/master {SHA_B}", {}, 0),
    ],
)
def test_push_guard_blocks_only_what_it_should(
    label: str, ref_line: str, env: dict[str, str], expected: int
) -> None:
    assert _run_hook(ref_line + "\n", env) == expected, f"{label}: wrong exit code"


def test_push_guard_fails_CLOSED_on_a_ref_line_with_no_trailing_newline() -> None:
    """`read` returns non-zero at EOF when the last line is unterminated.

    A plain `while read ...` therefore skips that ref and the hook exits 0 --
    silently ALLOWING the push it exists to block. Found by this suite: the guard
    failed open before the `|| [ -n "$local_ref" ]` continuation was added. A guard
    that fails open is worse than no guard, because everyone assumes it ran.
    """
    unterminated = f"refs/heads/master {SHA_A} refs/heads/master {SHA_B}"
    assert not unterminated.endswith("\n")
    assert _run_hook(unterminated) == 1, "unterminated final ref line must still block"


def test_constitution_no_longer_teaches_the_behaviour_that_caused_the_incident() -> None:
    """AGENTS 8 used to say "commit ... push" on EVERY milestone.

    That is the 10-25 pushes/day behaviour that exhausted the account allowance and
    dark-gated the whole fleet for twelve days. A hook that blocks the default branch
    while the constitution orders a push per milestone only teaches the agent to reach
    for the override every time -- so the hook and the wording are ONE change, not two.
    """
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    assert "Commit freely; push deliberately" in agents
    assert "Do not push per milestone" in agents
    assert "An open PR is not a free branch" in agents, (
        "the pull_request synchronize trigger makes branch pushes billable; omitting "
        "this is how a reader adopts the branch flow and still pays 2+ runs"
    )


# ---------------------------------------------------------------------------
# Database backup retention (temp_and_disk_discipline S6)
# ---------------------------------------------------------------------------

def _backup(dirpath: Path, when: date, hhmmss: str = "010000", prefix: str = "backup") -> Path:
    path = dirpath / f"{prefix}_{when:%Y%m%d}_{hhmmss}.db"
    path.write_bytes(b"x")
    return path


def test_db_retention_ships_and_is_config_driven_not_hardcoded() -> None:
    """The authoring project hardcoded its own `tips_backup_` prefix.

    A template that inherits one project's naming convention is useless to every other
    project: the capability has to be configurable to BE a capability.
    """
    script = REPO / "scripts" / "utilities" / "prune_db_backups.py"
    assert script.is_file()
    body = script.read_text(encoding="utf-8")
    assert "tips_backup" not in body, "the template must not inherit one project's file naming"

    config = (REPO / "config.yaml").read_text(encoding="utf-8")
    for key in ("database_backups:", "filename_prefix:", "daily_count:", "weekly_count:"):
        assert key in config, f"config.yaml must expose {key}"


def test_db_retention_keeps_one_per_day_then_one_per_week(tmp_path: Path) -> None:
    today = date(2026, 7, 31)
    for offset in range(40):
        _backup(tmp_path, today - timedelta(days=offset))
    # A second backup on the newest day: same-day extras are prunable, newest wins.
    _backup(tmp_path, today, hhmmss="235959")

    pruned = set(prune_db_backups.select_backups_to_prune(tmp_path, daily_count=7, weekly_count=4))
    kept = set(tmp_path.iterdir()) - pruned

    assert len(kept) == 11, f"expected 7 daily + 4 weekly = 11 kept, got {len(kept)}"
    same_day = {p for p in tmp_path.iterdir() if "20260731" in p.name}
    assert len(same_day & kept) == 1, "exactly one backup per day is kept"
    assert (tmp_path / "backup_20260731_235959.db") in kept, "the day's NEWEST is the keeper"


def test_db_retention_never_touches_manually_named_snapshots(tmp_path: Path) -> None:
    """Ad-hoc snapshots have no convention to key on -- which is why they accumulate.

    Automating their deletion is how you lose the one someone kept on purpose.
    """
    for offset in range(40):
        _backup(tmp_path, date(2026, 7, 31) - timedelta(days=offset))
    manual = tmp_path / "pre_migration_snapshot_260717.db"
    manual.write_bytes(b"precious")

    pruned = prune_db_backups.select_backups_to_prune(tmp_path, daily_count=7, weekly_count=4)
    assert manual not in pruned
    assert manual.exists()


def test_db_retention_is_dry_run_by_default(tmp_path: Path) -> None:
    for offset in range(40):
        _backup(tmp_path, date(2026, 7, 31) - timedelta(days=offset))
    before = len(list(tmp_path.iterdir()))

    result = prune_db_backups.prune(tmp_path, daily_count=7, weekly_count=4, execute=False)

    assert result["candidates"] > 0
    assert result["deleted"] == 0
    assert len(list(tmp_path.iterdir())) == before, "dry run must delete nothing (AGENTS 5.1)"


def test_db_retention_windows_adapt_to_gaps(tmp_path: Path) -> None:
    """Windows are defined by days that HAVE a backup, not calendar distance.

    This matters most precisely when the backup job has been failing: a naive calendar
    window silently shrinks the number of restore points you keep, exactly when you
    can least afford it.
    """
    base = date(2026, 7, 31)
    for offset in (0, 1, 2, 30, 60, 90, 120):
        _backup(tmp_path, base - timedelta(days=offset))

    pruned = prune_db_backups.select_backups_to_prune(tmp_path, daily_count=7, weekly_count=4)
    assert pruned == [], "7 backups across large gaps are all restore points; prune none"


def test_db_retention_ignores_a_shaped_but_impossible_date(tmp_path: Path) -> None:
    """`backup_20261332_010000.db` matches the shape and is not a date."""
    bogus = tmp_path / "backup_20261332_010000.db"
    bogus.write_bytes(b"x")
    for offset in range(40):
        _backup(tmp_path, date(2026, 7, 31) - timedelta(days=offset))

    pruned = prune_db_backups.select_backups_to_prune(tmp_path, daily_count=7, weekly_count=4)
    assert bogus not in pruned, "an unparseable date must not become a deletion candidate"


# ---------------------------------------------------------------------------
# Project-scoped temp (temp_and_disk_discipline S2 / S3)
# ---------------------------------------------------------------------------

def test_project_temp_helper_ships_and_stays_off_the_boot_drive() -> None:
    from backend.core.paths import PROJECT_ROOT, new_temp_dir, project_temp_dir

    root = project_temp_dir()
    assert root == PROJECT_ROOT / ".data" / "tmp"
    assert ".data" in root.parts, "scratch must live under a git-ignored path"

    with new_temp_dir("probe") as tmp:
        created = Path(tmp)
        assert created.exists()
        assert (PROJECT_ROOT / ".data" / "tmp") in created.parents


def test_embedded_script_token_refuses_a_silent_no_op() -> None:
    """A sentinel substitution matching nothing IS the leak it exists to prevent.

    If the token is absent the replace no-ops, the embedded script falls back to its
    own mkdtemp(), and the caller never learns the path -- so nothing ever cleans it.
    One project accumulated 141 orphaned directories exactly this way.
    """
    from backend.core.paths import temp_dir_for_embedded_script

    template, token = temp_dir_for_embedded_script("out = r'__X__'", "__X__")
    assert token in template

    with pytest.raises(ValueError, match="not found"):
        temp_dir_for_embedded_script("out = r'somewhere_else'", "__X__")


# ---------------------------------------------------------------------------
# Bidirectional numbering registry (sprint_status_bidirectional_registry_check S3)
# ---------------------------------------------------------------------------

def test_the_numbering_registry_is_checked_in_BOTH_directions() -> None:
    """`sync_sprint_status.py` only ever proved story file -> registry row.

    Nothing proved the reverse, so a done story with no file could be absent from the
    sole numbering registry entirely and its id left free for a future story to re-use.
    This repo's seed registry is a handful of contiguous stories, which is the project
    lens again: "no gaps here" says nothing about the clone that grows a real backlog
    and inherits whatever tests/ the template shipped.
    """
    check = REPO / "tests" / "test_sprint_status_integrity.py"
    assert check.is_file(), "the template must SHIP the reverse check, not just describe it"
    body = check.read_text(encoding="utf-8")
    for name in (
        "def test_story_numbering_has_no_unexplained_gaps",
        "def test_known_id_gaps_are_still_actually_gaps",
        "def test_the_checks_are_looking_at_a_populated_registry",
    ):
        assert name in body, f"{name} is missing; the shipped check is incomplete"
    assert "_KNOWN_ID_GAPS: dict[str, str]" in body, (
        "the allow-list must map each excused id to its REASON -- a bare list of ids is "
        "how an exclusion quietly outlives the thing it excused"
    )
