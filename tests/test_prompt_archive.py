"""Archive-on-write for application LLM prompts (AGENTS 5.4).

The old rule -- "superseded versions move to the agent's archive/ immediately" -- asked
the author to preserve the previous version at the precise moment they were replacing
it. It failed the way every "remember to clean up afterwards" rule fails: silently,
with no artefact left behind to prove anything went missing. One fleet project reached
8 live files with 7 having no archived copy at all, and nothing ever reported it.

The severities here are asymmetric ON PURPOSE, and that asymmetry is the fix rather
than a compromise. Measured across the fleet 2026-08-16: **5 of 6 projects follow the
OLD timestamped convention correctly**, and their loaders match on those exact names --
one hardcodes `__schema__260522_2222.txt`, two glob `__prompt__..._*`. Flipping the
naming rule fleet-wide would mean renaming 27 files and breaking prompt loading in
three live projects for no functional gain. So:

* missing archived copy -> ERROR   (the real loss of history)
* timestamped live name -> WARNING (grandfathered; new projects start clean)

Every test builds its own tree in `tmp_path`; none reads this repo's own ai_modules.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "utilities"))

import governance_lint  # noqa: E402


def _agent(root: Path, name: str = "10_demo_agent") -> Path:
    agent = root / "backend" / "ai_modules" / name
    (agent / "archive").mkdir(parents=True, exist_ok=True)
    return agent


def _severities(result: governance_lint.CheckResult, severity: str) -> list[str]:
    return [f.message for f in result.findings if f.severity == severity]


def _errors(result: governance_lint.CheckResult) -> list[str]:
    return _severities(result, governance_lint.SEVERITY_ERROR)


def _warnings(result: governance_lint.CheckResult) -> list[str]:
    return _severities(result, governance_lint.SEVERITY_WARNING)


def test_a_live_prompt_with_no_archived_copy_is_an_error(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    (agent / "10_demo_agent__prompt__.md").write_text("x", encoding="utf-8")
    errors = _errors(governance_lint.check_prompt_archive(tmp_path))
    assert len(errors) == 1 and "NO archived copy" in errors[0]


def test_a_live_prompt_with_an_archived_copy_is_clean(tmp_path: Path) -> None:
    """Stem match, not name equality -- the archived copy is timestamped, the live one is not."""
    agent = _agent(tmp_path)
    (agent / "10_demo_agent__prompt__.md").write_text("x", encoding="utf-8")
    (agent / "archive" / "10_demo_agent__prompt___260711_0036.md").write_text("x", encoding="utf-8")
    result = governance_lint.check_prompt_archive(tmp_path)
    assert _errors(result) == [] and _warnings(result) == []


def test_a_timestamped_live_file_warns_but_never_errors(tmp_path: Path) -> None:
    """The grandfather clause. Five of six fleet projects are in exactly this state.

    Making this an ERROR would demand 27 renames across four live projects and break
    three loaders -- so the check would be telling correct, working projects they are
    broken. That is how a gate gets disabled.
    """
    agent = _agent(tmp_path)
    (agent / "10_demo_agent__prompt__260711_0035.md").write_text("x", encoding="utf-8")
    (agent / "archive" / "10_demo_agent__prompt___260711_0036.md").write_text("x", encoding="utf-8")
    result = governance_lint.check_prompt_archive(tmp_path)
    assert _errors(result) == [], "a legacy timestamped name must NEVER be an error"
    assert len(_warnings(result)) == 1 and "GRANDFATHERED" in _warnings(result)[0]


def test_one_agents_archive_does_not_vouch_for_another(tmp_path: Path) -> None:
    """Without per-agent scoping the check reads as passing while covering nothing.

    The agents here deliberately share a stem. An earlier version of this test gave each
    agent a name-prefixed artifact (`10_good_agent__prompt__`), which made it **vacuous**
    -- pooling the archive state across agents could not change the verdict, because the
    stems were already unique per agent. Two agents whose files are named by their
    DIRECTORY rather than by a filename prefix is a real layout (one fleet project uses
    it), and it is the only shape in which this defect can actually bite.
    """
    good = _agent(tmp_path, "10_good_agent")
    (good / "__prompt__.md").write_text("x", encoding="utf-8")
    (good / "archive" / "__prompt___260711_0036.md").write_text("x", encoding="utf-8")

    bad = _agent(tmp_path, "20_bad_agent")
    (bad / "__prompt__.md").write_text("x", encoding="utf-8")

    errors = _errors(governance_lint.check_prompt_archive(tmp_path))
    assert len(errors) == 1, f"expected exactly the unarchived agent to fail, got: {errors}"
    assert "20_bad_agent" in errors[0], f"the wrong agent was flagged: {errors[0]}"


def test_identity_survives_the_marker_being_a_prefix_rather_than_a_suffix(tmp_path: Path) -> None:
    """`__prompt__<name>_<stamp>.md` is as valid as `<name>__prompt__<stamp>.md`.

    Splitting on the marker and keeping what comes BEFORE it collapses every artifact in
    such a project to the stem `__prompt__`, so a single archived file vouches for all of
    them. Stripping the version stamp instead keeps the identity intact.
    """
    agent = _agent(tmp_path, "10_blog")
    (agent / "__prompt__fact_extractor_260728_2200.md").write_text("x", encoding="utf-8")
    (agent / "__prompt__taxonomy_classifier_260814_0230.md").write_text("x", encoding="utf-8")
    # Only the FIRST one is archived.
    (agent / "archive" / "__prompt__fact_extractor_260728_2200.md").write_text("x", encoding="utf-8")

    errors = _errors(governance_lint.check_prompt_archive(tmp_path))
    assert len(errors) == 1, f"the two prompts must not share an identity: {errors}"
    assert "taxonomy_classifier" in errors[0], f"the wrong artifact was flagged: {errors[0]}"


def test_schema_files_are_covered_as_well_as_prompts(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    (agent / "10_demo_agent__schema__.json").write_text("{}", encoding="utf-8")
    errors = _errors(governance_lint.check_prompt_archive(tmp_path))
    assert len(errors) == 1 and "__schema__" in errors[0]


def test_non_artifact_files_in_an_agent_dir_are_ignored(tmp_path: Path) -> None:
    """Agent packages hold real code too; only prompt/schema artifacts are in scope."""
    agent = _agent(tmp_path)
    (agent / "client.py").write_text("x", encoding="utf-8")
    (agent / "__init__.py").write_text("", encoding="utf-8")
    result = governance_lint.check_prompt_archive(tmp_path)
    assert result.skipped is True and "no prompt/schema artifacts" in result.skip_reason


def test_a_project_without_ai_modules_skips_with_a_reason(tmp_path: Path) -> None:
    """A check that did not run must say so rather than report a clean pass (AGENTS 6)."""
    result = governance_lint.check_prompt_archive(tmp_path)
    assert result.skipped is True and "no backend/ai_modules/" in result.skip_reason


def test_every_unarchived_file_is_reported_not_just_the_first(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    for name in ("10_demo_agent__prompt__.md", "10_demo_agent__schema__.json"):
        (agent / name).write_text("x", encoding="utf-8")
    assert len(_errors(governance_lint.check_prompt_archive(tmp_path))) == 2


def test_the_masters_own_example_agent_satisfies_the_new_rule() -> None:
    """The template is the golden image: every clone starts from whatever it ships.

    Deliberately reads the real repo, unlike every other test here -- the point is that
    a new project must not be born already violating the rule its constitution states.
    """
    result = governance_lint.check_prompt_archive(REPO)
    assert _errors(result) == [], f"the master ships an unarchived prompt: {_errors(result)}"
    assert _warnings(result) == [], (
        "the master still ships a timestamped live prompt, so every new project starts "
        f"in the grandfathered state instead of the new one: {_warnings(result)}"
    )


# ---------------------------------------------------------------------------
# prompt_archive_check_defects pack (2026-08-29): the two confirmed defects
# ---------------------------------------------------------------------------


def test_a_grandfathered_live_file_with_an_agents54_archive_is_clean(tmp_path: Path) -> None:
    """The confirmed false-ERROR: archiving a stamped live file appends a SECOND
    stamp, and a single-pass strip left one behind -- so a correctly archived
    legacy file read as unarchived."""
    agent = _agent(tmp_path)
    (agent / "10_demo_agent__prompt__260711_0035.md").write_text("x", encoding="utf-8")
    (agent / "archive" / "10_demo_agent__prompt__260711_0035_260711_0036.md").write_text(
        "x", encoding="utf-8"
    )
    result = governance_lint.check_prompt_archive(tmp_path)
    assert _errors(result) == [], (
        f"a correctly archived grandfathered file must not ERROR: {_errors(result)}"
    )


def test_a_marker_without_trailing_underscores_is_visible(tmp_path: Path) -> None:
    """`10_writer__prompt.txt` is a compliant shape in one fleet project; the old
    `__prompt__` marker could not see it, exempting the file from the whole check."""
    agent = _agent(tmp_path)
    (agent / "10_writer__prompt.txt").write_text("x", encoding="utf-8")
    errors = _errors(governance_lint.check_prompt_archive(tmp_path))
    assert len(errors) == 1 and "10_writer__prompt.txt" in errors[0], (
        "an unarchived prompt in the suffix-less naming shape must be SEEN and flagged"
    )
