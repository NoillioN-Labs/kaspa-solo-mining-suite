"""The sole numbering registry must be checked in BOTH directions.

`sync_sprint_status.py` proves every story FILE has a registry row. Nothing proved
the reverse -- so a story that is done but whose file was never written (or was
renamed away) can be missing from the registry entirely, and an unregistered id is
an id nothing stops a future story from re-using. One fleet project shipped three
such stories: a hand stocktake found them, not a check, and every completion metric
was quietly understated while they were missing.

A gap check is the mechanical form of "the reverse", and it needs no knowledge of
what work exists: if `6-45` is registered then `6-41`..`6-44` must be too. Reading
only the registry's own keys is what makes it free of false positives -- scanning
`task.md` for ids was tried first and is useless, because every date (`06-21`,
`08-05`) matches a story-id regex.

Stated limitation, deliberately not hidden: this catches a missing INTERIOR id, not
a missing HIGHEST one. A brand-new `6-50` that never gets a row stays invisible until
`6-51` appears above it. Closing that needs commit-scope scanning; this is the cheap
90%, and `test_the_highest_id_is_the_documented_blind_spot` pins the boundary so
nobody mistakes it for more.

The seed registry a fresh clone carries is a handful of contiguous stories, so the
registry-level tests below prove only that THIS project is clean. The synthetic-input
tests are what prove the mechanism every clone inherits actually works (AGENTS 11).

A brand-new project has NO stories at all: `bootstrap_project.ps1` deletes every
`*.story.md` and writes `development_status: {}`, then runs the suite as its clone
check. An empty registry is therefore the CORRECT state, not a broken parser, and the
registry-level tests SKIP with a stated reason rather than fail. "Nothing to check"
and "checked and fine" are different answers and only one is evidence, which is why
this is a skip and not a silent pass.

Second stated limitation, created BY that skip and deliberately not hidden: a project
that loses every story file AND has an empty registry is, by construction,
indistinguishable from a fresh clone, so these tests skip instead of failing. That
ambiguity is irreducible here -- both states are "no stories anywhere" -- and it is
covered elsewhere rather than left open: `sync_sprint_status.py check` reports drift
the moment the two sides disagree, and git shows the deletion. What is NOT tolerated
is the asymmetric case, story files present beside an empty registry, which stays a
hard failure (`test_story_files_with_an_empty_registry_still_fail`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "utilities"))

import sync_sprint_status  # noqa: E402

#: Ids deliberately absent from the sequence, each with its REASON as the value --
#: never a bare list. An id belongs here only if it will NEVER exist (renumbering,
#: abandoned id); anything else is a missing row. Widening this dict to get green is
#: how the allow-list becomes the next defect, which is what the staleness test below
#: exists to stop.
_KNOWN_ID_GAPS: dict[str, str] = {}

# The capturing form of sync_sprint_status.STORY_KEY_RE, which is the key shape the
# generator writes.
#
# Start-anchored TWICE, deliberately: the `^` here and the `.match()` at the one call
# site below. Either alone is sufficient, so this is defence in depth, not redundancy
# to tidy away -- a scan that is anchored by NEITHER matches the date inside a key
# like `retro-2026-08-05-notes` and invents an epic 2026 with story 8. Measured: `^`
# + `.search()` is safe, and no-`^` + `.match()` is safe; only removing both breaks
# it. Any mutation testing this must therefore change BOTH to go red.
_STORY_ID_RE: re.Pattern[str] = re.compile(r"^(?P<epic>\d+)-(?P<story>\d+)-.+$")


def _registered_story_ids(development_status: dict[str, str]) -> dict[int, set[int]]:
    """Map epic number -> the story numbers registered under it.

    `epic-N` and `epic-N-retrospective` rows carry no story number and are skipped,
    as is any unrecognised entry sync_sprint_status preserved verbatim.
    """
    by_epic: dict[int, set[int]] = {}
    for key in development_status:
        match = _STORY_ID_RE.match(key)
        if match:
            by_epic.setdefault(int(match.group("epic")), set()).add(int(match.group("story")))
    return by_epic


def _unexplained_gaps(by_epic: dict[int, set[int]], known_gaps: dict[str, str]) -> list[str]:
    """Interior ids that are neither registered nor excused by *known_gaps*."""
    unexplained: list[str] = []
    for epic, numbers in sorted(by_epic.items()):
        for number in range(1, max(numbers) + 1):
            story_id = f"{epic}-{number}"
            if number not in numbers and story_id not in known_gaps:
                unexplained.append(story_id)
    return unexplained


def _stale_allowances(by_epic: dict[int, set[int]], known_gaps: dict[str, str]) -> list[str]:
    """Allow-list entries that ARE registered now, so the excuse has outlived itself."""
    registered = {f"{epic}-{n}" for epic, numbers in by_epic.items() for n in numbers}
    return sorted(story_id for story_id in known_gaps if story_id in registered)


def _registry_development_status() -> dict[str, str]:
    """This project's registry rows -- possibly none -- or a loud failure (AGENTS 5.5.1).

    An EMPTY mapping is returned, not rejected: a project with no stories yet is the
    state every clone starts in. What is still rejected is a registry that cannot be
    read at all, or one whose `development_status` key is absent entirely -- the
    generator writes that key unconditionally, so its absence means the file was
    hand-edited or truncated, which is a real defect rather than a young project.
    """
    path = sync_sprint_status.artifacts_dir(REPO) / "sprint-status.yaml"
    registry = sync_sprint_status.load_registry(path)
    assert registry is not None, f"registry missing or unparseable: {path}"
    assert "development_status" in registry, (
        f"development_status key is absent from {path} -- sync_sprint_status.py always "
        "writes it, so this registry was hand-edited or truncated"
    )
    development_status = registry["development_status"]
    # Two spellings of "empty" exist in the wild and both are legitimate: `{}` (what
    # bootstrap_project.ps1 writes, and what this module's generator now writes) and a
    # bare `development_status:` with no rows, which YAML parses to None (what the
    # generator emitted for a story-less project before 2026-08-16).
    if development_status is None:
        return {}
    assert isinstance(development_status, dict), (
        f"development_status is a {type(development_status).__name__}, not a mapping, "
        f"in {path}"
    )
    return {str(key): str(value) for key, value in development_status.items()}


def _story_files_on_disk() -> list[Path]:
    """The story files themselves -- ground truth, by raw glob.

    Deliberately pattern-free. Every other discovery in this file runs through a regex
    that could drift; asking the filesystem cannot. This is what lets the population
    self-check below distinguish "no stories exist" (a fresh clone, fine) from "stories
    exist but nothing parsed them" (the defect it is there to catch).
    """
    return sorted(sync_sprint_status.artifacts_dir(REPO).glob("*.story.md"))


def _registry_story_ids() -> dict[int, set[int]]:
    """Parse the registry, refusing to report success while looking at nothing.

    The generator's own `STORY_KEY_RE` and this file's `_STORY_ID_RE` must agree on
    which rows are stories. If one sees story rows and the other parses none, the
    discovery predicate has drifted and everything downstream of it goes vacuously
    green (AGENTS 4.1 axis 2) -- so that disagreement fails here, loudly, whether the
    registry is populated or not.
    """
    development_status = _registry_development_status()
    generator_rows = sorted(
        key for key in development_status if sync_sprint_status.STORY_KEY_RE.match(key)
    )
    by_epic = _registered_story_ids(development_status)
    assert bool(by_epic) == bool(generator_rows), (
        "the generator's story-key pattern and this file's disagree about the registry: "
        f"sync_sprint_status.STORY_KEY_RE matched {len(generator_rows)} row(s) "
        f"{generator_rows}, while {_STORY_ID_RE.pattern} parsed {len(by_epic)} epic(s). "
        "One of the two patterns has drifted"
    )
    return by_epic


def _populated_registry_story_ids() -> dict[int, set[int]]:
    """Story ids for this project, or SKIP when the project has none yet.

    The skip is the point: a freshly bootstrapped project legitimately has nothing to
    check, and reporting that as a pass would make the clone check meaningless for
    exactly the projects it runs in first.
    """
    by_epic = _registry_story_ids()
    if not by_epic:
        pytest.skip(
            "registry holds no story rows -- the correct state for a freshly "
            "bootstrapped project (bootstrap_project.ps1 deletes every *.story.md and "
            "writes `development_status: {}`). The synthetic-input tests below still "
            "prove the mechanism itself works"
        )
    return by_epic


# ---------------------------------------------------------------------------
# This project's registry
# ---------------------------------------------------------------------------

def test_the_checks_are_looking_at_a_populated_registry() -> None:
    """The population self-check, named so its failure is unmissable.

    A discovery predicate that matches nothing makes everything downstream of it
    vacuously green (AGENTS 4.1 axis 2). If sync_sprint_status.py ever changes the key
    shape it writes, this is what goes red -- instead of the suite going quietly, and
    wrongly, green.

    Populated-ness is judged against the STORY FILES, not against the registry, so
    that a fresh clone (no files, no rows) skips while a project whose registry has
    fallen behind its own story files still fails.
    """
    story_files = _story_files_on_disk()
    by_epic = _registry_story_ids()
    if not story_files and not by_epic:
        pytest.skip(
            "no story files on disk and no registry rows -- a freshly bootstrapped "
            "project, which is a valid state rather than a parsing failure"
        )
    assert by_epic, (
        f"{len(story_files)} story file(s) exist on disk but the registry parsed to zero "
        f"story ids -- the gap checks are inspecting nothing (expected key shape: "
        f"{_STORY_ID_RE.pattern}). Files: {[p.name for p in story_files]}"
    )


def test_the_story_id_pattern_still_agrees_with_the_generator() -> None:
    """One key shape, two owners: the generator writes them, this file reads them."""
    development_status = _registry_development_status()
    if not development_status:
        pytest.skip("registry has no rows to compare the two patterns against")
    for key in development_status:
        assert bool(sync_sprint_status.STORY_KEY_RE.match(key)) == bool(_STORY_ID_RE.match(key)), (
            f"{key!r} is a story key to one pattern and not to the other"
        )


def test_story_numbering_has_no_unexplained_gaps() -> None:
    unexplained = _unexplained_gaps(_populated_registry_story_ids(), _KNOWN_ID_GAPS)
    assert not unexplained, (
        "story ids missing from the sole numbering registry (AGENTS 6) -- a gap means "
        "either a story was completed without a registry row, or the id is unreserved "
        f"and a future story can silently re-use it: {unexplained}"
    )


def test_known_id_gaps_are_still_actually_gaps() -> None:
    """Without this, the allow-list becomes the next defect.

    An unreviewed exclusion silently absorbs whatever grows into it; one project
    watched an excused class grow 18 -> 24 behind exactly this kind of entry.
    """
    stale = _stale_allowances(_populated_registry_story_ids(), _KNOWN_ID_GAPS)
    assert not stale, (
        "these ids are in _KNOWN_ID_GAPS but ARE registered now -- remove the stale "
        f"entries so a future gap at the same id is not excused: {stale}"
    )


# ---------------------------------------------------------------------------
# The mechanism itself -- what every clone inherits (AGENTS 11)
# ---------------------------------------------------------------------------

def test_an_interior_hole_is_reported() -> None:
    assert _unexplained_gaps({6: {1, 2, 4, 5}}, {}) == ["6-3"]


def test_an_explained_hole_is_excused_by_its_reason() -> None:
    assert _unexplained_gaps({6: {1, 2, 4, 5}}, {"6-3": "260624 renumbering -> 7-1"}) == []


def test_gaps_are_reported_per_epic_not_across_them() -> None:
    """Epic 5 stopping at 3 says nothing about whether epic 6 starts at 1."""
    assert _unexplained_gaps({5: {1, 3}, 6: {2}}, {}) == ["5-2", "6-1"]


def test_the_highest_id_is_the_documented_blind_spot() -> None:
    """A missing TOP id stays invisible until one above it is registered.

    Pinned rather than hidden: if this ever starts failing, someone has widened the
    check into commit-scope territory and the module docstring needs to say so.
    """
    assert _unexplained_gaps({6: {1, 2, 3}}, {}) == []
    assert _unexplained_gaps({6: {1, 2, 3, 5}}, {}) == ["6-4"]


def test_a_gap_that_filled_itself_in_is_reported_as_stale() -> None:
    assert _stale_allowances({6: {1, 2, 3}}, {"6-2": "abandoned"}) == ["6-2"]


def test_an_allowance_for_an_id_that_is_still_absent_is_left_alone() -> None:
    assert _stale_allowances({6: {1, 2, 3}}, {"6-4": "abandoned"}) == []


# ---------------------------------------------------------------------------
# The fresh-clone state -- what bootstrap_project.ps1 actually produces (AGENTS 11)
# ---------------------------------------------------------------------------

#: The literal `development_status` line bootstrap_project.ps1 writes into a new
#: project's registry. Pinned as a constant so that if the bootstrapper ever changes
#: spelling, the divergence shows up here rather than as four failures in a clone.
_BOOTSTRAP_EMPTY_ROWS: str = "development_status: {}"


def _write_registry(directory: Path, rows_block: str) -> None:
    """Write a minimal but real sprint-status.yaml carrying *rows_block* verbatim."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "sprint-status.yaml").write_text(
        "generated: 2026-08-16T00:00:00Z\n"
        "last_updated: 2026-08-16T00:00:00Z\n"
        "project: Fresh Clone\n"
        "project_key: NOKEY\n"
        "tracking_system: file-system\n"
        "story_location: _bmad-output/implementation-artifacts\n"
        "\n"
        f"{rows_block}\n",
        encoding="utf-8",
        newline="\n",
    )


