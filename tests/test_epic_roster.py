"""An epic is not done because its WRITTEN stories are (sync_sprint_status.py).

Two stacked defects, both verified in this repo before the fix:

* **Derive-from-files:** an epic's status came from the `*.story.md` files on disk,
  and a story file only exists once someone has written that story -- so an epic
  whose first two (of ten) stories were done read as `done`. Every input the
  generator had said done; the answer was still false about the epic, in the file
  AGENTS 6 calls the sole numbering registry.
* **Latching:** the epic value, once written, was preserved verbatim on every later
  sync ("epic-level entries are preserved as-is") -- so a wrong `done` could never
  be corrected, because hand-editing generated output is forbidden.

The fix reads the epic's intended roster from the epics document (unwritten
stories are unstarted work, not absent work), re-derives epic status every run
(drift is reported, loudly), and refuses to fall back silently when the roster is
missing or ambiguous (AGENTS 5.5.1).

Origin: Nineteen's Epic 10 retrospective, absorbed at the master 2026-08-29.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "utilities"))

import pytest  # noqa: E402
import sync_sprint_status as sync  # noqa: E402

# ---------------------------------------------------------------------------
# derive_epic_status with a roster
# ---------------------------------------------------------------------------


def test_the_original_defect_pinned_two_done_of_ten_reads_done_without_a_roster() -> None:
    """The defect, pinned exactly: with no roster the old answer comes back."""
    assert sync.derive_epic_status(["done", "done"]) == "done"


def test_a_roster_forces_in_progress_while_stories_are_unwritten() -> None:
    assert sync.derive_epic_status(["done", "done"], roster_size=10) == "in-progress"


def test_a_complete_epic_still_closes() -> None:
    assert sync.derive_epic_status(["done", "done", "done"], roster_size=3) == "done"


def test_an_epic_with_no_written_stories_is_backlog_not_done() -> None:
    assert sync.derive_epic_status([], roster_size=5) == "backlog"


def test_roster_none_preserves_old_behaviour_for_other_callers() -> None:
    assert sync.derive_epic_status(["backlog", "backlog"], roster_size=None) == "backlog"
    assert sync.derive_epic_status(["in-progress"], roster_size=None) == "in-progress"


# ---------------------------------------------------------------------------
# epic_roster reads the real document shape
# ---------------------------------------------------------------------------


def test_both_heading_depths_parse_and_a_fifth_hash_does_not(tmp_path: Path) -> None:
    d = tmp_path / "_bmad-output" / "planning-artifacts"
    d.mkdir(parents=True)
    (d / "epics.md").write_text(
        "## Epic 6: Things\n"
        "### Story 6.1: First\n"
        "#### Story 6.2: Second (four hashes is a real depth)\n"
        "##### Story 6.3: NOT a story heading at five hashes\n"
        "### Story 7.1: Other epic\n",
        encoding="utf-8",
    )
    roster, problem = sync.epic_roster(tmp_path)
    assert problem is None
    assert roster == {6: 2, 7: 1}


def test_a_missing_epics_document_is_reported_not_guessed(tmp_path: Path) -> None:
    (tmp_path / "_bmad-output" / "planning-artifacts").mkdir(parents=True)
    roster, problem = sync.epic_roster(tmp_path)
    assert roster == {}
    assert problem is not None and "no epics document" in problem


def test_two_epics_documents_are_ambiguous_not_merged(tmp_path: Path) -> None:
    d = tmp_path / "_bmad-output" / "planning-artifacts"
    d.mkdir(parents=True)
    (d / "epics.md").write_text("### Story 1.1: A\n", encoding="utf-8")
    (d / "old-epics.md").write_text("### Story 1.1: A\n### Story 1.2: B\n", encoding="utf-8")
    roster, problem = sync.epic_roster(tmp_path)
    assert roster == {}
    assert problem is not None and "more than one" in problem


def test_a_document_with_no_story_headings_says_so(tmp_path: Path) -> None:
    d = tmp_path / "_bmad-output" / "planning-artifacts"
    d.mkdir(parents=True)
    (d / "epics.md").write_text("# Epics\n\nProse only.\n", encoding="utf-8")
    roster, problem = sync.epic_roster(tmp_path)
    assert roster == {}
    assert problem is not None and "no 'Story N.M:' headings" in problem


def test_the_real_roster_control_the_masters_own_epics_document_parses() -> None:
    """The reader must parse THIS project's actual epics.md, not just fixtures.

    Skips -- with the reason -- on a fresh clone whose bootstrap leaves no epics
    document: empty is a valid state there, and failing would re-create the
    fresh-clone defect repaired on 2026-08-16 ('empty is valid; vacuous is not').
    """
    roster, problem = sync.epic_roster(REPO)
    if problem is not None and "no epics document" in problem:
        pytest.skip(f"fresh-clone state: {problem}")
    assert problem is None, f"the master's own epics document failed to parse: {problem}"
    story_files = sync.collect_stories(sync.artifacts_dir(REPO))[0]
    for epic in {s.epic for s in story_files}:
        assert epic in roster, (
            f"epic {epic} has story files on disk but no roster entry -- the epics "
            "document is behind (this is the roster-behind flag's job at sync time; "
            "at test time it means fix the document)"
        )


# ---------------------------------------------------------------------------
# build_development_status: un-latching + loud fallbacks
# ---------------------------------------------------------------------------


def _story(key: str, epic: int, story: int, status: str) -> sync.StoryInfo:
    return sync.StoryInfo(
        key=key, epic=epic, story=story, status=status, status_missing=False,
        path=Path(f"{key}.story.md"),
    )


def test_a_latched_wrong_epic_value_is_corrected_and_reported_as_drift() -> None:
    """Defect B: the old code preserved 'done' forever; now it re-derives."""
    stories = [_story("6-1-a", 6, 1, "done"), _story("6-2-b", 6, 2, "done")]
    ordered, flags = sync.build_development_status(
        stories, {"epic-6": "done"}, {6: 10}, None
    )
    assert ("epic-6", "in-progress") in ordered, "the latched 'done' must be re-derived"
    assert any("Epic status drift" in f and "epic-6" in f for f in flags)


def test_an_unchanged_epic_value_reports_no_drift() -> None:
    stories = [_story("6-1-a", 6, 1, "done")]
    ordered, flags = sync.build_development_status(stories, {"epic-6": "done"}, {6: 1}, None)
    assert ("epic-6", "done") in ordered
    assert not any("drift" in f.lower() for f in flags)


def test_a_missing_roster_falls_back_LOUDLY_not_silently() -> None:
    stories = [_story("6-1-a", 6, 1, "done")]
    _ordered, flags = sync.build_development_status(
        stories, {}, None, "no epics document under _bmad-output/planning-artifacts/"
    )
    assert any("Epic roster unavailable" in f and "cannot see unwritten stories" in f for f in flags)


def test_more_story_files_than_roster_entries_is_flagged() -> None:
    stories = [_story("6-1-a", 6, 1, "done"), _story("6-2-b", 6, 2, "done")]
    _ordered, flags = sync.build_development_status(stories, {}, {6: 1}, None)
    assert any("roster is behind" in f for f in flags)


def test_retrospective_rows_are_still_preserved_verbatim() -> None:
    """Un-latching applies to epic-N rows ONLY; retros have no derivation source."""
    stories = [_story("6-1-a", 6, 1, "done")]
    ordered, _flags = sync.build_development_status(
        stories, {"epic-6-retrospective": "backlog"}, {6: 1}, None
    )
    assert ("epic-6-retrospective", "backlog") in ordered
