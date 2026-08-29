r"""Memory & skills lint - the knowledge-base maintenance pass.

**Rot is prevented by structure, not detected by heuristics** (AGENTS 7).

The first version of this script tried to *detect* bad memory: shared-passage matching
against the constitution, a governance keyword list, byte budgets. It worked badly. The
real duplication in the wild was paraphrase, which shares no long passages; the keyword
heuristic then flagged five of six of our own pages, which is not discrimination, it is
noise; and every threshold in it was a number somebody made up. Worst of all it fired
*after* a session had already read and trusted the lie.

So the model changed. **Memory may only contain what cannot rot:**

* **pointers** - a broken one is objectively detectable
* **why / history** - it happened; it cannot go out of date
* **user preferences** - they rarely change, and only the user changes them

Anything that CAN go out of date (a rule, an invariant, a procedure, a decision) has an
owner elsewhere - AGENTS.md, the architecture map, a skill, an ADR - and memory points at
it. One home means one place to fix, so it cannot half-rot.

Every page is therefore three fields, under a hard cap::

    **Fact:** what the agent must know before it reads anything (1-2 sentences)
    **Why:** the incident or reasoning that exists nowhere else (immutable)
    **Authority:** AGENTS 9 | ADR-NNNN (this project's own) | ARCHITECTURE.md | skills/foo | none (domain gotcha)

Which makes every check a yes/no with nothing to tune: are the fields present, is it under
the cap, and **does the Authority resolve?** A governance essay is no longer something we
hunt for - it is something that will not fit.

Advisory by default (``--strict`` exits non-zero on warnings); schema breaches are errors.
Deliberately NOT in CI and deliberately not part of ``governance_lint.py``: what remains
after the objective checks is judgment, and that half belongs to the ``memory-lint`` skill.

Usage::

    python scripts/utilities/memory_lint.py [--memory-dir DIR] [--json] [--strict]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - pyyaml is a declared dependency
    yaml = None  # type: ignore[assignment]

SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"

ALLOWED_TYPES: frozenset[str] = frozenset({"user", "feedback", "project", "reference"})

# A cache entry is a pointer, not an essay. At this size a restated rule simply does not
# fit - which is the entire mechanism. (Worst page before this: 8,119 bytes.)
DEFAULT_MAX_PAGE_BYTES = 800

FACT_RE: re.Pattern[str] = re.compile(r"^\s*\*\*Fact:\*\*\s*(?P<value>.+)", re.MULTILINE)
WHY_RE: re.Pattern[str] = re.compile(r"^\s*\*\*Why:\*\*\s*(?P<value>.+)", re.MULTILINE)
AUTHORITY_RE: re.Pattern[str] = re.compile(r"^\s*\*\*Authority:\*\*\s*(?P<value>.+)", re.MULTILINE)

WIKILINK_RE: re.Pattern[str] = re.compile(r"\[\[([^\]]+)\]\]")
INDEX_ROW_RE: re.Pattern[str] = re.compile(r"^\s*-\s*\[[^\]]+\]\(([^)]+)\)")

# Authority forms we can resolve. Anything else is unresolvable by definition.
ADR_RE: re.Pattern[str] = re.compile(r"ADR[-\s]?(\d{3,4})", re.IGNORECASE)
AGENTS_RE: re.Pattern[str] = re.compile(r"AGENTS(?:\.md)?\s*(?:§|section\s*)?\s*(\d+(?:\.\d+)*)", re.IGNORECASE)
SKILL_RE: re.Pattern[str] = re.compile(r"skills?/([a-z0-9-]+)", re.IGNORECASE)
NONE_RE: re.Pattern[str] = re.compile(r"\bnone\b", re.IGNORECASE)
PATH_RE: re.Pattern[str] = re.compile(r"`?([\w./-]+\.(?:md|py|ps1|yaml|yml|toml|json))`?")

# A decision is never a "domain gotcha": it has an owner, and the owner is an ADR.
DECISION_RE: re.Pattern[str] = re.compile(
    r"\b(approved|decided|decision|agreed|rejected|we will|chose|ruling)\b", re.IGNORECASE
)

REPO_PREFIXES: tuple[str, ...] = (
    "scripts/", "docs/", "backend/", "frontend/", "tests/", "_bmad-output/", "_bmad/",
    ".agent/", ".github/",
)
BACKTICK_RE: re.Pattern[str] = re.compile(r"`([^`\n]+?)`")


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    message: str
    path: str


@dataclass
class CheckResult:
    name: str
    title: str
    findings: list[Finding] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    def add(self, severity: str, message: str, path: Path | str) -> None:
        self.findings.append(Finding(self.name, severity, message, str(path)))


@dataclass
class MemoryPage:
    path: Path
    frontmatter: dict
    body: str
    raw: str = ""

    @property
    def name(self) -> str:
        value = self.frontmatter.get("name")
        return str(value) if value else self.path.stem

    @property
    def reviewed(self) -> bool:
        """Human-curated: revise around it, never rewrite it wholesale."""
        return bool(self.frontmatter.get("reviewed"))

    @property
    def size(self) -> int:
        # The WHOLE file counts against the cap, frontmatter included: the cap is
        # a context-budget mechanism and the agent loads the whole file. Weighing
        # only the body let a page smuggle arbitrary bytes above the fold --
        # measured 4,264B files passing an 800B cap (reviewed_pages pack, ML-2).
        text = self.raw if self.raw else self.body
        return len(text.strip().encode("utf-8"))

    def field_value(self, pattern: re.Pattern[str]) -> str | None:
        match = pattern.search(self.body)
        return match.group("value").strip() if match else None


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def parse_page(path: Path) -> MemoryPage:
    text = read_text(path)
    frontmatter: dict = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]
            if yaml is not None:
                try:
                    loaded = yaml.safe_load(parts[1])
                    if isinstance(loaded, dict):
                        frontmatter = loaded
                except yaml.YAMLError:
                    frontmatter = {}
    return MemoryPage(path=path, frontmatter=frontmatter, body=body, raw=text)


def load_config(repo_root: Path) -> dict:
    config_path = repo_root / "config.yaml"
    if yaml is None or not config_path.is_file():
        return {}
    try:
        data = yaml.safe_load(read_text(config_path))
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    section = data.get("knowledge")
    return section if isinstance(section, dict) else {}


def resolve_configured_path(repo_root: Path, value: str) -> Path:
    """Relative config values are repo-relative, so no machine path leaks into governance."""
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (repo_root / candidate).resolve()


def discover_pages(memory_dir: Path) -> list[MemoryPage]:
    return [
        parse_page(p) for p in sorted(memory_dir.glob("*.md")) if p.name.upper() != "MEMORY.MD"
    ]


# ---------------------------------------------------------------------------
# Schema: the prevention layer
# ---------------------------------------------------------------------------

def check_schema(pages: list[MemoryPage], max_page_bytes: int) -> CheckResult:
    """Every page is Fact + Why + Authority, under the cap. No thresholds, no guessing.

    The cap is the mechanism, not a style preference: a restated rule does not fit in it.
    That is why this replaced the heuristics rather than joining them.
    """
    result = CheckResult("schema", "Pages are Fact + Why + Authority, under the cap")
    for page in pages:
        for label, pattern in (("Fact", FACT_RE), ("Why", WHY_RE), ("Authority", AUTHORITY_RE)):
            if not page.field_value(pattern):
                result.add(
                    SEVERITY_ERROR,
                    f"no **{label}:** field - a cache entry states the fact, the why nothing "
                    "else records, and the authority that owns the rule",
                    page.path,
                )
        if page.size > max_page_bytes and page.reviewed:
            # One frontmatter line used to switch the cap off entirely (ML-1). A
            # curated page may legitimately run long, but silence is how 4KB essays
            # accumulate in an 800B cache -- so it WARNS, permanently, and the
            # warning is the prompt to split the page (owner decision D8).
            result.add(
                SEVERITY_WARNING,
                f"{page.size}B over the {max_page_bytes}B cap (reviewed page - warning, "
                "never silence: split it, or shrink it around the human-edited parts)",
                page.path,
            )
        elif page.size > max_page_bytes:
            result.add(
                SEVERITY_ERROR,
                f"{page.size}B over the {max_page_bytes}B cap - this is an essay, not a "
                "pointer. Move the rule to AGENTS, the invariant to the architecture map, "
                "the procedure to a skill, the decision to an ADR; keep the pointer + why",
                page.path,
            )
    return result


def check_authority(
    pages: list[MemoryPage], repo_root: Path, registry: Path, config: dict
) -> CheckResult:
    """**The check that makes this work.** Does the cited authority actually exist?

    A pointer either resolves or it does not - there is nothing to tune and nothing to
    guess. This is what replaces the paraphrase-hunting: we no longer ask "is this page
    secretly restating a rule?", we require it to *name the owner of the rule* and then
    verify the owner is real.

    `none (domain gotcha)` is legitimate - some knowledge genuinely has no other home -
    but a *decision* is never a gotcha, so that combination is flagged.
    """
    result = CheckResult("authority", "Cited authorities resolve")
    agents = read_text(repo_root / "AGENTS.md")
    register = read_text(repo_root / "docs" / "ADR" / "ADR_decision_register.md")
    arch = config.get("architecture_map")

    for page in pages:
        raw = page.field_value(AUTHORITY_RE)
        if not raw:
            continue  # already an error in check_schema

        if NONE_RE.search(raw) and not ADR_RE.search(raw):
            if DECISION_RE.search(page.body):
                result.add(
                    SEVERITY_WARNING,
                    "claims no authority but records a decision - a decision is not a domain "
                    "gotcha. Write the ADR, then point at it",
                    page.path,
                )
            continue

        resolved = False

        for section in AGENTS_RE.findall(raw):
            resolved = True
            top = section.split(".")[0]
            if not re.search(rf"^#+\s*{re.escape(top)}\.", agents, re.MULTILINE):
                result.add(
                    SEVERITY_ERROR,
                    f"cites AGENTS section {section}, which does not exist", page.path
                )

        for number in ADR_RE.findall(raw):
            resolved = True
            padded = number.zfill(4)
            if not list((repo_root / "docs" / "ADR").glob(f"{padded}-*.md")):
                result.add(SEVERITY_ERROR, f"cites ADR-{padded}, which does not exist", page.path)
            elif f"[{padded}]" not in register:
                result.add(
                    SEVERITY_WARNING,
                    f"cites ADR-{padded}, which has no row in the ADR register", page.path
                )

        for skill in SKILL_RE.findall(raw):
            resolved = True
            if registry.is_dir() and not (registry / skill).is_dir():
                result.add(
                    SEVERITY_ERROR, f"cites skill `{skill}`, which is not in the registry", page.path
                )

        for candidate in PATH_RE.findall(raw):
            if ADR_RE.search(candidate) or candidate.lower().startswith("agents"):
                continue
            target = repo_root / candidate
            if arch and Path(candidate).name == Path(str(arch)).name:
                target = repo_root / str(arch)
            resolved = True
            if not target.exists():
                result.add(
                    SEVERITY_ERROR, f"cites `{candidate}`, which does not exist", page.path
                )

        if not resolved:
            result.add(
                SEVERITY_WARNING,
                f"authority '{raw[:60]}' is not a resolvable reference - name an AGENTS "
                "section, an ADR, a file, a skill, or 'none (domain gotcha)'",
                page.path,
            )
    return result


# ---------------------------------------------------------------------------
# Integrity: unchanged, and objective
# ---------------------------------------------------------------------------

def check_index(memory_dir: Path, pages: list[MemoryPage]) -> CheckResult:
    """A page missing from the index is never loaded; a row for a deleted page is a lie."""
    result = CheckResult("index-drift", "MEMORY.md index matches the store")
    index_path = memory_dir / "MEMORY.md"
    if not index_path.is_file():
        result.add(SEVERITY_ERROR, "MEMORY.md index is missing", index_path)
        return result

    listed = {
        match.group(1).strip()
        for line in read_text(index_path).splitlines()
        if (match := INDEX_ROW_RE.match(line))
    }
    on_disk = {p.path.name for p in pages}

    for target in sorted(listed - on_disk):
        result.add(SEVERITY_ERROR, f"index lists '{target}', which does not exist", index_path)
    for orphan in sorted(on_disk - listed):
        result.add(
            SEVERITY_ERROR,
            f"'{orphan}' is not in the index - the agent will never load it",
            memory_dir / orphan,
        )
    return result


def check_frontmatter(pages: list[MemoryPage]) -> CheckResult:
    result = CheckResult("frontmatter", "Pages carry valid frontmatter")
    for page in pages:
        fm = page.frontmatter
        if not fm:
            result.add(SEVERITY_ERROR, "no parseable frontmatter", page.path)
            continue
        for key in ("name", "description"):
            if not fm.get(key):
                result.add(SEVERITY_ERROR, f"frontmatter is missing '{key}'", page.path)
        metadata = fm.get("metadata")
        mem_type = metadata.get("type") if isinstance(metadata, dict) else None
        if not mem_type:
            result.add(SEVERITY_WARNING, "frontmatter is missing metadata.type", page.path)
        elif str(mem_type) not in ALLOWED_TYPES:
            allowed = "|".join(sorted(ALLOWED_TYPES))
            result.add(
                SEVERITY_WARNING,
                f"metadata.type '{mem_type}' is not one of: {allowed} "
                "(there is deliberately no 'governance' type - governance lives in AGENTS.md)",
                page.path,
            )
    return result


def check_dead_wikilinks(pages: list[MemoryPage]) -> CheckResult:
    result = CheckResult("dead-links", "Wikilinks resolve to real pages")
    known = {p.name for p in pages} | {p.path.stem for p in pages}
    for page in pages:
        for target in sorted(set(WIKILINK_RE.findall(page.body))):
            if target.strip() not in known:
                result.add(SEVERITY_WARNING, f"[[{target}]] has no matching memory page", page.path)
    return result


def check_stale_refs(pages: list[MemoryPage], repo_root: Path) -> CheckResult:
    """A memory citing a deleted file actively misleads the next session."""
    result = CheckResult("stale-refs", "Cited repo paths still exist")
    for page in pages:
        for token in sorted(set(BACKTICK_RE.findall(page.body))):
            candidate = token.strip().replace("\\", "/").lstrip("./")
            if not candidate.startswith(REPO_PREFIXES):
                continue
            if any(ch in candidate for ch in " *?<>|"):
                continue
            if not (repo_root / candidate).exists():
                result.add(SEVERITY_WARNING, f"cites `{token}`, which no longer exists", page.path)
    return result


def check_decommissioned_concepts(pages: list[MemoryPage]) -> CheckResult:
    """Memory pages must not contain active references to decommissioned concepts (AGENTS 7)."""
    result = CheckResult("decommissioned-concepts", "No active references to decommissioned concepts")
    decommissioned_terms = {"wsl", "hermes"}
    for page in pages:
        body_lower = page.body.lower()
        for term in decommissioned_terms:
            if re.search(rf"\b{re.escape(term)}\b", body_lower):
                if not any(word in body_lower for word in ("decommission", "retired", "legacy", "done", "completed")):
                    result.add(
                        SEVERITY_WARNING,
                        f"mentions decommissioned concept '{term}' without explicitly marking it "
                        "as decommissioned/retired/legacy. Verify this page is not stale",
                        page.path
                    )
    return result


def check_skills(registry: Path) -> CheckResult:
    """A skill directory with no SKILL.md is inert dead weight - nothing can load it."""
    result = CheckResult("skills", "Skills registry is coherent")
    if not registry.is_dir():
        result.skipped = True
        result.skip_reason = f"skills registry not found at {registry}"
        return result

    for skill_dir in sorted(p for p in registry.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            result.add(SEVERITY_ERROR, "skill directory has no SKILL.md", skill_md)
            continue
        page = parse_page(skill_md)
        if not page.frontmatter.get("name"):
            result.add(SEVERITY_WARNING, "SKILL.md frontmatter is missing 'name'", skill_md)
        if not page.frontmatter.get("description"):
            result.add(
                SEVERITY_WARNING,
                "SKILL.md frontmatter is missing 'description' - it is what the agent "
                "matches on, so the skill is effectively undiscoverable",
                skill_md,
            )
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_checks(
    repo_root: Path, memory_dir: Path, registry: Path, max_page_bytes: int, config: dict | None = None
) -> list[CheckResult]:
    pages = discover_pages(memory_dir)
    cfg = config or {}
    return [
        check_index(memory_dir, pages),
        check_frontmatter(pages),
        check_schema(pages, max_page_bytes),
        check_authority(pages, repo_root, registry, cfg),
        check_dead_wikilinks(pages),
        check_stale_refs(pages, repo_root),
        check_decommissioned_concepts(pages),
        check_skills(registry),
    ]


def _print_header(memory_dir, registry, max_page_bytes) -> None:
    print(f"Memory store:    {memory_dir}")
    print(f"Skills registry: {registry}")
    print(f"Page cap:        {max_page_bytes}B")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Memory & skills lint (the third verb).")
    parser.add_argument("--memory-dir", type=str, help="Override the configured memory store")
    parser.add_argument("--skills-registry", type=str, help="Override the configured registry")
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings too")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    config = load_config(repo_root)

    memory_dir = resolve_configured_path(repo_root, args.memory_dir or config.get("memory_store", ""))
    registry = resolve_configured_path(
        repo_root, args.skills_registry or config.get("skills_registry", "")
    )
    max_page_bytes = int(config.get("memory_max_page_bytes", DEFAULT_MAX_PAGE_BYTES))

    if not memory_dir or not memory_dir.is_dir():
        print(f"[SKIP] Memory store not found: {memory_dir or '<unconfigured>'}")
        print("       Set knowledge.memory_store in config.yaml, or pass --memory-dir.")
        sys.exit(0)

    page_count = len([q for q in memory_dir.glob("*.md") if q.name != "MEMORY.md"])
    if page_count == 0:
        # An empty store passing every check is a PASS caused by the defect
        # (AGENTS 4.1 axis 7): with zero subjects, nothing was verified. Say
        # UNKNOWN and the subject-set size; never print the clean bill. Under
        # --json this branch too must emit pure JSON -- the skeptic pass caught
        # it emitting prose here while the comment below promised structure.
        if args.json:
            print(json.dumps({
                "pages_examined": 0,
                "findings": [],
                "skipped": [{"name": "all", "reason": "0 memory pages - health UNVERIFIED"}],
            }, indent=2))
        else:
            print("[SKIP] 0 memory pages found - health UNVERIFIED, not perfect.")
            print("       An empty cache in a governed project usually means the junction")
            print("       or the store path is wrong; check knowledge.memory_store.")
        sys.exit(0)

    if not args.json:
        _print_header(memory_dir, registry, max_page_bytes)

    results = run_checks(repo_root, memory_dir, registry, max_page_bytes, config)

    if args.json:
        # PURE JSON on stdout -- the prose header used to precede it, so every
        # consumer's json.loads failed on line one (ML-3). Structured, so an empty
        # store is distinguishable from a clean one (AGENTS 4.1 axis 7).
        print(json.dumps({
            "pages_examined": len([q for q in memory_dir.glob("*.md") if q.name != "MEMORY.md"]),
            "findings": [asdict(f) for r in results for f in r.findings],
            "skipped": [{"name": r.name, "reason": r.skip_reason} for r in results if r.skipped],
        }, indent=2))
    else:
        for result in results:
            if result.skipped:
                print(f"[SKIP] {result.title} ({result.name})\n       {result.skip_reason}")
                continue
            if not result.findings:
                print(f"[PASS] {result.title} ({result.name})")
                continue
            print(f"[FAIL] {result.title} ({result.name})")
            for finding in result.findings:
                print(f"       {finding.severity}: {finding.message} [{finding.path}]")

    errors = sum(1 for r in results for f in r.findings if f.severity == SEVERITY_ERROR)
    warnings = sum(1 for r in results for f in r.findings if f.severity == SEVERITY_WARNING)
    if not args.json:
        # Under --json stdout is PURE JSON; the exit code carries the verdict.
        print(f"\nSummary: {errors} error(s), {warnings} warning(s)")

    if errors or (args.strict and warnings):
        if not args.json:
            print("Result: FAIL")
        sys.exit(1)
    if not args.json:
        print("Result: PASS (the judgment half is the `memory-lint` skill)")
    sys.exit(0)


if __name__ == "__main__":
    main()
