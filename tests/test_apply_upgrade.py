"""Unit tests for scripts/utilities/apply_upgrade.py.

Regression cover for the stale-pack bug (2026-07-13): `disseminate` decided a project
was up to date by checking whether a file of that NAME existed, so a pack revised after
its first dissemination was silently skipped forever. The fleet kept a stale copy it
believed was current.

That is a silent-success failure of exactly the kind AGENTS 5.5.1 forbids, and it bit
for real: a pack was corrected (memory must move in-repo, not stay vendor-locked) and
all four projects were left holding the superseded instructions.
"""

import argparse
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "utilities"))

import apply_upgrade  # noqa: E402


def test_identical_pack_is_recognised_as_current(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    target = tmp_path / "target.md"
    source.write_text("# Pack\n\nDo the thing.\n", encoding="utf-8")
    target.write_text("# Pack\n\nDo the thing.\n", encoding="utf-8")

    assert apply_upgrade.same_content(source, target)


def test_revised_pack_is_detected_as_stale(tmp_path: Path) -> None:
    """The bug: this returned 'exists, skip' and the correction never shipped."""
    source = tmp_path / "source.md"
    target = tmp_path / "target.md"
    source.write_text("# Pack\n\nDo the thing. CORRECTION: do it the other way.\n", encoding="utf-8")
    target.write_text("# Pack\n\nDo the thing.\n", encoding="utf-8")

    assert not apply_upgrade.same_content(source, target)


def test_line_endings_alone_do_not_mark_a_pack_stale(tmp_path: Path) -> None:
    """The fleet spans repos with different autocrlf settings; CRLF vs LF is not a
    revision, and treating it as one would refresh every pack on every run."""
    source = tmp_path / "source.md"
    target = tmp_path / "target.md"
    source.write_bytes(b"# Pack\n\nDo the thing.\n")
    target.write_bytes(b"# Pack\r\n\r\nDo the thing.\r\n")

    assert apply_upgrade.same_content(source, target)


def test_unreadable_target_is_treated_as_stale(tmp_path: Path) -> None:
    """Fail toward refreshing, never toward silently leaving a project behind."""
    source = tmp_path / "source.md"
    source.write_text("# Pack\n", encoding="utf-8")

    assert not apply_upgrade.same_content(source, tmp_path / "does-not-exist.md")


# ---------------------------------------------------------------------------
# Fleet topology + the template `record` guard (AGENTS 6)
#
# Fleet discovery is POSITIONAL -- immediate siblings of the project root. Relocating
# the master to D:\Projects therefore left it discovering ZERO projects: `disseminate`
# warned and exited 0 (reaching nobody, reporting success), and `prune` would have read
# a pack recorded by the first project to move in beside it as "absorbed (1/1)" and
# deleted it from the canonical library while the rest never received it.
#
# Separately, `record` deleted the pack file with no template guard -- in the master,
# docs/upgrades/ IS the library and removal is `prune`'s job.
# ---------------------------------------------------------------------------

def _config(root: Path, body: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text(body, encoding="utf-8")


def test_expected_min_projects_is_read_from_config(tmp_path: Path) -> None:
    _config(tmp_path, "fleet:\n  expected_min_projects: 5\n")
    assert apply_upgrade.read_expected_min_projects(tmp_path) == 5


@pytest.mark.parametrize(
    "body",
    [
        "knowledge:\n  memory_store: docs/memory\n",   # no fleet: section
        "fleet:\n  expected_min_projects: nope\n",      # not an int
        "fleet:\n  expected_min_projects: -1\n",        # nonsense
        "fleet: []\n",                                   # wrong shape
    ],
)
def test_unreadable_fleet_config_returns_none(tmp_path: Path, body: str) -> None:
    """None means 'cannot evaluate the guard' and must be reported, never assumed OK."""
    _config(tmp_path, body)
    assert apply_upgrade.read_expected_min_projects(tmp_path) is None


def test_short_fleet_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The split-fleet state: discovery finds fewer projects than the fleet really has."""
    _config(tmp_path, "fleet:\n  expected_min_projects: 5\n")

    rc = apply_upgrade.assert_fleet_is_whole(tmp_path, [tmp_path / "only-one"], "disseminate")

    assert rc == 1
    out = capsys.readouterr().out
    assert "Split fleet" in out and "discovered 1 project(s)" in out


def test_whole_fleet_is_allowed(tmp_path: Path) -> None:
    _config(tmp_path, "fleet:\n  expected_min_projects: 2\n")
    projects = [tmp_path / "a", tmp_path / "b"]

    assert apply_upgrade.assert_fleet_is_whole(tmp_path, projects, "prune") == 0


def test_unconfigured_guard_says_so_out_loud(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An inactive guard must announce itself; silently passing is the failure mode."""
    _config(tmp_path, "knowledge: {}\n")

    rc = apply_upgrade.assert_fleet_is_whole(tmp_path, [], "disseminate")

    assert rc == 0
    assert "INACTIVE" in capsys.readouterr().out


def _record_repo(tmp_path: Path, project_name: str) -> tuple[Path, str]:
    root = tmp_path / "repo"
    (root / "_bmad").mkdir(parents=True)
    (root / "_bmad" / "config.toml").write_text(
        f'[core]\nproject_name = "{project_name}"\n', encoding="utf-8"
    )
    packs = root / "docs" / "upgrades"
    packs.mkdir(parents=True)
    name = "upgrade_instructions_thing_260727_2035.md"
    (packs / name).write_text("# Pack\n", encoding="utf-8")
    return root, name


def _record_args(name: str) -> argparse.Namespace:
    return argparse.Namespace(
        pack_filename=name, status="applied", notes="", yes=True,
        dry_run=False, delete_pack=False,
    )


def _patch_git(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(apply_upgrade, "get_project_root", lambda: root)
    monkeypatch.setattr(apply_upgrade, "stage_paths", lambda *a, **k: None)
    monkeypatch.setattr(apply_upgrade, "git_path_is_tracked", lambda *a, **k: False)


def test_record_retains_the_pack_in_the_master_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The near-miss: this would have destroyed the only copy of a pack pre-dissemination."""
    root, name = _record_repo(tmp_path, apply_upgrade.TEMPLATE_PROJECT_NAME)
    _patch_git(monkeypatch, root)

    assert apply_upgrade.cmd_record(_record_args(name)) == 0
    assert (root / "docs" / "upgrades" / name).is_file(), "template must RETAIN its library copy"
    assert name in (root / "docs" / "upgrades" / "upgrades_ledger.md").read_text(encoding="utf-8")


def test_record_still_deletes_the_pack_in_a_fleet_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Receiving projects are unchanged: row + deletion is still the closing action."""
    root, name = _record_repo(tmp_path, "Horse racing tips")
    _patch_git(monkeypatch, root)

    assert apply_upgrade.cmd_record(_record_args(name)) == 0
    assert not (root / "docs" / "upgrades" / name).exists()


def test_delete_pack_flag_overrides_the_template_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, name = _record_repo(tmp_path, apply_upgrade.TEMPLATE_PROJECT_NAME)
    _patch_git(monkeypatch, root)
    args = _record_args(name)
    args.delete_pack = True

    assert apply_upgrade.cmd_record(args) == 0
    assert not (root / "docs" / "upgrades" / name).exists()


# ---------------------------------------------------------------------------
# The pack's documented closing command must actually be runnable.
#
# Section 8 has now broken TWICE in two different ways, both discovered only at the
# very last step of a migration, after all the real work was done:
#   - NEON PowerPoint creator: `--status Applied` -> argparse rejects it (lowercase only)
#   - NEON Vision AI:          no `--yes` -> input() hits EOF in an agent shell, EOFError
# Prose fixes did not hold. This parses the commands out of the packs and checks them
# against the real parser, so a third variant cannot ship.
# ---------------------------------------------------------------------------


def _documented_record_commands(directory: Path | None = None) -> list[list[str]]:
    """Extract every `apply_upgrade.py record ...` invocation from the shipped packs."""
    packs = sorted((directory or Path("docs/upgrades")).glob("upgrade_instructions_*.md"))
    commands: list[list[str]] = []
    tick = chr(96)
    for pack in packs:
        # Fenced code blocks, ANY language tag or none. Prose that quotes the command
        # while explaining a past defect is documentation, not an instruction, and must
        # not be parsed as one -- but restricting to ```powershell was narrower than
        # that: it silently never extracted a command from a bare ``` fence. That gap
        # was masked for months by older packs whose fences happened to say
        # "powershell", keeping the overall command list non-empty. Once those packs
        # were pruned (2026-08-30), the five packs fenced with bare ``` were suddenly
        # the whole population, and their commands turned out to have NEVER been
        # checked (AGENTS 4.1 axis 7 -- the prune didn't cause the gap, it removed the
        # thing hiding it).
        fenced, inside = [], False
        for line in pack.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not inside and stripped.startswith(tick * 3):
                inside = True
                continue
            if inside and stripped.startswith(tick * 3):
                inside = False
                continue
            if inside:
                fenced.append(line)
        # PowerShell line continuations are backticks at end-of-line.
        flat = "\n".join(fenced).replace(tick + "\n", " ")
        for line in flat.splitlines():
            if "apply_upgrade.py record" not in line:
                continue
            args = line.split("apply_upgrade.py record", 1)[1]
            tokens = [t for t in args.replace(tick, "").split() if t and not t.startswith("#")]
            if tokens:
                commands.append(tokens)
    return commands


def test_documented_record_commands_are_accepted_by_the_parser() -> None:
    packs = sorted(Path("docs/upgrades").glob("upgrade_instructions_*.md"))
    if not packs:
        # An EMPTY library is a legitimate steady state: every pack absorbed by the
        # whole fleet and pruned. Skip with a reason rather than fail -- but never
        # pass silently, because "nothing to check" and "checked and fine" are
        # different answers and only one of them is evidence (AGENTS 4.1 axis 3).
        pytest.skip("no packs in docs/upgrades/ -- library fully absorbed and pruned")
    commands = _documented_record_commands()
    assert commands, (
        f"{len(packs)} pack(s) present but none documents a `record` command in a "
        "fenced block; every pack must tell the applying agent how to close it"
    )
    for tokens in commands:
        # Drop the quoted --notes value; argparse would take it, but shlex-free splitting
        # cannot reassemble it and it is not what these regressions were about.
        cleaned: list[str] = []
        skip = False
        for t in tokens:
            if skip:
                skip = False
                continue
            if t == "--notes":
                skip = True
                continue
            cleaned.append(t.strip('"'))
        status = cleaned[cleaned.index("--status") + 1] if "--status" in cleaned else None
        assert status in ("applied", "partial", "skipped"), (
            f"documented --status {status!r} is not an accepted choice: {' '.join(cleaned)}"
        )


def test_documented_record_commands_pass_yes_for_unattended_use() -> None:
    """Without --yes, `record` reaches input() and dies on EOF in an agent's shell.

    Note the distinction the pack itself draws: for `record`, --yes only silences a prompt
    and is right for an agent closing its own work. It is NOT equivalent to `disseminate`'s
    --approved-by-user, which asserts a user decision and must never be auto-supplied.
    """
    for tokens in _documented_record_commands():
        assert "--yes" in tokens, (
            f"documented `record` command omits --yes and will EOFError unattended: {' '.join(tokens)}"
        )

def test_a_bare_fence_with_no_language_tag_is_still_extracted(tmp_path: Path) -> None:
    """Regression: restricting extraction to ```powershell silently skipped every
    bare ``` fence. Masked for months by older packs whose fences said "powershell";
    surfaced only once those packs were pruned and the bare-fence packs were the
    whole population (AGENTS 4.1 axis 7 -- the prune revealed it, didn't cause it)."""
    (tmp_path / "upgrade_instructions_bare_fence_260830_0900.md").write_text(
        "# A pack whose closing command uses a BARE fence\n\n"
        "## Close\n\n"
        "```\n"
        "python scripts/utilities/apply_upgrade.py record "
        "upgrade_instructions_bare_fence_260830_0900.md --status applied --yes\n"
        "```\n",
        encoding="utf-8",
    )
    commands = _documented_record_commands(tmp_path)
    assert commands, "a bare ``` fence must still be recognised as a fenced code block"
    assert "--status" in commands[0] and "applied" in commands[0]


def test_inline_prose_quoting_a_command_is_still_not_extracted(tmp_path: Path) -> None:
    """The exclusion this logic exists for must survive the widening."""
    (tmp_path / "upgrade_instructions_prose_only_260830_0901.md").write_text(
        "# A pack that only DISCUSSES a command, never instructs one\n\n"
        "The old command read `apply_upgrade.py record thing.md --status Applied` "
        "(uppercase, wrong) -- fixed since.\n",
        encoding="utf-8",
    )
    assert _documented_record_commands(tmp_path) == []


# ---------------------------------------------------------------------------
# disseminate --only: the approval unit is a SET OF PACKS, not "the library"
#
# docs/upgrades/ is also the INBOX for packs the fleet sends back for review, so
# an unscoped run ships whatever happens to be sitting there. Two packs landed
# from fleet projects part-way through the session that added this flag.
# ---------------------------------------------------------------------------


def _fleet(tmp_path: Path, pack_names: list[str]) -> Path:
    """A template with `pack_names` in its library and five sibling fleet projects."""
    root = tmp_path / "_NEON dev stack"
    (root / "_bmad").mkdir(parents=True)
    (root / "_bmad" / "config.toml").write_text(
        f'[core]\nproject_name = "{apply_upgrade.TEMPLATE_PROJECT_NAME}"\n', encoding="utf-8"
    )
    (root / "config.yaml").write_text("fleet:\n  expected_min_projects: 5\n", encoding="utf-8")
    packs = root / "docs" / "upgrades"
    packs.mkdir(parents=True)
    for name in pack_names:
        (packs / name).write_text(f"# {name}\n", encoding="utf-8")
    for i in range(5):
        sibling = tmp_path / f"project-{i}"
        (sibling / "docs" / "upgrades").mkdir(parents=True)
        (sibling / "AGENTS.md").write_text("# rules\n", encoding="utf-8")
    return root


def _dis_args(**kw) -> argparse.Namespace:
    base = {"dry_run": False, "only": [], "yes": True, "approved_by_user": True}
    base.update(kw)
    return argparse.Namespace(**base)


APPROVED = "upgrade_instructions_approved_260101_0000.md"
UNAPPROVED = "upgrade_instructions_arrived_midsession_260102_0000.md"


def test_only_withholds_every_pack_the_user_did_not_approve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _fleet(tmp_path, [APPROVED, UNAPPROVED])
    monkeypatch.setattr(apply_upgrade, "get_project_root", lambda: root)

    assert apply_upgrade.cmd_disseminate(_dis_args(only=[APPROVED])) == 0

    for i in range(5):
        target = tmp_path / f"project-{i}" / "docs" / "upgrades"
        assert (target / APPROVED).is_file()
        assert not (target / UNAPPROVED).exists(), (
            "a pack the user never saw must not ride along with one they approved"
        )
    assert "WITHHELD" in capsys.readouterr().out


def test_an_unscoped_run_would_have_shipped_the_unapproved_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The behaviour --only exists to prevent -- pinned so nobody 'simplifies' the flag away."""
    root = _fleet(tmp_path, [APPROVED, UNAPPROVED])
    monkeypatch.setattr(apply_upgrade, "get_project_root", lambda: root)

    assert apply_upgrade.cmd_disseminate(_dis_args()) == 0

    assert (tmp_path / "project-0" / "docs" / "upgrades" / UNAPPROVED).is_file()


def test_an_unknown_only_name_is_refused_not_quietly_narrowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A typo must not disseminate a smaller set than asked for and report success."""
    root = _fleet(tmp_path, [APPROVED])
    monkeypatch.setattr(apply_upgrade, "get_project_root", lambda: root)

    assert apply_upgrade.cmd_disseminate(_dis_args(only=[APPROVED, "typo.md"])) == 1

    assert not (tmp_path / "project-0" / "docs" / "upgrades" / APPROVED).exists()
    assert "not in the library" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Ledger matching is CELL EQUALITY, never file-substring
# (pack: ledger_row_must_match_the_upgrade_file_cell_260820_1518; supersedes
#  record_dedups_on_filename_260818_2340 per the 2026-08-29 consolidation, D5)
#
# A row's Notes cell mentioning a pack ("superseded by `X.md`") made record take
# the idempotent path: pack deleted, NO row written, two reassuring [OK] lines.
# The same match drove prune (which deletes across the fleet) and disseminate.
# ---------------------------------------------------------------------------


_LEDGER_WITH_MENTION = (
    "# Project Upgrades Ledger\n\n"
    "prose intro\n\n"
    "| Date | Upgrade File | Status | Notes |\n"
    "| :--- | :--- | :--- | :--- |\n"
    "| 2026-08-01 | `upgrade_instructions_other_260801_0900.md` | Applied | "
    "superseded by `upgrade_instructions_thing_260727_2035.md` |\n"
)


def test_a_notes_mention_is_not_a_record() -> None:
    """The defect, stated as the unit it lives in."""
    assert not apply_upgrade.ledger_contains(
        _LEDGER_WITH_MENTION, "upgrade_instructions_thing_260727_2035.md"
    )
    assert apply_upgrade.ledger_contains(
        _LEDGER_WITH_MENTION, "upgrade_instructions_other_260801_0900.md"
    )


def test_cell_match_is_equality_not_substring() -> None:
    """`in` on the cell would let `thing.md` match `something.md`."""
    ledger = (
        "| Date | Upgrade File | Status | Notes |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| 2026-08-01 | `upgrade_instructions_super_thing_260801_0900.md` | Applied |  |\n"
    )
    assert not apply_upgrade.ledger_contains(ledger, "thing_260801_0900.md")


def test_record_appends_a_row_despite_a_notes_mention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test 1 from the pack: the row must be written, not skipped."""
    root, name = _record_repo(tmp_path, "Fleet Project")
    ledger = root / "docs" / "upgrades" / "upgrades_ledger.md"
    ledger.write_text(_LEDGER_WITH_MENTION, encoding="utf-8")
    _patch_git(monkeypatch, root)

    assert apply_upgrade.cmd_record(_record_args(name)) == 0
    text = ledger.read_text(encoding="utf-8")
    assert apply_upgrade.ledger_contains(text, name), (
        "record must APPEND a row when the only prior reference is a Notes mention"
    )


def test_recorded_row_lands_inside_the_table_not_after_trailing_prose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test 2, in its POSITIONAL form.

    The origin first asserted `ledger_contains(...)` -- true under the defect too,
    because a row appended at end-of-file still puts the filename in the text. The
    mutation came back GREEN, which is how the bad test was caught.
    """
    root, name = _record_repo(tmp_path, "Fleet Project")
    ledger = root / "docs" / "upgrades" / "upgrades_ledger.md"
    ledger.write_text(
        "| Date | Upgrade File | Status | Notes |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| 2026-08-01 | `upgrade_instructions_other_260801_0900.md` | Applied |  |\n"
        "\n"
        "## Trailing prose section\n\n"
        "This paragraph is BELOW the table and must stay below the new row.\n",
        encoding="utf-8",
    )
    _patch_git(monkeypatch, root)

    assert apply_upgrade.cmd_record(_record_args(name)) == 0
    lines = ledger.read_text(encoding="utf-8").split("\n")
    row_index = next(i for i, ln in enumerate(lines) if name in ln)
    prose_index = next(i for i, ln in enumerate(lines) if ln.startswith("## Trailing prose"))
    assert row_index < prose_index, "the new row must land INSIDE the table"
    assert lines[row_index - 1].strip().startswith("|"), (
        "the line above the new row must be a table row"
    )


def test_a_ledger_with_no_table_gains_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, name = _record_repo(tmp_path, "Fleet Project")
    ledger = root / "docs" / "upgrades" / "upgrades_ledger.md"
    ledger.write_text("Just prose, no table at all.\n", encoding="utf-8")
    _patch_git(monkeypatch, root)

    assert apply_upgrade.cmd_record(_record_args(name)) == 0
    text = ledger.read_text(encoding="utf-8")
    assert apply_upgrade.ledger_contains(text, name)
    assert "| Date | Upgrade File | Status | Notes |" in text


def test_a_genuine_prior_row_still_dedups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard #8 wanted deleted survives, re-scoped: a REAL record still skips.

    In the master, `record` retains the pack, so an accidental double-run would
    otherwise write duplicate rows forever.
    """
    root, name = _record_repo(tmp_path, "Fleet Project")
    ledger = root / "docs" / "upgrades" / "upgrades_ledger.md"
    _patch_git(monkeypatch, root)
    assert apply_upgrade.cmd_record(_record_args(name)) == 0
    # Re-create the pack (record deleted it in a fleet project) and record again.
    (root / "docs" / "upgrades" / name).write_text("# Pack\n", encoding="utf-8")
    assert apply_upgrade.cmd_record(_record_args(name)) == 0
    text = ledger.read_text(encoding="utf-8")
    assert text.count("`" + name + "`") == 1, (
        "a genuinely recorded pack must not gain duplicate rows"
    )


def test_list_reports_the_subject_set_and_names_unrecognised_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression test 3: a clean bill means nothing without the count examined."""
    root, _name = _record_repo(tmp_path, "Fleet Project")
    packs_dir = root / "docs" / "upgrades"
    (packs_dir / "upgrade_bmad_dev_story_promotion_260724_1934.md").write_text(
        "# real pack, nonconforming name\n", encoding="utf-8"
    )
    monkeypatch.setattr(apply_upgrade, "get_project_root", lambda: root)

    assert apply_upgrade.cmd_list(argparse.Namespace()) == 0
    out = capsys.readouterr().out
    assert "Examined 2 .md file(s)" in out
    assert "[UNRECOGNISED] upgrade_bmad_dev_story_promotion_260724_1934.md" in out


# ---------------------------------------------------------------------------
# ONLY the master disseminates (owner rule 2026-08-29, C7 / AGENTS 6+9)
# ---------------------------------------------------------------------------


def test_disseminate_refuses_outside_the_master_and_states_the_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = _record_repo(tmp_path, "Some Fleet Project")
    monkeypatch.setattr(apply_upgrade, "get_project_root", lambda: root)
    args = argparse.Namespace(only=None, dry_run=True, yes=True, approved_by_user=False)
    assert apply_upgrade.cmd_disseminate(args) == 1
    out = capsys.readouterr().out
    assert "ONLY the master template disseminates" in out
    assert "DRAFT upgrade packs and push them to the master" in out
    assert "the answer is already no" in out


def test_prune_refuses_outside_the_master(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = _record_repo(tmp_path, "Some Fleet Project")
    monkeypatch.setattr(apply_upgrade, "get_project_root", lambda: root)
    args = argparse.Namespace(dry_run=True, yes=True)
    assert apply_upgrade.cmd_prune(args) == 1
    assert "ONLY the master template prunes" in capsys.readouterr().out


def test_a_missing_bmad_config_fails_closed_not_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No _bmad/config.toml -> project_name None -> NOT the master -> refuse."""
    root = tmp_path / "bare"
    (root / "docs" / "upgrades").mkdir(parents=True)
    monkeypatch.setattr(apply_upgrade, "get_project_root", lambda: root)
    args = argparse.Namespace(only=None, dry_run=True, yes=True, approved_by_user=False)
    assert apply_upgrade.cmd_disseminate(args) == 1


# ---------------------------------------------------------------------------
# Findings from the 2026-08-29 six-skeptic verification pass, pinned as tests
# ---------------------------------------------------------------------------


def test_recorded_skip_warning_names_the_unreachable_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The corrected-pack-unreachable trap must be ANNOUNCED, not a silent count.

    The skeptic pass proved this behaviour had no binding test: deleting the whole
    [RECORDED-SKIP] block left the suite green. A sibling whose ledger records a pack
    (file deleted, as record does in the fleet) must be named in the plan output.
    """
    master = tmp_path / "master"
    (master / "_bmad").mkdir(parents=True)
    (master / "_bmad" / "config.toml").write_text(
        '[core]\nproject_name = "_NEON dev stack"\n', encoding="utf-8"
    )
    packs = master / "docs" / "upgrades"
    packs.mkdir(parents=True)
    name = "upgrade_instructions_corrected_260829_0100.md"
    (packs / name).write_text("# corrected content v2\n", encoding="utf-8")

    sibling = tmp_path / "Fleet Sib"
    (sibling / "docs" / "upgrades").mkdir(parents=True)
    (sibling / "AGENTS.md").write_text("# c\n", encoding="utf-8")
    (sibling / "docs" / "upgrades" / "upgrades_ledger.md").write_text(
        "| Date | Upgrade File | Status | Notes |\n"
        "| :--- | :--- | :--- | :--- |\n"
        f"| 2026-08-20 | `{name}` | Applied |  |\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(apply_upgrade, "get_project_root", lambda: master)
    monkeypatch.setattr(apply_upgrade, "discover_fleet_projects", lambda root: [sibling])
    monkeypatch.setattr(apply_upgrade, "assert_fleet_is_whole", lambda *a, **k: 0)

    args = argparse.Namespace(only=None, dry_run=True, yes=True, approved_by_user=False)
    apply_upgrade.cmd_disseminate(args)
    out = capsys.readouterr().out
    assert "[RECORDED-SKIP]" in out and name in out and "hand-deliver" in out, (
        f"the unreachable pack must be named with the hand-delivery warning: {out[-600:]}"
    )


def test_check_reports_a_stale_epic_row_as_drift(tmp_path: Path, monkeypatch) -> None:
    """The skeptic pass proved `check` blessed exactly the epic value `sync` corrects."""
    import sync_sprint_status as sync_mod

    artifacts = tmp_path / "_bmad-output" / "implementation-artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "6-1-a.story.md").write_text("Status: done\n", encoding="utf-8")
    (artifacts / "sprint-status.yaml").write_text(
        "project: T\ndevelopment_status:\n  epic-6: backlog\n  6-1-a: done\n",
        encoding="utf-8",
    )
    planning = tmp_path / "_bmad-output" / "planning-artifacts"
    planning.mkdir(parents=True)
    (planning / "epics.md").write_text("### Story 6.1: A\n", encoding="utf-8")

    monkeypatch.setattr(sync_mod, "get_project_root", lambda: tmp_path)
    rc = sync_mod.cmd_check(argparse.Namespace())
    assert rc == 1, "a stale epic row must be DRIFT, not [OK]"


# ---------------------------------------------------------------------------
# prune ARCHIVES absorbed packs, it does not delete them (owner decision 2026-08-30)
# ---------------------------------------------------------------------------


def _fleet_with_recorded_pack(tmp_path: Path, pack_name: str) -> Path:
    """A template holding one pack, recorded in every one of 5 sibling ledgers."""
    root = tmp_path / "_NEON dev stack"
    (root / "_bmad").mkdir(parents=True)
    (root / "_bmad" / "config.toml").write_text(
        f'[core]\nproject_name = "{apply_upgrade.TEMPLATE_PROJECT_NAME}"\n', encoding="utf-8"
    )
    (root / "config.yaml").write_text("fleet:\n  expected_min_projects: 5\n", encoding="utf-8")
    packs = root / "docs" / "upgrades"
    packs.mkdir(parents=True)
    (packs / pack_name).write_text(f"# {pack_name}\n", encoding="utf-8")
    for i in range(5):
        sibling = tmp_path / f"project-{i}"
        (sibling / "docs" / "upgrades").mkdir(parents=True)
        (sibling / "AGENTS.md").write_text("# rules\n", encoding="utf-8")
        (sibling / "docs" / "upgrades" / apply_upgrade.LEDGER_NAME).write_text(
            "| Date | Upgrade File | Status | Notes |\n"
            "| :--- | :--- | :--- | :--- |\n"
            f"| 2026-08-20 | `{pack_name}` | Applied |  |\n",
            encoding="utf-8",
        )
    return root


def _prune_args(**kw) -> argparse.Namespace:
    defaults = {"dry_run": False, "yes": True}
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def test_prune_moves_an_absorbed_pack_to_the_archive_subfolder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The owner's correction: a pack is evidence of a defect and its fix, and git
    history is not where an agent goes looking for one -- archive/ is."""
    name = "upgrade_instructions_thing_260820_0900.md"
    root = _fleet_with_recorded_pack(tmp_path, name)
    _patch_git(monkeypatch, root)

    assert apply_upgrade.cmd_prune(_prune_args()) == 0

    live = root / "docs" / "upgrades" / name
    archived = root / "docs" / "upgrades" / "archive" / name
    assert not live.exists(), "an absorbed pack must leave the live library"
    assert archived.exists(), "an absorbed pack must land in docs/upgrades/archive/"
    assert archived.read_text(encoding="utf-8") == f"# {name}\n"


def test_prune_dry_run_says_archive_not_prune_and_moves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    name = "upgrade_instructions_thing_260820_0900.md"
    root = _fleet_with_recorded_pack(tmp_path, name)
    _patch_git(monkeypatch, root)

    assert apply_upgrade.cmd_prune(_prune_args(dry_run=True)) == 0
    out = capsys.readouterr().out
    assert "archive" in out.lower()
    assert (root / "docs" / "upgrades" / name).exists(), "dry-run must move nothing"


def test_prune_refuses_to_overwrite_a_differently_named_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same filename already archived with DIFFERENT content -> refuse, don't clobber."""
    name = "upgrade_instructions_thing_260820_0900.md"
    root = _fleet_with_recorded_pack(tmp_path, name)
    archive_dir = root / "docs" / "upgrades" / "archive"
    archive_dir.mkdir(parents=True)
    (archive_dir / name).write_text("# a DIFFERENT, older version\n", encoding="utf-8")
    _patch_git(monkeypatch, root)

    assert apply_upgrade.cmd_prune(_prune_args()) == 1
    assert (root / "docs" / "upgrades" / name).exists(), "must not delete on a refused collision"
    assert (archive_dir / name).read_text(encoding="utf-8") == "# a DIFFERENT, older version\n"
