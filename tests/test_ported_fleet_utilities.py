"""Capability the FLEET built that the template lacked.

Five utilities existed in one fleet project each and in none of the others, because
they were never packaged as upgrade packs. The template therefore could not do things
its own projects had already solved -- and every project stamped from it inherited
those holes.

The sharpest of them: the AGENTS 9 write-boundary rule lived INSIDE the vendor adapter
`.claude/hooks/write_guard.py`, which violates AGENTS 2 ("adapters contain zero rules...
losing them must never lose information"). bootstrap regenerates adapters, so a
regenerated hook silently took the project's only cross-project write enforcement with
it, and nothing failed.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "utilities"))

import backup_project_data  # noqa: E402
import capability_lie_check  # noqa: E402
import prune_temp_root  # noqa: E402
from write_boundary_check import check_write_boundary  # noqa: E402

# ---------------------------------------------------------------------------
# AGENTS 9 write boundary -- the rule, and the Adapter Rule that moved it here
# ---------------------------------------------------------------------------

def _fleet(tmp_path: Path) -> tuple[Path, Path]:
    """A fleet directory holding this project and one governed sibling."""
    mine = tmp_path / "my-project"
    (mine / "docs").mkdir(parents=True)
    (mine / "AGENTS.md").write_text("x", encoding="utf-8")
    sibling = tmp_path / "sibling-project"
    (sibling / "docs" / "upgrades").mkdir(parents=True)
    (sibling / "backend").mkdir(parents=True)
    (sibling / "AGENTS.md").write_text("x", encoding="utf-8")
    return mine, sibling


def test_the_rule_lives_outside_the_vendor_adapter() -> None:
    """AGENTS 2: adapters are thin, regenerable, and contain ZERO rules.

    With the rule inside the hook, bootstrap regenerating `.claude/hooks/` silently
    removes the project's only AGENTS 9 enforcement -- and nothing fails, which is
    exactly why the Adapter Rule exists.
    """
    assert (REPO / "scripts" / "utilities" / "write_boundary_check.py").is_file()
    hook = (REPO / ".claude" / "hooks" / "write_guard.py").read_text(encoding="utf-8")
    assert "write_boundary_check" in hook, "the adapter must delegate, not decide"
    assert "docs" not in hook.split('"""')[2], (
        "the adapter still contains path rules; they belong in the shared checker"
    )


def test_writes_inside_this_project_are_allowed(tmp_path: Path) -> None:
    mine, _ = _fleet(tmp_path)
    allowed, reason = check_write_boundary(mine / "docs" / "notes.md", mine)
    assert allowed is True
    assert reason == ""


def test_writes_into_a_sibling_are_blocked(tmp_path: Path) -> None:
    mine, sibling = _fleet(tmp_path)
    allowed, reason = check_write_boundary(sibling / "backend" / "main.py", mine)
    assert allowed is False
    assert "sibling-project" in reason


def test_the_one_permitted_cross_project_write_is_upgrade_dissemination(tmp_path: Path) -> None:
    mine, sibling = _fleet(tmp_path)
    allowed, _ = check_write_boundary(sibling / "docs" / "upgrades" / "pack.md", mine)
    assert allowed is True, "docs/upgrades/ is the single permitted sibling write (AGENTS 9)"
    # ...and only that folder, not its parent.
    blocked, _ = check_write_boundary(sibling / "docs" / "ADR" / "0001.md", mine)
    assert blocked is False


def test_an_ungoverned_sibling_defers_rather_than_blocking(tmp_path: Path) -> None:
    """A sibling with no AGENTS.md (a shared skills registry, a scratch dir) is not
    this rule's business -- the permission system still governs it. This guard stops
    one well-defined mistake; it must not try to become the permission system."""
    mine, _ = _fleet(tmp_path)
    registry = tmp_path / "_shared_registry"
    registry.mkdir()
    allowed, _ = check_write_boundary(registry / "skills" / "x.md", mine)
    assert allowed is True


def test_unrelated_locations_defer(tmp_path: Path) -> None:
    mine, _ = _fleet(tmp_path)
    allowed, _ = check_write_boundary(Path(tmp_path.anchor) / "elsewhere" / "f.txt", mine)
    assert allowed is True


