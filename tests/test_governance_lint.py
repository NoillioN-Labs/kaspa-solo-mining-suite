"""Unit tests for scripts/utilities/governance_lint.py.

Regression cover for the source walker (pack lint_walker_symlink_crash_260712_1135).
Two fleet projects independently hit the same incident: a dangling POSIX symlink left
behind by a WSL-era `.venv-linux/` made the linter raise `OSError: [WinError 1920]`
mid-walk, CI-blocking every push. The linter was violating the very rule it enforces
(AGENTS 5.5.1: `Path.exists()`/`is_file()` *raise* near legacy symlinks, they do not
return False).
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "utilities"))

import governance_lint  # noqa: E402

SUFFIXES = (".ps1", ".bat", ".cmd")


def test_excluded_dirs_are_pruned(tmp_path: Path) -> None:
    """Files inside vendor/archive trees are never returned."""
    (tmp_path / "live.ps1").write_text("Write-Output 'ok'\n", encoding="ascii")
    for excluded in (".venv-linux", ".venv", "node_modules", "archive"):
        target = tmp_path / excluded
        target.mkdir()
        (target / "vendored.ps1").write_text("Write-Output 'skip'\n", encoding="ascii")

    found = {p.name for p in governance_lint.walk_source_files(tmp_path, SUFFIXES)}

    assert found == {"live.ps1"}


def test_venv_linux_is_excluded() -> None:
    """The dual-venv fleet projects carry a .venv-linux; it must be in the exclude set."""
    assert ".venv-linux" in governance_lint.WALK_EXCLUDE_DIRS


def test_walk_survives_oserror_on_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A path that raises OSError (dangling symlink, WinError 1920) is skipped, not fatal.

    Symlink creation needs elevation/developer mode on Windows, so the raise is injected
    at the probe instead — the failure mode under test is the *unguarded probe*, not the
    link itself.
    """
    (tmp_path / "good.ps1").write_text("Write-Output 'ok'\n", encoding="ascii")
    (tmp_path / "dangling.ps1").write_text("Write-Output 'boom'\n", encoding="ascii")

    real_is_file = Path.is_file

    def exploding_is_file(self: Path) -> bool:
        if self.name == "dangling.ps1":
            raise OSError(1920, "The file cannot be accessed by the system")
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", exploding_is_file)

    found = {p.name for p in governance_lint.walk_source_files(tmp_path, SUFFIXES)}

    assert found == {"good.ps1"}


def test_walk_does_not_flag_itself(tmp_path: Path) -> None:
    """The linter names the patterns it hunts for; it must not scan itself."""
    lint_path = Path(governance_lint.__file__).resolve()
    found = {p.resolve() for p in governance_lint.walk_source_files(lint_path.parent, (".py",))}

    assert lint_path not in found


# ---------------------------------------------------------------------------
# -LiteralPath + wildcard: copies nothing, silently (AGENTS 5.5.1 class)
# ---------------------------------------------------------------------------

def _flag(text: str) -> list[str]:
    result = governance_lint.CheckResult("windows-traps", "t")
    governance_lint.flag_literalpath_wildcards(result, Path("probe.ps1"), text)
    return [f.message for f in result.findings]


def test_literalpath_with_wildcard_is_an_error() -> None:
    """The near-miss: copy nothing -> rename the source away -> junction to an empty dir."""
    messages = _flag('Copy-Item -LiteralPath "$vendor\\*.md" -Destination $target')

    assert len(messages) == 1
    assert "does NOT expand" in messages[0]


def test_unquoted_literalpath_wildcard_is_an_error() -> None:
    assert _flag("Copy-Item -LiteralPath $vendor\\*.md -Destination $t")


def test_wildcard_in_a_different_parameter_is_not_flagged() -> None:
    """`-Filter '*.md'` and `-Pattern` are correct usage. Only the IMMEDIATE argument counts;
    a rule that cried wolf here would be turned off within a day."""
    assert not _flag("Get-ChildItem -LiteralPath $dir -Filter '*.md' -File")
    assert not _flag("Select-String -LiteralPath $p -Pattern '(?m)^\\s*\\.env\\s*$' -Quiet")


def test_path_with_wildcard_is_correct_usage() -> None:
    assert not _flag("Copy-Item -Path (Join-Path $vendor '*.md') -Destination $target")


