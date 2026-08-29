"""Unit tests for scripts/utilities/memory_lint.py (AGENTS 7).

The design under test is *prevention*, not detection. An earlier version tried to spot bad
memory with heuristics -- shared-passage matching, a governance keyword list, invented byte
thresholds -- and it failed: the real duplication was paraphrase (no shared passages), the
keyword fallback flagged 5 of 6 of our own pages, and it only ever fired after a session had
already believed the lie.

So the checks here are all yes/no. The two that carry the weight:

* `schema`    -- Fact + Why + Authority, under a hard cap. A restated rule does not FIT.
* `authority` -- the cited owner must actually exist. This is what replaced paraphrase-hunting:
                 we no longer guess whether a page is secretly restating a rule, we require it
                 to name the rule's owner and then verify the owner is real.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "utilities"))

import memory_lint  # noqa: E402

CAP = 800

CONSTITUTION = """# Project Constitution

## 7. Skills & Memory
## 9. Access Boundaries
"""

REGISTER = """# ADR Index

| [0008](0008-memory.md) | Memory is a Cache | 2026-07-13 | Accepted | ... |
"""


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A repo with a constitution, one real ADR, and one real skill."""
    (tmp_path / "AGENTS.md").write_text(CONSTITUTION, encoding="utf-8")
    adr = tmp_path / "docs" / "ADR"
    adr.mkdir(parents=True)
    (adr / "0008-memory.md").write_text("# ADR-0008\n", encoding="utf-8")
    (adr / "ADR_decision_register.md").write_text(REGISTER, encoding="utf-8")
    (tmp_path / "skills" / "crystallize").mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def store(repo: Path) -> Path:
    memory = repo / "docs" / "memory"
    memory.mkdir(parents=True)
    return memory