@pytest.fixture()
def registry_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every registry read in this module at a throwaway directory."""
    monkeypatch.setattr(sync_sprint_status, "artifacts_dir", lambda _root: tmp_path)
    return tmp_path


def test_a_freshly_bootstrapped_project_skips_rather_than_fails(registry_dir: Path) -> None:
    """The clone check must go green on a brand-new project.

    bootstrap_project.ps1 deletes every story file, writes an empty registry, and then
    runs `uv run pytest -q` as its verification. Four failures there tell the owner of
    a correct new project that the template is broken.
    """
    _write_registry(registry_dir, _BOOTSTRAP_EMPTY_ROWS)
    assert _registry_development_status() == {}
    assert _story_files_on_disk() == []
    assert _registry_story_ids() == {}

    for check in (
        test_the_checks_are_looking_at_a_populated_registry,
        test_the_story_id_pattern_still_agrees_with_the_generator,
        test_story_numbering_has_no_unexplained_gaps,
        test_known_id_gaps_are_still_actually_gaps,
    ):
        with pytest.raises(pytest.skip.Exception):
            check()


def test_the_generators_own_empty_output_parses_back_as_a_mapping() -> None:
    """The generator must not invent a second spelling of "empty".

    Rendering zero rows used to emit a bare `development_status:`, which YAML reads as
    None -- so `sync` run once in a new project turned bootstrap's valid `{}` into a
    value every reader had to special-case.
    """
    import yaml

    content = sync_sprint_status.render_sprint_status(
        project="Fresh Clone",
        project_key="NOKEY",
        tracking_system="file-system",
        story_location="_bmad-output/implementation-artifacts",
        generated="2026-08-16T00:00:00Z",
        last_updated="2026-08-16T00:00:00Z",
        development_status=[],
    )
    assert _BOOTSTRAP_EMPTY_ROWS in content, "the generator no longer agrees with bootstrap"
    parsed = yaml.safe_load(content)
    assert parsed["development_status"] == {}
    assert isinstance(parsed["development_status"], dict)


def test_the_legacy_null_spelling_of_empty_is_still_read_as_empty(registry_dir: Path) -> None:
    """Registries written by the OLD generator must not fail the clone they sit in."""
    _write_registry(registry_dir, "development_status:")
    assert _registry_development_status() == {}
    assert _registry_story_ids() == {}


def test_an_absent_development_status_key_is_still_a_hard_failure(registry_dir: Path) -> None:
    """Empty is valid; MISSING is a truncated file and must stay loud (AGENTS 5.5.1)."""
    _write_registry(registry_dir, "# no development_status key at all")
    with pytest.raises(AssertionError, match="development_status key is absent"):
        _registry_development_status()


def test_story_files_with_an_empty_registry_still_fail(registry_dir: Path) -> None:
    """The population self-check must keep biting where it always did.

    This is the case the fresh-clone fix must NOT swallow: files exist, so "no rows"
    means the registry fell behind, not that the project is new.
    """
    _write_registry(registry_dir, _BOOTSTRAP_EMPTY_ROWS)
    (registry_dir / "6-1-a-real-story.story.md").write_text("Status: done\n", encoding="utf-8")

    # Deliberately NOT `pytest.raises(AssertionError)`. If the check degrades into a
    # skip, that exception escapes the raises() block and THIS test reports as skipped
    # -- which reads like it never ran rather than like a failure. Both wrong outcomes
    # are caught by name so the verdict is always pass-or-fail, never absent.
    try:
        test_the_checks_are_looking_at_a_populated_registry()
    except pytest.skip.Exception as exc:  # noqa: PT012
        pytest.fail(
            "the population self-check SKIPPED while a real story file exists on disk -- "
            f"a stale registry would go unreported: {exc}"
        )
    except AssertionError as exc:
        assert "story file(s) exist on disk" in str(exc), f"failed for the wrong reason: {exc}"
    else:
        pytest.fail("the population self-check PASSED against an empty registry beside a story file")


def test_a_drifted_story_key_pattern_fails_even_with_rows_present(registry_dir: Path) -> None:
    """If the generator sees stories and this file parses none, that is the defect."""
    _write_registry(registry_dir, "development_status:\n  6-1-a-real-story: done")
    monkeyed = re.compile(r"^NEVER-MATCHES-(?P<epic>\d+)-(?P<story>\d+)-.+$")
    original = globals()["_STORY_ID_RE"]
    globals()["_STORY_ID_RE"] = monkeyed
    try:
        with pytest.raises(AssertionError, match="patterns has drifted"):
            _registry_story_ids()
    finally:
        globals()["_STORY_ID_RE"] = original


def test_non_story_rows_never_become_story_ids() -> None:
    """Epic and retrospective rows carry no story number, and a date-shaped key is the
    exact false positive that killed the `task.md`-scanning approach.
    """
    rows = {
        "epic-6": "in-progress",
        "6-1-first-slug": "done",
        "6-2-second-slug": "done",
        "epic-6-retrospective": "backlog",
        "retro-2026-08-05-notes": "done",
    }
    assert _registered_story_ids(rows) == {6: {1, 2}}