def _flag_md(text: str) -> list[str]:
    result = governance_lint.CheckResult("windows-traps", "t")
    governance_lint.flag_literalpath_wildcards(result, Path("pack.md"), text, fenced_only=True)
    return [f.message for f in result.findings]


def test_markdown_prose_describing_the_bug_is_not_flagged() -> None:
    """A pack that WARNS about this footgun has to be able to show it in prose."""
    text = 'An earlier draft used `Copy-Item -LiteralPath "$vendor\\*.md"`, which copies nothing.\n'

    assert not _flag_md(text)


def test_markdown_fenced_code_is_flagged() -> None:
    """The fenced snippet is what an agent actually executes."""
    text = '```powershell\nCopy-Item -LiteralPath "$vendor\\*.md" -Destination $t\n```\n'

    assert len(_flag_md(text)) == 1


def test_a_deliberate_counter_example_can_be_suppressed() -> None:
    """Explicit, and impossible to trip by accident."""
    text = (
        "```powershell\n"
        "# LINT-IGNORE: this is the BUG being described, not an instruction\n"
        'Copy-Item -LiteralPath "$vendor\\*.md" -Destination $t\n'
        "```\n"
    )

    assert not _flag_md(text)


# ---------------------------------------------------------------------------
# C:\ hardcoding / unscoped tempfile (AGENTS 5.5.1): generated files must not
# default onto the OS drive.
# ---------------------------------------------------------------------------

def _flag_c_drive(text: str) -> list[str]:
    result = governance_lint.CheckResult("windows-traps", "t")
    governance_lint.flag_c_drive_and_tempfile_defaults(result, Path("probe.py"), text)
    return [f.message for f in result.findings]


def test_hardcoded_c_drive_string_is_flagged() -> None:
    # LINT-IGNORE: the fixture string is the bug being tested for, not real usage
    assert _flag_c_drive('OUT_DIR = "C:\\\\renders"\n')


def test_hardcoded_c_drive_forward_slash_is_flagged() -> None:
    # LINT-IGNORE: the fixture string is the bug being tested for, not real usage
    assert _flag_c_drive("OUT_DIR = 'C:/renders'\n")


def test_d_drive_string_is_not_flagged() -> None:
    assert not _flag_c_drive('OUT_DIR = "D:\\\\renders"\n')


def test_tempfile_gettempdir_is_flagged() -> None:
    # LINT-IGNORE: the fixture string is the bug being tested for, not real usage
    messages = _flag_c_drive("scratch = tempfile.gettempdir()\n")

    assert len(messages) == 1
    assert "OS default" in messages[0]


def test_tempfile_mkstemp_without_dir_is_flagged() -> None:
    # LINT-IGNORE: the fixture string is the bug being tested for, not real usage
    assert _flag_c_drive("fd, path = tempfile.mkstemp(suffix='.mp4')\n")


def test_tempfile_mkstemp_with_dir_is_not_flagged() -> None:
    assert not _flag_c_drive("fd, path = tempfile.mkstemp(suffix='.mp4', dir=project_tmp)\n")


def test_c_drive_lint_ignore_suppresses_the_line() -> None:
    text = (
        "# LINT-IGNORE: documenting the bug, not writing it\n"
        'OUT_DIR = "C:\\\\renders"\n'
    )

    assert not _flag_c_drive(text)


# ---------------------------------------------------------------------------
# architecture-map (AGENTS 5.8): the map must be singular and demonstrably alive
# ---------------------------------------------------------------------------

MAP_REL = "_bmad-output/planning-artifacts/ARCHITECTURE.md"


def _repo(tmp_path: Path, *, map_body: str | None = None, extras: list[str] | None = None) -> Path:
    planning = tmp_path / "_bmad-output" / "planning-artifacts"
    planning.mkdir(parents=True)
    (tmp_path / "config.yaml").write_text(
        "knowledge:\n"
        f"  architecture_map: \"{MAP_REL}\"\n"
        "  architecture_max_age_days: 90\n",
        encoding="utf-8",
    )
    if map_body is not None:
        (tmp_path / MAP_REL).write_text(map_body, encoding="utf-8")
    for name in extras or []:
        (planning / name).write_text("# other\n", encoding="utf-8")
    return tmp_path


def _map_body(reviewed: str) -> str:
    return f"---\nlast_reviewed: {reviewed}\n---\n\n# Architecture\n\nComponents...\n"