def _page(store: Path, name: str, body: str, *, reviewed: bool = False, mtype: str = "project") -> Path:
    reviewed_line = "\nreviewed: true" if reviewed else ""
    path = store / f"{name}.md"
    path.write_text(
        f"---\nname: {name}\ndescription: d{reviewed_line}\nmetadata:\n  type: {mtype}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def _good_body(authority: str = "AGENTS 9") -> str:
    return f"**Fact:** The thing is true.\n\n**Why:** It broke once.\n\n**Authority:** {authority}"


# ---------------------------------------------------------------------------
# schema - the prevention layer
# ---------------------------------------------------------------------------

def test_a_well_formed_page_passes(store: Path) -> None:
    _page(store, "good", _good_body())

    assert not memory_lint.check_schema(memory_lint.discover_pages(store), CAP).findings


@pytest.mark.parametrize("missing", ["Fact", "Why", "Authority"])
def test_every_field_is_required(store: Path, missing: str) -> None:
    body = "\n\n".join(
        f"**{f}:** value" for f in ("Fact", "Why", "Authority") if f != missing
    )
    _page(store, "partial", body)

    findings = memory_lint.check_schema(memory_lint.discover_pages(store), CAP).findings

    assert any(missing in f.message for f in findings)
    assert all(f.severity == memory_lint.SEVERITY_ERROR for f in findings)


def test_an_essay_cannot_fit_under_the_cap(store: Path) -> None:
    """THE mechanism. A restated rule is not detected -- it does not fit.

    The page this models was 1,646B of paraphrased constitution carrying a claim that had
    been false for a day. Under the cap it is simply unwriteable.
    """
    _page(store, "essay", _good_body() + "\n\n" + ("Restating the constitution at length. " * 40))

    findings = memory_lint.check_schema(memory_lint.discover_pages(store), CAP).findings

    assert len(findings) == 1
    assert "over the" in findings[0].message
    assert findings[0].severity == memory_lint.SEVERITY_ERROR


def test_reviewed_pages_are_not_exempt_from_the_cap(store: Path) -> None:
    """REVERSED 2026-08-29 (owner decision D8, reviewed_pages pack ML-1).

    This test used to pin the opposite: `reviewed: true` switched the cap off
    entirely, so one frontmatter line exempted a page from memory_lint's only
    size enforcement, and 4KB essays accumulated in an 800B cache with a clean
    bill of health. A curated page still deserves gentler treatment than an
    unreviewed one -- WARNING, not ERROR -- but never silence: the warning is
    the standing prompt to split the page.
    """
    _page(store, "curated", _good_body() + "\n\n" + ("Long human prose. " * 60), reviewed=True)

    findings = memory_lint.check_schema(memory_lint.discover_pages(store), CAP).findings

    over = [f for f in findings if "over the" in f.message]
    assert len(over) == 1, "a reviewed page over the cap must be REPORTED"
    assert over[0].severity == memory_lint.SEVERITY_WARNING, (
        "reviewed = WARNING (revise around the human's edits), never ERROR, never silence"
    )


# ---------------------------------------------------------------------------
# authority - the check that replaced the heuristics
# ---------------------------------------------------------------------------

def test_real_authorities_resolve(store: Path, repo: Path) -> None:
    _page(store, "ok", _good_body("AGENTS 7, ADR-0008, skills/crystallize"))

    result = memory_lint.check_authority(
        memory_lint.discover_pages(store), repo, repo / "skills", {}
    )

    assert not result.findings


def test_a_nonexistent_adr_is_an_error(store: Path, repo: Path) -> None:
    _page(store, "bad", _good_body("ADR-0099"))

    findings = memory_lint.check_authority(
        memory_lint.discover_pages(store), repo, repo / "skills", {}
    ).findings

    assert any("ADR-0099, which does not exist" in f.message for f in findings)


def test_a_nonexistent_agents_section_is_an_error(store: Path, repo: Path) -> None:
    """The WSL failure in one line: memory cited a rule; nobody checked the rule was there."""
    _page(store, "bad", _good_body("AGENTS 47"))

    findings = memory_lint.check_authority(
        memory_lint.discover_pages(store), repo, repo / "skills", {}
    ).findings

    assert any("section 47, which does not exist" in f.message for f in findings)


def test_a_nonexistent_skill_is_an_error(store: Path, repo: Path) -> None:
    _page(store, "bad", _good_body("skills/ghost"))

    findings = memory_lint.check_authority(
        memory_lint.discover_pages(store), repo, repo / "skills", {}
    ).findings

    assert any("`ghost`, which is not in the registry" in f.message for f in findings)


def test_domain_gotchas_may_declare_no_authority(store: Path, repo: Path) -> None:
    """Some knowledge genuinely has no other home. That is what memory is FOR."""
    _page(
        store,
        "gotcha",
        "**Fact:** The engine ignores spec.scenes.\n\n**Why:** Found the hard way.\n\n"
        "**Authority:** none (domain gotcha)",
    )

    assert not memory_lint.check_authority(
        memory_lint.discover_pages(store), repo, repo / "skills", {}
    ).findings


def test_a_decision_may_not_claim_to_be_a_gotcha(store: Path, repo: Path) -> None:
    """A decision has an owner, and the owner is an ADR."""
    _page(
        store,
        "sneaky",
        "**Fact:** We approved the new layout.\n\n**Why:** Phil decided.\n\n"
        "**Authority:** none (domain gotcha)",
    )

    findings = memory_lint.check_authority(
        memory_lint.discover_pages(store), repo, repo / "skills", {}
    ).findings

    assert any("a decision is not a domain gotcha" in f.message for f in findings)


def test_an_unresolvable_authority_is_flagged(store: Path, repo: Path) -> None:
    _page(store, "vague", _good_body("because I said so"))

    findings = memory_lint.check_authority(
        memory_lint.discover_pages(store), repo, repo / "skills", {}
    ).findings

    assert any("not a resolvable reference" in f.message for f in findings)


# ---------------------------------------------------------------------------
# integrity
# ---------------------------------------------------------------------------

def test_orphan_page_is_an_error(store: Path) -> None:
    _page(store, "alpha", _good_body())
    (store / "MEMORY.md").write_text("# Memory Index\n", encoding="utf-8")

    findings = memory_lint.check_index(store, memory_lint.discover_pages(store)).findings

    assert any("not in the index" in f.message for f in findings)


def test_index_row_for_deleted_page_is_an_error(store: Path) -> None:
    (store / "MEMORY.md").write_text("# Index\n\n- [Ghost](ghost.md) - x\n", encoding="utf-8")

    findings = memory_lint.check_index(store, memory_lint.discover_pages(store)).findings

    assert any("does not exist" in f.message for f in findings)


def test_dead_wikilink_is_flagged(store: Path) -> None:
    _page(store, "alpha", _good_body() + "\n\nSee [[nonexistent]].")

    findings = memory_lint.check_dead_wikilinks(memory_lint.discover_pages(store)).findings

    assert any("nonexistent" in f.message for f in findings)


def test_stale_repo_path_is_flagged(store: Path, repo: Path) -> None:
    _page(store, "alpha", _good_body() + "\n\nSee `scripts/utilities/gone.py`.")

    findings = memory_lint.check_stale_refs(memory_lint.discover_pages(store), repo).findings

    assert any("no longer exists" in f.message for f in findings)


def test_sibling_paths_are_not_guessed_at(store: Path, repo: Path) -> None:
    _page(store, "alpha", _good_body() + "\n\nSee `Horse racing tips/run.py`.")

    assert not memory_lint.check_stale_refs(memory_lint.discover_pages(store), repo).findings


def test_bad_metadata_type_is_flagged(store: Path) -> None:
    """There is deliberately no 'governance' type: governance lives in AGENTS.md."""
    _page(store, "alpha", _good_body(), mtype="governance")

    findings = memory_lint.check_frontmatter(memory_lint.discover_pages(store)).findings

    assert any("is not one of" in f.message for f in findings)


# ---------------------------------------------------------------------------
# skills registry
# ---------------------------------------------------------------------------

def test_skill_dir_without_skill_md_is_an_error(tmp_path: Path) -> None:
    """The live registry had exactly this: BMAD replaced two skills and orphaned their subdirs."""
    registry = tmp_path / "skills"
    (registry / "orphan" / "steps").mkdir(parents=True)

    findings = memory_lint.check_skills(registry).findings

    assert any("no SKILL.md" in f.message for f in findings)


def test_missing_registry_is_skipped_not_failed(tmp_path: Path) -> None:
    result = memory_lint.check_skills(tmp_path / "nope")

    assert result.skipped
    assert not result.findings
