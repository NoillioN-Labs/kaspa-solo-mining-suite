"""Destination-side retention for scripts/utilities/backup_project_data.py.

The mirror's AGENTS 9 refusals and its additive-only contract are covered in
tests/test_ported_fleet_utilities.py. This file covers the half the template was
shipping WITHOUT: retention. An additive mirror of a daily 500MB snapshot grows ~15GB a
month; nothing fails, no warning is printed, the exit code stays 0, and the cheapest fix
in the moment is to turn the whole mechanism off.

The load-bearing distinction every test below pins: applying a retention POLICY at the
destination is not the same as PROPAGATING a source deletion. The first reads only the
destination; the second is a sync, and a sync replicates your mistakes.

Every test builds its OWN config in tmp_path, so none of them inherit the repo's real
retention counts or filename_prefix -- values that would otherwise silently change what
the assertions mean. The single deliberate exception asserts the template's INERTNESS
(AGENTS 9): a test pinning the mirror ON would fail on the Golden Image and be "fixed"
by enabling an external write in a template.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "utilities"))

import backup_project_data as bpd  # noqa: E402

#: Pinned through _config_file, and deliberately NOT prune_db_backups' own "backup"
#: default. A defaulted prefix at the destination matches nothing, deletes nothing,
#: returns {0, 0, 0} and exits 0 -- a no-op wearing the appearance of a working
#: retention policy. A suite that tests with the default prefix agrees with that bug.
PREFIX = "snapshot"


def _write_backup(directory: Path, name: str, content: str = "db") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


def _daily_backup_names(count: int, *, last_day: str = "2026-06-21") -> list[str]:
    """`count` consecutive daily backup filenames ending at `last_day`, oldest first.

    Built from date arithmetic, never hand-written literals. The weekly tier is computed
    over what remains AFTER the dailies are taken, so a fixture must span roughly
    (daily_count / 7 + weekly_count + 1) weeks before that tier can fill at all --
    hand-written dates are exactly how a fixture ends up inside a single ISO week,
    exercising ONE of the two tiers while appearing to test both.
    """
    end = date.fromisoformat(last_day)
    return [
        f"{PREFIX}_{(end - timedelta(days=i)).strftime('%Y%m%d')}_060000.db"
        for i in range(count - 1, -1, -1)
    ]


def _config_file(
    tmp_path: Path, dest_root: Path, *, enabled: bool, daily: int = 7, weekly: int = 4,
    backup_dir: str | None = None,
) -> Path:
    """A self-contained config, so no test here inherits the production values.

    Declares no `backup.categories` override on purpose: `database_backups` is a
    BUILT-IN (bpd._DEFAULT_CATEGORIES), and restating the glob here would make deleting
    it from the defaults invisible to every test in this file.
    """
    config = tmp_path / "config.yaml"
    config.write_text(
        "backup:\n"
        f"  destination_path: '{dest_root.as_posix()}'\n"
        "  include:\n"
        f"    database_backups: {'true' if enabled else 'false'}\n"
        "database_backups:\n"
        f"  filename_prefix: '{PREFIX}'\n"
        f"  daily_count: {daily}\n"
        f"  weekly_count: {weekly}\n"
        + (f"  backup_dir: '{backup_dir}'\n" if backup_dir else ""),
        encoding="utf-8",
    )
    return config


# ---------------------------------------------------------------------------
# The category itself -- present, and inert
# ---------------------------------------------------------------------------

def test_the_snapshot_category_is_a_built_in_and_the_template_ships_it_off() -> None:
    """Two facts that pull in opposite directions, both required.

    It must EXIST: load_enabled_categories() iterates load_categories() keys, so a
    category missing from the defaults can never be switched on by config at all, and
    _RETAINED_CATEGORIES keys retention on this exact name -- retention over a
    category that cannot be enabled is dead code.

    It must ship OFF: the Golden Image never enables an external write (AGENTS 9). This
    asserts the inertness rather than the feature, so it cannot be "fixed" by turning
    a template's backup on.
    """
    categories = bpd.load_categories()

    assert categories["database_backups"] == ".data/backups/**/*"
    assert set(bpd._RETAINED_CATEGORIES) <= set(categories), (
        "retention is keyed on a category name that no longer exists"
    )
    assert bpd.load_enabled_categories() == [], (
        "the template ships every category off; a project enables one deliberately"
    )


# ---------------------------------------------------------------------------
# Retention at the destination -- an independent policy, never a sync
# ---------------------------------------------------------------------------

def test_destination_prune_applies_gfs_to_the_destinations_own_contents(tmp_path: Path) -> None:
    """21 consecutive dailies at the destination; a 7-daily + 2-weekly policy keeps 9.

    The fixture spans three ISO weeks on purpose (2026-06-01 is a Monday, so Jun 1-7 =
    wk23, Jun 8-14 = wk24, Jun 15-21 = wk25), because the weekly tier only sees what is
    LEFT AFTER the dailies are taken. A 13-day fixture leaves every non-daily candidate
    inside one ISO week and quietly exercises one tier while appearing to test both.
    """
    dest_root = tmp_path / "dest"
    backups = dest_root / ".data" / "backups"
    for name in _daily_backup_names(21):
        _write_backup(backups, name)
    config = _config_file(tmp_path, dest_root, enabled=True, daily=7, weekly=2)

    result = bpd.prune_destination_backups(dest_root, execute=True, config_path=config)

    survivors = sorted(p.name for p in backups.iterdir())
    assert result["deleted"] == 12
    assert len(survivors) == 9, survivors
    # The 7 most recent days survive as dailies (Jun 15-21, all inside week 25)...
    for day in range(15, 22):
        assert f"{PREFIX}_202606{day:02d}_060000.db" in survivors
    # ...then one per ISO week for the next two distinct weeks: Jun 14 (wk24), Jun 7 (wk23).
    assert f"{PREFIX}_20260614_060000.db" in survivors
    assert f"{PREFIX}_20260607_060000.db" in survivors


def test_destination_prune_never_touches_a_hand_named_snapshot(tmp_path: Path) -> None:
    """Hand-named snapshots are the last known-good state before a destructive repair --
    the most valuable files in the folder. They do not match
    <prefix>_<YYYYMMDD>_<HHMMSS>.db and must survive any retention pass, including one
    whose name merely STARTS with the configured prefix.
    """
    dest_root = tmp_path / "dest"
    backups = dest_root / ".data" / "backups"
    for name in _daily_backup_names(19):
        _write_backup(backups, name)
    plain = _write_backup(backups, "pre_repair_260807.db", "precious")
    prefixed = _write_backup(backups, f"{PREFIX}_pre_repair_260807.db", "precious too")
    config = _config_file(tmp_path, dest_root, enabled=True, daily=2, weekly=1)

    result = bpd.prune_destination_backups(dest_root, execute=True, config_path=config)

    assert result["deleted"] == 16, "only the dated files are ever candidates"
    assert plain.read_text(encoding="utf-8") == "precious"
    assert prefixed.read_text(encoding="utf-8") == "precious too"
    assert len(list(backups.iterdir())) == 5  # 3 dated survivors + 2 hand-named


def test_destination_prune_keys_on_the_configured_prefix_not_the_pruners_default(
    tmp_path: Path,
) -> None:
    """The regression guard for a defaulted `filename_prefix`.

    select_backups_to_prune and prune both default to "backup". Port the retention pass
    without passing the configured prefix through and the regex matches NOTHING at a
    destination named anything else: no candidates printed, nothing deleted, exit 0 --
    a no-op indistinguishable from a healthy retention policy, on top of a mirror that
    keeps growing. The decoys below carry the pruner's own default prefix, so the bugged
    version selects THEM (and, under a 7-daily policy, finds nothing to prune at all).
    """
    dest_root = tmp_path / "dest"
    backups = dest_root / ".data" / "backups"
    for name in _daily_backup_names(21):
        _write_backup(backups, name)
    decoys = [
        _write_backup(backups, "backup_20260601_060000.db", "decoy"),
        _write_backup(backups, "backup_20260608_060000.db", "decoy"),
        _write_backup(backups, "backup_20260615_060000.db", "decoy"),
    ]
    config = _config_file(tmp_path, dest_root, enabled=True, daily=7, weekly=2)

    result = bpd.prune_destination_backups(dest_root, execute=True, config_path=config)

    assert result["deleted"] == 12, "the CONFIGURED prefix must be what gets selected"
    for decoy in decoys:
        assert decoy.exists(), "a file outside the configured prefix is never a candidate"
    assert len(list(backups.iterdir())) == 12  # 9 dated survivors + 3 decoys


def test_the_announced_candidates_are_the_files_actually_deleted(tmp_path: Path, capsys) -> None:
    """The announcement and the deletion are two SEPARATE selections, and they can diverge.

    `select_backups_to_prune` feeds only the printed list; `prune` re-selects internally and
    does the deleting. So the configured prefix has to reach BOTH, and dropping it from the
    announcement alone leaves every count and every survivor assertion in this file green
    while the log names a different set of files from the one being destroyed. Found by
    mutation: removing the prefix from the selection call broke nothing else in this suite.

    A DELETE against an external destination is exactly where a log that does not describe
    what happened is worse than no log -- it is the record you would reach for afterwards.
    """
    dest_root = tmp_path / "dest"
    backups = dest_root / ".data" / "backups"
    for name in _daily_backup_names(13):
        _write_backup(backups, name)
    config = _config_file(tmp_path, dest_root, enabled=True, daily=1, weekly=1)

    before = {p.name for p in backups.iterdir()}
    result = bpd.prune_destination_backups(dest_root, execute=True, config_path=config)
    after = {p.name for p in backups.iterdir()}

    announced = {
        line.strip() for line in capsys.readouterr().out.splitlines()
        if line.startswith("      ") and line.strip().endswith(".db")
    }
    assert announced, "a delete that announces nothing is not auditable"
    assert announced == before - after, (
        "the announced candidates must BE the deleted files, not a different set "
        f"(announced {len(announced)}, deleted {len(before - after)})"
    )
    assert len(announced) == result["deleted"]


def test_destination_prune_dry_run_deletes_nothing_but_still_reports_candidates(
    tmp_path: Path,
) -> None:
    """AGENTS 5.1: dry-run is the default posture, and it must still tell you what it
    WOULD do -- a dry run reporting zero candidates is indistinguishable from a broken
    selection."""
    dest_root = tmp_path / "dest"
    backups = dest_root / ".data" / "backups"
    for name in _daily_backup_names(13):
        _write_backup(backups, name)
    config = _config_file(tmp_path, dest_root, enabled=True, daily=1, weekly=1)

    result = bpd.prune_destination_backups(dest_root, execute=False, config_path=config)

    assert result["candidates"] == 11
    assert result["deleted"] == 0
    assert len(list(backups.iterdir())) == 13


def test_destination_prune_is_a_noop_when_the_backup_directory_is_absent(tmp_path: Path) -> None:
    """An absent destination backup directory is nothing to do, not an error.

    The category is ENABLED here on purpose, so it is the is_dir() gate being exercised
    and not the enabled-category gate -- which would answer identically and hide it.
    """
    missing = tmp_path / "nowhere"
    config = _config_file(tmp_path, missing, enabled=True)

    result = bpd.prune_destination_backups(missing, execute=True, config_path=config)

    assert result == {"candidates": 0, "deleted": 0, "failed": 0}
    assert not missing.exists()


def test_destination_retention_survives_a_source_side_catastrophe(tmp_path: Path) -> None:
    """THE regression guard for the whole design: wipe the ENTIRE source backup
    directory, then mirror + prune. The destination keeps exactly what its OWN policy
    keeps, because the prune never consults the source. If this ever fails, the mirror
    has become a sync.

    THE FIXTURE IS DELIBERATELY LARGER THAN THE POLICY. Seed 5 backups under a 7-daily
    policy and a correct prune, a prune wrongly pointed at the (now empty) source, and a
    prune that never ran all produce the same 5 survivors -- the test would be asserting
    the outcome of doing nothing. With 42 dailies and a 7+4 policy the outcomes separate
    cleanly: correct -> 11, source-pointed -> 42, never-ran -> 42, sync -> 0.
    """
    project_root = tmp_path / "project"
    source_backups = project_root / ".data" / "backups"
    for name in _daily_backup_names(42):  # 6 ISO weeks: 7 dailies + 4 weeklies can fill
        _write_backup(source_backups, name)
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    dest_backups = dest_root / ".data" / "backups"
    config = _config_file(tmp_path, dest_root, enabled=True, daily=7, weekly=4)

    bpd.mirror_enabled_categories(execute=True, project_root=project_root, config_path=config)
    assert len(list(dest_backups.iterdir())) == 42

    for path in list(source_backups.iterdir()):
        path.unlink()
    assert not list(source_backups.iterdir())

    result = bpd.mirror_enabled_categories(
        execute=True, prune_destination=True, project_root=project_root, config_path=config
    )

    survivors = sorted(p.name for p in dest_backups.iterdir())
    assert len(survivors) == 11, survivors
    assert result["destination_pruned"] == 31
    assert result["copied"] == 0
    # The RIGHT 11, by name: the 7 most recent days, then one per ISO week for 4 weeks.
    for name in _daily_backup_names(7):
        assert name in survivors
    for weekly in (
        f"{PREFIX}_20260614_060000.db",
        f"{PREFIX}_20260607_060000.db",
        f"{PREFIX}_20260531_060000.db",
        f"{PREFIX}_20260524_060000.db",
    ):
        assert weekly in survivors, weekly
    # Content survived, not merely the filenames.
    assert (dest_backups / f"{PREFIX}_20260621_060000.db").read_text(encoding="utf-8") == "db"


# ---------------------------------------------------------------------------
# Turning the feature off must not leave half of it running -- gated ONCE,
# tested at both the entry point and the gate itself
# ---------------------------------------------------------------------------

def test_retention_does_not_run_when_the_category_is_disabled(tmp_path: Path) -> None:
    """Driven through the public entry point: `include.database_backups: false` is the
    documented way to turn the mirror OFF, and it must not convert a nightly job into a
    pure destination-side DELETER that stops copying and keeps deleting."""
    project_root = tmp_path / "project"
    (project_root / ".data" / "backups").mkdir(parents=True)
    dest_root = tmp_path / "dest"
    for name in _daily_backup_names(21):
        _write_backup(dest_root / ".data" / "backups", name)
    config = _config_file(tmp_path, dest_root, enabled=False, daily=1, weekly=1)

    result = bpd.mirror_enabled_categories(
        execute=True, prune_destination=True, project_root=project_root, config_path=config
    )

    assert result["destination_pruned"] == 0
    assert result["categories"] == 0
    assert len(list((dest_root / ".data" / "backups").iterdir())) == 21


def test_prune_destination_backups_itself_refuses_a_disabled_category(tmp_path: Path) -> None:
    """The gate itself, tested on its own.

    The gate lives in exactly one place (this function); mirror_enabled_categories just
    passes its enabled list in. Driving only the pair would leave a mutation of the gate
    looking like a mutation of the caller, so this pins the decision point directly --
    delete `if category not in enabled: continue` and this test is the one that names it.
    """
    dest_root = tmp_path / "dest"
    for name in _daily_backup_names(21):
        _write_backup(dest_root / ".data" / "backups", name)
    config = _config_file(tmp_path, dest_root, enabled=False, daily=1, weekly=1)

    result = bpd.prune_destination_backups(dest_root, execute=True, config_path=config)

    assert result == {"candidates": 0, "deleted": 0, "failed": 0}
    assert len(list((dest_root / ".data" / "backups").iterdir())) == 21


# ---------------------------------------------------------------------------
# "Nothing was attempted" must never read as success (AGENTS 5.5.1)
# ---------------------------------------------------------------------------

def test_a_missing_pruner_warns_loudly_instead_of_returning_a_quiet_zero(
    tmp_path: Path, monkeypatch, capsys,
) -> None:
    """Both import styles failing means the retention pass DID NOT RUN. Reported as a
    quiet {0, 0, 0} that is indistinguishable from "there was nothing to prune", which
    is the silent-fallback shape AGENTS 5.5.1 exists to forbid.

    Setting sys.modules[name] = None makes `import name` raise ImportError, which is how
    a branch marked "only outside the repo layout entirely" becomes testable.
    """
    dest_root = tmp_path / "dest"
    backups = dest_root / ".data" / "backups"
    for name in _daily_backup_names(21):
        _write_backup(backups, name)
    config = _config_file(tmp_path, dest_root, enabled=True, daily=1, weekly=1)
    monkeypatch.setitem(sys.modules, "scripts.utilities.prune_db_backups", None)
    monkeypatch.setitem(sys.modules, "prune_db_backups", None)

    result = bpd.prune_destination_backups(dest_root, execute=True, config_path=config)

    assert result == {"candidates": 0, "deleted": 0, "failed": -1}
    assert "[WARN] prune_db_backups unavailable" in capsys.readouterr().out
    assert len(list(backups.iterdir())) == 21, "a skipped pass must not delete anything"


def test_main_counts_a_skipped_retention_pass_as_a_failure_never_as_a_credit(
    tmp_path: Path, monkeypatch, capsys,
) -> None:
    """The -1 sentinel is a failure to REPORT, not a number to add.

    Summed raw it decrements the run's failure count, so one failed copy plus one
    skipped retention pass sums to 0 and the CLI exits clean. Clamped to 0 it disappears
    entirely and the skipped pass becomes invisible. Neither is acceptable, so the exact
    totals line is asserted here rather than only the exit code.
    """
    project_root = tmp_path / "project"
    _write_backup(project_root / ".data" / "backups", f"{PREFIX}_20260621_060000.db")
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    monkeypatch.setattr(bpd, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(
        bpd, "_load_backup_config",
        lambda config_path=None: {
            "destination_path": str(dest_root),
            "include": {"database_backups": True},
        },
    )
    monkeypatch.setitem(sys.modules, "scripts.utilities.prune_db_backups", None)
    monkeypatch.setitem(sys.modules, "prune_db_backups", None)

    exit_code = bpd.main(["--prune-destination", "--execute"])

    out = capsys.readouterr().out
    assert "[WARN] prune_db_backups unavailable" in out
    assert "Copied 1 file(s); 0 already current; 1 failed." in out, out
    assert exit_code == 1


def test_mirror_enabled_categories_reports_an_unconfigured_destination_as_a_failure(
    tmp_path: Path, monkeypatch,
) -> None:
    """A caller embedded in a scheduled job needs a REPORTABLE result, not an exception
    -- and "no destination configured" must never read as success."""
    monkeypatch.setattr(bpd, "_load_backup_config", lambda config_path=None: {})

    result = bpd.mirror_enabled_categories(execute=True, project_root=tmp_path)

    assert result["failed"] == -1
    assert result["copied"] == 0


def test_a_missing_destination_root_is_refused_not_created(tmp_path: Path, capsys) -> None:
    """mirror_files calls mkdir(parents=True) per file, so an unmounted or typo'd
    destination would be FABRICATED on the local disk, copied into, and reported a
    complete success -- with the "off-machine" copy sitting on the very disk it exists
    to survive, and the real offsite set orphaned elsewhere."""
    project_root = tmp_path / "project"
    _write_backup(project_root / ".data" / "backups", f"{PREFIX}_20260621_060000.db")
    missing = tmp_path / "not-mounted"
    config = _config_file(tmp_path, missing, enabled=True)

    result = bpd.mirror_enabled_categories(
        execute=True, project_root=project_root, config_path=config
    )

    assert result["failed"] == -1
    assert not missing.exists(), "the destination must never be auto-created"
    assert "[REFUSED]" in capsys.readouterr().out


def test_verify_landed_confirms_this_runs_snapshot_reached_the_destination(tmp_path: Path) -> None:
    """"Did we copy anything" cannot answer "did TONIGHT'S backup land" -- a legitimate
    re-run copies 0 and skips 15. The check must name the artefact (AGENTS 4.1 axis 3)."""
    project_root = tmp_path / "project"
    snapshot = _write_backup(
        project_root / ".data" / "backups", f"{PREFIX}_20260621_060000.db", "tonight"
    )
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    landed = dest_root / ".data" / "backups" / f"{PREFIX}_20260621_060000.db"
    config = _config_file(tmp_path, dest_root, enabled=True)

    first = bpd.mirror_enabled_categories(
        execute=True, project_root=project_root, config_path=config, verify_landed=snapshot
    )
    assert first["verified"] == 1

    landed.unlink()
    again = bpd.mirror_enabled_categories(
        execute=True, project_root=project_root, config_path=config, verify_landed=snapshot
    )
    assert again["verified"] == 1, "a re-copy should restore it"

    landed.unlink()
    dry = bpd.mirror_enabled_categories(
        execute=False, project_root=project_root, config_path=config, verify_landed=snapshot
    )
    assert dry["verified"] == 0, "a dry run copied nothing, so nothing landed"


# ---------------------------------------------------------------------------
# The copy itself -- a failed copy must leave nothing that looks like a backup
# ---------------------------------------------------------------------------

def test_a_truncated_destination_copy_is_re_copied_not_called_current(tmp_path: Path) -> None:
    """The worst failure a backup system can have: an offsite copy that is silently
    truncated and reports healthy forever.

    Killing a copy mid-flight leaves a stub whose mtime -- written NOW, while the source
    snapshot was written minutes ago -- is NEWER than the source's, so an mtime-only
    freshness test skips it every subsequent night. Loud once, green forever.
    """
    project_root = tmp_path / "project"
    src = _write_backup(
        project_root / ".data" / "backups", f"{PREFIX}_20260621_060000.db", "full content"
    )
    dest_root = tmp_path / "dest"
    dest = dest_root / ".data" / "backups" / f"{PREFIX}_20260621_060000.db"
    dest.parent.mkdir(parents=True)
    dest.write_text("trunc", encoding="utf-8")
    future = time.time() + 600
    os.utime(dest, (future, future))
    assert dest.stat().st_mtime > src.stat().st_mtime

    result = bpd.mirror_files([src], project_root, dest_root, execute=True)

    assert result == {"copied": 1, "skipped": 0, "failed": 0}
    assert dest.read_text(encoding="utf-8") == "full content"


def test_a_failed_copy_leaves_nothing_that_looks_like_a_backup(tmp_path: Path, monkeypatch) -> None:
    """A full destination raises on the FIRST write, by which point open(dst, 'wb') has
    already created a 0-byte file -- for EVERY file in the batch. One disk-full night
    could convert the whole mirror, including the irreplaceable hand-named snapshots,
    into 0-byte files that would then be reported "already current" and never
    re-copied."""
    project_root = tmp_path / "project"
    src = _write_backup(
        project_root / ".data" / "backups", f"{PREFIX}_20260621_060000.db", "content"
    )
    dest_root = tmp_path / "dest"
    dest_root.mkdir()

    def _boom(source, target, *args, **kwargs):
        Path(target).write_bytes(b"")  # what a real open-for-write leaves behind
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(bpd.shutil, "copy2", _boom)
    result = bpd.mirror_files([src], project_root, dest_root, execute=True)

    assert result == {"copied": 0, "skipped": 0, "failed": 1}
    backups = dest_root / ".data" / "backups"
    assert not (backups / f"{PREFIX}_20260621_060000.db").exists(), (
        "a failed copy must leave no file that could be mistaken for a backup"
    )
    assert list(backups.glob("*.partial")) == [], "the partial must be cleaned up"


# ---------------------------------------------------------------------------
# Four defects found by adversarial review of this module's own first cut.
# Each is a silent-success shape: nothing raises, nothing logs, exit 0.
# ---------------------------------------------------------------------------


def test_a_relocated_backup_dir_is_followed_by_both_the_mirror_and_retention(
    tmp_path: Path,
) -> None:
    """`backup_dir` is a documented config option; hardcoding it breaks BOTH halves.

    This is the `filename_prefix` defect wearing a path. With the directory hardcoded, a
    project that sets `database_backups.backup_dir` gets a mirror glob matching nothing
    AND a retention pass pointed at a directory that does not exist -- copying nothing,
    pruning nothing, reporting success twice.
    """
    dest_root = tmp_path / "dest"
    backups = dest_root / ".data" / "db_snapshots"
    for name in _daily_backup_names(21):
        _write_backup(backups, name)
    config = _config_file(tmp_path, dest_root, enabled=True, daily=1, weekly=1,
                          backup_dir=".data/db_snapshots")

    assert bpd.load_categories(config)["database_backups"] == ".data/db_snapshots/**/*"

    result = bpd.prune_destination_backups(dest_root, execute=True, config_path=config)

    assert result["deleted"] > 0, "retention must follow the configured backup_dir"
    assert len(list(backups.iterdir())) < 21


def test_main_refuses_a_destination_that_does_not_exist(
    tmp_path: Path, monkeypatch, capsys,
) -> None:
    """The CLI is what the Usage block tells people to run; it had no such guard."""
    missing = tmp_path / "not-mounted"
    src = tmp_path / "proj"
    (src / ".data" / "backups").mkdir(parents=True)
    (src / ".data" / "backups" / "snapshot_20260621_060000.db").write_text("x", encoding="utf-8")
    monkeypatch.setattr(bpd, "PROJECT_ROOT", src)
    monkeypatch.setattr(bpd, "load_enabled_categories", lambda *a, **k: ["database_backups"])

    rc = bpd.main(["--destination", str(missing), "--execute"])

    assert rc == 1
    assert not missing.exists(), "an unmounted destination must never be fabricated"
    assert "[REFUSED]" in capsys.readouterr().out


def test_a_skipped_retention_pass_reaches_an_embedded_caller_as_a_failure(
    tmp_path: Path, monkeypatch,
) -> None:
    """max(sentinel, 0) told a scheduled job `failed: 0` for a pass that never ran.

    mirror_enabled_categories is documented as the entry point for a caller that needs a
    result it can REPORT ON. Clamping the -1 away makes "retention did not run" and
    "retention found nothing to do" the same answer -- the exact conflation the sentinel
    was introduced to prevent.
    """
    dest_root = tmp_path / "dest"
    (dest_root / ".data" / "backups").mkdir(parents=True)
    proj = tmp_path / "proj"
    (proj / ".data" / "backups").mkdir(parents=True)
    (proj / ".data" / "backups" / "snapshot_20260621_060000.db").write_text("x", encoding="utf-8")
    config = _config_file(tmp_path, dest_root, enabled=True, daily=1, weekly=1)

    monkeypatch.setitem(sys.modules, "prune_db_backups", None)
    monkeypatch.setitem(sys.modules, "scripts.utilities.prune_db_backups", None)

    totals = bpd.mirror_enabled_categories(
        dest_root, execute=True, prune_destination=True,
        project_root=proj, config_path=config,
    )

    assert totals["failed"] >= 1, (
        f"a retention pass that never ran must not report clean: {totals}"
    )


def test_a_malformed_config_does_not_raise_out_of_a_raises_nothing_function(
    tmp_path: Path, capsys,
) -> None:
    """It raised AFTER the copies had landed, destroying the report of a backup that worked."""
    dest_root = tmp_path / "dest"
    (dest_root / ".data" / "backups").mkdir(parents=True)
    bad = tmp_path / "broken.yaml"
    bad.write_text("database_backups:\n  backup_dir: [unclosed\n", encoding="utf-8")

    result = bpd.prune_destination_backups(
        dest_root, execute=True, config_path=bad, enabled_categories=["database_backups"]
    )

    assert result["failed"] == -1, "unreadable retention config is a loud skip, not a traceback"
    assert "[WARN]" in capsys.readouterr().out


def test_an_absolute_backup_dir_never_aims_retention_at_the_source(tmp_path: Path) -> None:
    """The sharpest regression this module can have: a DELETE pointed at the source.

    `backup_dir` is documented as "relative to repo root, or absolute". Joining an
    absolute one onto the destination makes pathlib DISCARD the destination, so the
    retention pass -- whose entire safety argument is that it never reads the source --
    would select and delete the project's own live backups. A config value, not a code
    change, is all it takes.
    """
    project = tmp_path / "proj"
    source_backups = project / ".data" / "backups"
    for name in _daily_backup_names(30):
        _write_backup(source_backups, name)
    dest_root = tmp_path / "dest"
    (dest_root / ".data" / "backups").mkdir(parents=True)

    config = _config_file(tmp_path, dest_root, enabled=True, daily=1, weekly=1,
                          backup_dir=source_backups.as_posix())

    before = {p.name for p in source_backups.iterdir()}
    bpd.prune_destination_backups(dest_root, execute=True, config_path=config,
                                  enabled_categories=["database_backups"])
    after = {p.name for p in source_backups.iterdir()}

    assert after == before, (
        f"retention deleted {len(before - after)} file(s) from the SOURCE tree -- that is "
        "a sync propagating a deletion, which this module exists to make impossible"
    )


def test_an_absolute_backup_dir_does_not_build_an_unusable_glob(tmp_path: Path) -> None:
    """Path.glob raises NotImplementedError on an absolute pattern, out of a function
    documented as raising nothing."""
    dest_root = tmp_path / "dest"
    (dest_root / ".data" / "backups").mkdir(parents=True)
    project = tmp_path / "proj"
    (project / ".data" / "backups").mkdir(parents=True)
    config = _config_file(tmp_path, dest_root, enabled=True,
                          backup_dir=(tmp_path / "elsewhere").as_posix())

    pattern = bpd.load_categories(config)["database_backups"]
    assert not Path(pattern).is_absolute(), f"an absolute glob cannot be used: {pattern}"

    totals = bpd.mirror_enabled_categories(
        dest_root, execute=True, prune_destination=True,
        project_root=project, config_path=config,
    )
    assert isinstance(totals, dict)