def test_boundary_check_cli_reports_a_machine_readable_verdict(tmp_path: Path) -> None:
    """A non-Python vendor adapter must be able to shell out and parse the answer."""
    import json

    mine, sibling = _fleet(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "utilities" / "write_boundary_check.py"),
         "--target", str(sibling / "backend" / "x.py"), "--project-root", str(mine)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["allowed"] is False


# ---------------------------------------------------------------------------
# Temp-root pruning -- a SIZE ceiling, oldest-first
# ---------------------------------------------------------------------------

def test_temp_prune_deletes_oldest_first_only_until_under_the_ceiling(tmp_path: Path) -> None:
    """Emptying the root would destroy the scratch of the run that triggered the sweep.

    The newest entry is the in-progress run's own temp directory, so a wholesale wipe
    breaks the very thing that caused the prune.
    """
    import os

    root = tmp_path / "tmp"
    root.mkdir()
    for i in range(4):
        entry = root / f"run{i}"
        entry.mkdir()
        (entry / "blob").write_bytes(b"x" * 300_000_000)  # 0.3 GB each, 1.2 GB total
        os.utime(entry, (1_000_000 + i * 1000, 1_000_000 + i * 1000))

    result = prune_temp_root.prune(root, max_gb=0.7, execute=True)

    assert result["deleted"] == 2, "0.3 GB x4 = 1.2 GB; two must go to reach <= 0.7"
    survivors = sorted(p.name for p in root.iterdir())
    assert survivors == ["run2", "run3"], f"oldest must go first, got {survivors}"


def test_temp_prune_is_dry_run_by_default(tmp_path: Path) -> None:
    root = tmp_path / "tmp"
    root.mkdir()
    (root / "big").mkdir()
    (root / "big" / "blob").write_bytes(b"x" * 200_000_000)

    result = prune_temp_root.prune(root, max_gb=0.01, execute=False)
    assert result["deleted"] == 1
    assert (root / "big").exists(), "dry run must delete nothing (AGENTS 5.1)"


def test_temp_prune_does_nothing_when_under_the_ceiling(tmp_path: Path) -> None:
    root = tmp_path / "tmp"
    root.mkdir()
    (root / "small").write_bytes(b"x" * 1000)
    assert prune_temp_root.prune(root, max_gb=2.0, execute=True)["deleted"] == 0
    assert (root / "small").exists()


def test_temp_prune_reads_the_configured_root_not_a_hardcoded_one(tmp_path: Path) -> None:
    """The source version hardcoded `.data/tmp` in main(), ignoring the very config key
    its own docstring cited -- so a project that set testing.temp_root was pruning the
    wrong directory, or nothing at all."""
    config = tmp_path / "config.yaml"
    config.write_text(
        "testing:\n  temp_root: 'custom/scratch'\n  temp_root_max_gb: 3.5\n", encoding="utf-8"
    )
    root, max_gb = prune_temp_root._load_settings(config)
    assert root.parts[-2:] == ("custom", "scratch")
    assert max_gb == 3.5


# ---------------------------------------------------------------------------
# Producer/pruner coherence -- one prefix, read by both
# ---------------------------------------------------------------------------

def test_backup_producer_and_pruner_share_one_filename_convention() -> None:
    """Split them and the pruner silently matches nothing: it reports "no candidates",
    looks healthy, and the directory grows forever."""
    producer = (REPO / "scripts" / "utilities" / "backup_db.py").read_text(encoding="utf-8")
    assert "_load_config" in producer, "the producer must read the pruner's config block"
    assert 'f"{prefix}_{stamp}.db"' in producer, "the producer must build the pruned shape"

    import prune_db_backups

    config = prune_db_backups._load_config()
    stamped = f"{config['filename_prefix']}_20260731_140000.db"
    assert prune_db_backups._parse_backup_date(
        Path(stamped), prune_db_backups._filename_re(config["filename_prefix"])
    ) == date(2026, 7, 31), "what the producer writes must be what the pruner matches"


def test_backup_producer_refuses_rather_than_no_opping_without_a_db(tmp_path: Path) -> None:
    import backup_db

    with pytest.raises(ValueError, match="db_path"):
        backup_db.backup(db_path=None)