def test_missing_architecture_map_is_flagged(tmp_path: Path) -> None:
    result = governance_lint.check_architecture_map(_repo(tmp_path))

    assert any("no architecture map" in f.message for f in result.findings)


def test_a_second_architecture_doc_is_flagged(tmp_path: Path) -> None:
    """One fleet project had drifted to four architecture docs. Two maps that
    disagree are worse than none, because nothing says which one wins.

    Note the extras must differ from ARCHITECTURE.md by more than case: Windows is
    case-insensitive, so an `architecture.md` fixture silently *overwrites* the map
    rather than sitting beside it (AGENTS 5.5.1 territory).
    """
    root = _repo(
        tmp_path,
        map_body=_map_body(datetime.now(UTC).strftime("%Y-%m-%d")),
        extras=["ARCHITECTURE-Blender-MCP.md", "solution-architecture.md"],
    )

    result = governance_lint.check_architecture_map(root)
    messages = [f.message for f in result.findings]

    assert len(messages) == 2
    assert all("second architecture document" in m for m in messages)


def test_map_without_last_reviewed_is_flagged(tmp_path: Path) -> None:
    root = _repo(tmp_path, map_body="# Architecture\n\nNo frontmatter.\n")

    result = governance_lint.check_architecture_map(root)

    assert any("last_reviewed" in f.message for f in result.findings)


def test_stale_map_is_flagged(tmp_path: Path) -> None:
    """'Is the map true?' is not scriptable. 'Has anyone claimed it's true lately?' is."""
    old = (datetime.now(UTC) - timedelta(days=120)).strftime("%Y-%m-%d")
    root = _repo(tmp_path, map_body=_map_body(old))

    result = governance_lint.check_architecture_map(root)

    assert any("stale by definition" in f.message for f in result.findings)


def test_fresh_singular_map_passes(tmp_path: Path) -> None:
    fresh = datetime.now(UTC).strftime("%Y-%m-%d")
    root = _repo(tmp_path, map_body=_map_body(fresh))

    assert not governance_lint.check_architecture_map(root).findings


# ---------------------------------------------------------------------------
# knowledge.* path resolution (AGENTS 6)
#
# The D:\Projects relocation moved the template out of its old parent, so the
# sibling-relative `skills_registry: "../_NEON_skills/skills"` still RESOLVED -- just
# to nothing. memory_lint's skills checks SKIP on a missing registry, and
# check_memory_cache forwarded only findings, so the linter printed a clean
# `0 error(s), 0 warning(s)` over a broken knowledge base. Both halves are covered here.
# ---------------------------------------------------------------------------


def _knowledge_repo(tmp_path: Path, memory_store: str, skills_registry: str) -> Path:
    root = tmp_path / "repo"
    (root / "docs" / "memory").mkdir(parents=True)
    (root / "config.yaml").write_text(
        "knowledge:\n"
        f"  memory_store: \"{memory_store}\"\n"
        f"  skills_registry: \"{skills_registry}\"\n"
        "  memory_max_page_bytes: 800\n",
        encoding="utf-8",
    )
    return root


def test_knowledge_paths_pass_when_both_resolve(tmp_path: Path) -> None:
    root = _knowledge_repo(tmp_path, "docs/memory", "../registry/skills")
    (tmp_path / "registry" / "skills").mkdir(parents=True)

    assert not governance_lint.check_knowledge_paths(root).findings


def test_missing_in_repo_knowledge_path_is_an_error(tmp_path: Path) -> None:
    """An in-repo path must exist wherever the repo is checked out."""
    root = _knowledge_repo(tmp_path, "docs/does_not_exist", "../registry/skills")
    (tmp_path / "registry" / "skills").mkdir(parents=True)

    findings = governance_lint.check_knowledge_paths(root).findings

    assert [f.severity for f in findings] == [governance_lint.SEVERITY_ERROR]
    assert "memory_store" in findings[0].message


def test_missing_out_of_repo_knowledge_path_is_a_warning_not_an_error(tmp_path: Path) -> None:
    """The exact regression the relocation caused -- but it must NOT be an ERROR.

    The shared skills registry is a separate git repo that legitimately does not exist
    on a CI runner; erroring would block every push forever. A WARNING still moves the
    summary off `0 warning(s)`, which is what kills the false green.
    """
    root = _knowledge_repo(tmp_path, "docs/memory", "../_NEON_skills/skills")

    findings = governance_lint.check_knowledge_paths(root).findings

    assert [f.severity for f in findings] == [governance_lint.SEVERITY_WARNING]
    assert "skills_registry" in findings[0].message


def test_knowledge_path_probe_survives_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """is_dir() RAISES WinError 1920 on a dangling link; a check that dies never reported."""
    root = _knowledge_repo(tmp_path, "docs/memory", "../registry/skills")

    def exploding_is_dir(self: Path) -> bool:
        raise OSError(1920, "The file cannot be accessed by the system")

    monkeypatch.setattr(Path, "is_dir", exploding_is_dir)

    result = governance_lint.check_knowledge_paths(root)  # must not raise

    assert len(result.findings) == 2


def test_memory_cache_forwards_skipped_subchecks(tmp_path: Path) -> None:
    """A SKIPPED sub-check is not a passing sub-check (AGENTS 5.5.1).

    Before this, memory_lint's skip reasons were dropped on the floor and a dangling
    skills registry read as PASS.
    """
    root = _knowledge_repo(tmp_path, "docs/memory", "../nowhere/skills")
    (root / "docs" / "memory" / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")

    result = governance_lint.check_memory_cache(root)

    skipped = [f for f in result.findings if "SKIPPED" in f.message]
    assert skipped, "a skipped memory_lint sub-check must surface as a finding"
    assert any("registry" in f.message for f in skipped)
    assert all(f.severity == governance_lint.SEVERITY_WARNING for f in skipped)


# ---------------------------------------------------------------------------
# Clone inheritance: operating knowledge vs provenance (AGENTS 7)
#
# The template must ship a child the knowledge it needs to work inside this
# structure, and NOT the record of how the template itself was built. bootstrap
# fails closed on `metadata.inherit`, which makes an undeclared page vanish from
# every future clone silently -- so the declaration is enforced here instead.
# ---------------------------------------------------------------------------


def _template_repo(tmp_path: Path, pages: dict[str, str]) -> Path:
    """A repo that identifies as the master template, with the given memory pages."""
    root = tmp_path / "repo"
    (root / "_bmad").mkdir(parents=True)
    (root / "_bmad" / "config.toml").write_text(
        f'[core]\nproject_name = "{governance_lint.TEMPLATE_PROJECT_NAME}"\n', encoding="utf-8"
    )
    mem = root / "docs" / "memory"
    mem.mkdir(parents=True)
    (root / "config.yaml").write_text(
        'knowledge:\n  memory_store: "docs/memory"\n  memory_max_page_bytes: 800\n', encoding="utf-8"
    )
    body = "**Fact:** x\n\n**Why:** y\n\n**Authority:** AGENTS 7\n"
    for name, front in pages.items():
        (mem / name).write_text(f"---\n{front}---\n\n{body}", encoding="utf-8")
    return root


def test_declared_inheritance_passes(tmp_path: Path) -> None:
    root = _template_repo(tmp_path, {
        "keep.md": "name: keep\nmetadata:\n  type: project\n  inherit: true\n",
        "drop.md": "name: drop\nmetadata:\n  type: project\n  inherit: false\n",
    })
    assert not governance_lint.check_memory_inheritance_declared(root).findings


def test_undeclared_inheritance_is_an_error(tmp_path: Path) -> None:
    """The silent-drop failure mode: an undeclared page disappears from every clone."""
    root = _template_repo(tmp_path, {
        "silent.md": "name: silent\nmetadata:\n  type: project\n",
    })
    findings = governance_lint.check_memory_inheritance_declared(root).findings
    assert [f.severity for f in findings] == [governance_lint.SEVERITY_ERROR]
    assert "metadata.inherit" in findings[0].message


def test_non_boolean_inheritance_is_an_error(tmp_path: Path) -> None:
    root = _template_repo(tmp_path, {
        "fuzzy.md": "name: fuzzy\nmetadata:\n  type: project\n  inherit: maybe\n",
    })
    findings = governance_lint.check_memory_inheritance_declared(root).findings
    assert [f.severity for f in findings] == [governance_lint.SEVERITY_ERROR]
    assert "boolean" in findings[0].message


def test_inheritance_check_is_template_scoped(tmp_path: Path) -> None:
    """The fleet's ~50 existing pages predate the flag; demanding it everywhere would
    fail lint in every project for no benefit."""
    root = _template_repo(tmp_path, {"x.md": "name: x\nmetadata:\n  type: project\n"})
    (root / "_bmad" / "config.toml").write_text(
        '[core]\nproject_name = "Horse racing tips"\n', encoding="utf-8"
    )
    result = governance_lint.check_memory_inheritance_declared(root)
    assert result.skipped and not result.findings


def test_every_template_memory_page_declares_inheritance() -> None:
    """Live check against this repo: the real pages must all be classified."""
    result = governance_lint.check_memory_inheritance_declared(Path("."))
    assert not result.findings, [f.message for f in result.findings]
    assert not result.skipped, "this IS the template; the check must not skip here"


# ---------------------------------------------------------------------------
# adr-refs: no master ADR numbers in anything a clone inherits
#
# Measured 2026-07-28: NEON video creator has 52 of its own ADRs, so all nine
# master ids cited by the inherited scripts RESOLVED there -- every one to the
# wrong document. A dangling pointer is detectable; a resolving-but-wrong one
# is not, which is why this is an ERROR rather than a warning.
# ---------------------------------------------------------------------------


def test_adr_reference_in_an_inherited_script_is_an_error(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "scripts" / "utilities").mkdir(parents=True)
    (root / "scripts" / "utilities" / "thing.py").write_text(
        '"""Does a thing (ADR-0016)."""\n', encoding="utf-8"
    )
    findings = governance_lint.check_adr_references(root).findings
    assert [f.severity for f in findings] == [governance_lint.SEVERITY_ERROR]
    assert "ADR-0016" in findings[0].message


def test_agents_section_citation_is_accepted(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "scripts" / "utilities").mkdir(parents=True)
    (root / "scripts" / "utilities" / "thing.py").write_text(
        '"""Does a thing (AGENTS 5.5.1)."""\n', encoding="utf-8"
    )
    assert not governance_lint.check_adr_references(root).findings


def test_lint_ignore_allows_a_deliberate_adr_reference(tmp_path: Path) -> None:
    """A file explaining the rule must be able to show the shape it forbids."""
    root = tmp_path / "repo"
    (root / "scripts" / "utilities").mkdir(parents=True)
    (root / "scripts" / "utilities" / "thing.py").write_text(
        '# LINT-IGNORE: naming the pattern, not citing it\nX = "ADR-0016"\n', encoding="utf-8"
    )
    assert not governance_lint.check_adr_references(root).findings


def test_this_repo_has_no_adr_numbers_in_inherited_files() -> None:
    """Live check: the constitution and every inherited script must be clean."""
    findings = governance_lint.check_adr_references(Path(".")).findings
    assert not findings, [f"{f.path}: {f.message}" for f in findings]


def _bare_repo(tmp_path: Path, *, is_template: bool) -> Path:
    """A minimal repo that either identifies as the master template, or does not."""
    root = tmp_path / "repo"
    (root / "_bmad").mkdir(parents=True)
    name = governance_lint.TEMPLATE_PROJECT_NAME if is_template else "some-client-project"
    (root / "_bmad" / "config.toml").write_text(
        f'[core]\nproject_name = "{name}"\n', encoding="utf-8"
    )
    return root


@pytest.mark.parametrize("relpath", governance_lint.ADR_REF_SCAN_TEMPLATE_ONLY_FILES)
def test_adr_reference_in_an_inherited_config_file_is_an_error_in_the_master(
    tmp_path: Path, relpath: str
) -> None:
    """The master ships these verbatim, so a number here is a number nobody chose."""
    root = _bare_repo(tmp_path, is_template=True)
    target = root / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# coverage ratchet (ADR-0015)\n", encoding="utf-8")

    findings = governance_lint.check_adr_references(root).findings
    assert [f.severity for f in findings] == [governance_lint.SEVERITY_ERROR]
    assert "ADR-0015" in findings[0].message


@pytest.mark.parametrize("relpath", governance_lint.ADR_REF_SCAN_TEMPLATE_ONLY_FILES)
def test_a_clone_may_cite_its_own_adrs_in_these_files(tmp_path: Path, relpath: str) -> None:
    """The half of the rule that keeps it from crying wolf.

    Once bootstrap has run, config.yaml and pyproject.toml are the PROJECT'S files and a
    citation in them resolves correctly. Erroring here would train people to delete good
    references -- so the scan is master-only, and this test is what pins that down.
    """
    root = _bare_repo(tmp_path, is_template=False)
    target = root / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# coverage ratchet (ADR-0015)\n", encoding="utf-8")

    assert not governance_lint.check_adr_references(root).findings


# ---------------------------------------------------------------------------
# temp_and_disk_discipline S5 -- narrow the C:-literal check, keep tempfile universal
# ---------------------------------------------------------------------------

def test_c_drive_literal_is_exempt_in_tests_and_generated_artifacts() -> None:
    """A literal C: path is a DESTINATION in app code and INPUT DATA in a test.

    The originating project had 53 such warnings, 50 of them noise, and that volume is
    exactly why its 3 genuine tempfile findings sat unfixed for three days. Narrowing
    beats suppressing: a check nobody reads is worse than no check, because it looks
    like coverage.
    """
    exempt = governance_lint._is_c_drive_literal_exempt
    assert exempt(Path("tests") / "test_paths.py") is True
    assert exempt(Path("backend") / "tests" / "conftest.py") is True
    assert exempt(Path("scripts") / "test_probe.py") is True
    assert exempt(Path("backend") / "render_generated.py") is True
    # Application code is NOT exempt -- that is where a C: literal is a real defect.
    assert exempt(Path("backend") / "core" / "renderer.py") is False


def test_tempfile_checks_still_fire_inside_tests_while_the_literal_does_not() -> None:
    """The scope asymmetry IS the fix, so it gets its own test.

    Narrowing the literal check while narrowing the tempfile check too would throw away
    the half of the rule that actually caught bugs: a tempfile call with no dir= is
    actionable no matter who writes it.
    """
    # LINT-IGNORE: fixture data, not a call site -- this string IS the thing under test.
    text = 'p = "C:\\Temp\\fixture"\nd = tempfile.mkdtemp()\n'

    in_test = governance_lint.CheckResult("windows-traps", "t")
    governance_lint.flag_c_drive_and_tempfile_defaults(
        in_test, Path("tests") / "test_thing.py", text
    )
    messages = " ".join(f.message for f in in_test.findings)
    assert "hardcodes a C: path" not in messages, "literal check must be exempt in tests/"
    assert "no dir=" in messages, (
        "the tempfile call shape is a real finding wherever it is written; exempting it "
        "too would discard the half of the rule that caught actual bugs"
    )

    in_app = governance_lint.CheckResult("windows-traps", "t")
    governance_lint.flag_c_drive_and_tempfile_defaults(
        in_app, Path("backend") / "core" / "thing.py", text
    )
    app_messages = " ".join(f.message for f in in_app.findings)
    assert "hardcodes a C: path" in app_messages, "app code must still be flagged"


# ---------------------------------------------------------------------------
# temp_and_disk_discipline S4c -- test temp-root ceiling
# ---------------------------------------------------------------------------

def _write_config(root: Path, body: str) -> None:
    (root / "config.yaml").write_text(body, encoding="utf-8")


def test_temp_root_check_skips_when_unconfigured_and_says_why(tmp_path: Path) -> None:
    """A check that did not run is not a check that passed (AGENTS 6).

    Unset temp_root must SKIP with a reason, never search for "some temp dir" -- a sweep
    that guesses eventually deletes something it should not.
    """
    _write_config(tmp_path, "testing:\n  coverage:\n    mode: advisory\n")
    result = governance_lint.check_test_temp_root(tmp_path)
    assert result.skipped is True
    assert "temp_root" in result.skip_reason


def test_temp_root_check_warns_only_above_the_ceiling(tmp_path: Path) -> None:
    temp = tmp_path / "pytest_tmp"
    temp.mkdir()
    (temp / "blob.bin").write_bytes(b"x" * 2048)

    over = "testing:\n  temp_root: 'pytest_tmp'\n  temp_root_max_gb: 0.000001\n"
    _write_config(tmp_path, over)
    result = governance_lint.check_test_temp_root(tmp_path)
    assert result.skipped is False
    assert any("over the" in f.message for f in result.findings), "should warn above ceiling"
    assert all(
        f.severity == governance_lint.SEVERITY_WARNING for f in result.findings
    ), "an oversized temp root is a smell, not a broken build -- WARNING, never ERROR"

    under = "testing:\n  temp_root: 'pytest_tmp'\n  temp_root_max_gb: 10.0\n"
    _write_config(tmp_path, under)
    assert governance_lint.check_test_temp_root(tmp_path).findings == []