def test_backup_producer_creates_a_restorable_snapshot(tmp_path: Path) -> None:
    """Uses the sqlite3 online backup API: a filesystem copy of a live database can
    capture a torn page and produce a backup that only fails when you restore it."""
    import sqlite3

    import backup_db

    db = tmp_path / "app.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t VALUES ('kept')")
    conn.commit()
    conn.close()

    written = backup_db.backup(db_path=db, prune=False)
    assert written.exists()

    restored = sqlite3.connect(str(written))
    assert restored.execute("SELECT v FROM t").fetchone()[0] == "kept"
    restored.close()
    written.unlink()


# ---------------------------------------------------------------------------
# External data mirror -- never guesses a destination, never deletes
# ---------------------------------------------------------------------------

def test_mirror_refuses_without_an_explicit_destination() -> None:
    assert backup_project_data.main(["--execute"]) == 1, (
        "an external destination is AGENTS 9 ask-first; it must never be guessed"
    )


def test_mirror_categories_are_off_until_named(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("backup:\n  destination_path: 'X'\n", encoding="utf-8")
    assert backup_project_data.load_enabled_categories(config) == []


def test_mirror_never_deletes_at_the_destination(tmp_path: Path) -> None:
    """A mirror that propagates deletions is a sync, and a sync replicates your mistake.
    Surviving a source-side loss is the entire point."""
    src = tmp_path / "src"
    (src / "client_files").mkdir(parents=True)
    (src / "client_files" / "keep.txt").write_text("new", encoding="utf-8")
    dest = tmp_path / "dest"
    (dest / "client_files").mkdir(parents=True)
    orphan = dest / "client_files" / "source_was_deleted.txt"
    orphan.write_text("precious", encoding="utf-8")

    files = backup_project_data.discover_category_files(
        "client_files", src, backup_project_data.load_categories(tmp_path / "nope.yaml")
    )
    backup_project_data.mirror_files(files, src, dest, execute=True)

    assert orphan.exists(), "a file whose source vanished must survive at the destination"
    assert (dest / "client_files" / "keep.txt").read_text(encoding="utf-8") == "new"


# ---------------------------------------------------------------------------
# Capability-lie check -- generalised off one project's schema
# ---------------------------------------------------------------------------

def test_capability_check_defaults_to_the_constitution_prompt_layout() -> None:
    """AGENTS 5.4 mandates backend/ai_modules/<NN>_<agent>/ with one __prompt__ file,
    so a constitution-following project needs no configuration at all."""
    settings = capability_lie_check.load_settings(REPO / "config.yaml")
    assert settings["prompt_globs"] == ("backend/ai_modules/*/*__prompt__*.md",)


def test_capability_check_flags_a_claim_that_a_resolved_entry_contradicts() -> None:
    prompt = (
        "<STEP>\n## GENUINELY ABSENT\n"
        "* **camera shake stabilisation** is not available\n"
        "* **teleportation** cannot be done\n"
        "</STEP>\n"
    )
    resolved = [{"gap_id": "G-1", "gap_class": "BUILT", "title": "camera shake stabilisation"}]
    settings = capability_lie_check.load_settings(REPO / "config.yaml")

    findings = capability_lie_check.find_stale_claims(prompt, resolved, settings)

    claims = [c for c, _, _ in findings]
    assert any("camera shake" in c for c in claims), "a now-BUILT capability must be flagged"
    assert not any("teleportation" in c for c in claims), "unresolved claims must stay quiet"


def test_capability_check_deduplicates_repeated_sections() -> None:
    """A per-variant prompt repeating the same capability prose would otherwise print
    the same real finding many times -- volume that makes a true finding look like noise."""
    section = "## GENUINELY ABSENT\n* **camera shake stabilisation** absent\n</STEP>\n"
    resolved = [{"gap_id": "G-1", "gap_class": "BUILT", "title": "camera shake stabilisation"}]
    settings = capability_lie_check.load_settings(REPO / "config.yaml")

    findings = capability_lie_check.find_stale_claims(section * 3, resolved, settings)
    assert len(findings) == 1


def test_capability_check_skips_loudly_when_no_registry_is_configured(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A check that did not run is not a check that passed (AGENTS 6)."""
    assert capability_lie_check.main([]) == 0
    assert "[SKIP]" in capsys.readouterr().out
