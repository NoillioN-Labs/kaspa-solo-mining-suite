#!/usr/bin/env python3
"""Deterministic governance rule checker for this project template.

Usage:
    python scripts/utilities/governance_lint.py [--json] [--strict]

Exit codes:
    0 -- no ERROR findings (WARNINGs are allowed unless --strict is set)
    1 -- at least one ERROR finding (or any WARNING when --strict is set)

All checks are pure functions over the repository tree; no network access,
no external tools. Output is ASCII-only so it survives Windows cp1252 pipes.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shlex
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

try:
    import yaml
except ImportError:  # pragma: no cover - degraded mode when pyyaml missing
    yaml = None  # type: ignore[assignment]

# Repo root = two levels up from scripts/utilities/.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

TEMPLATE_PROJECT_NAME: str = "_NEON dev stack"
TEMPLATE_NAME_URLENCODED: str = "_NEON%20dev%20stack"

SEVERITY_ERROR: str = "ERROR"
SEVERITY_WARNING: str = "WARNING"

UPGRADE_PACK_MAX_AGE_DAYS: int = 14
SPRINT_STATUS_MAX_LAG_DAYS: int = 3
LOOSE_FILE_MAX_AGE_DAYS: int = 7

UPGRADE_INCLUDE_GLOBS: tuple[str, ...] = (
    "upgrade_instructions_*.md",
    "*_guide_*.md",
)
UPGRADE_EXCLUDE_GLOBS: tuple[str, ...] = (
    "upgrades_ledger.md",
    "Global_Hermes_Skill_Candidates.md",
    "project_upgrade_assessment_questions_*.md",
    "archiving_instructions.md",
    "cross_project_optimization_guide.md",
)

LINK_CHECK_FILES: tuple[str, ...] = ("AGENTS.md", "README.md")
SKIPPED_LINK_PREFIXES: tuple[str, ...] = ("http://", "https://", "file://", "mailto:", "#")

LEAKAGE_CHECK_FILES: tuple[str, ...] = (
    "AGENTS.md",
    "README.md",
    "_bmad-output/project-context.md",
    "_bmad-output/implementation-artifacts/sprint-status.yaml",
)

LOOSE_FILE_DIRS: tuple[str, ...] = (
    "docs/chat_logs",
    "docs/sessions",
    "docs/retrospectives",
    "docs/code review",
    "logs",
)

MARKDOWN_LINK_PATTERN: re.Pattern[str] = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
ADR_FILE_PATTERN: re.Pattern[str] = re.compile(r"^(\d{4})-.+\.md$")

# Native-Windows execution traps (AGENTS 5.5.1 / native_windows_traps pack).
SHELL_SCRIPT_SUFFIXES: tuple[str, ...] = (".ps1", ".bat", ".cmd")
WALK_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        ".venv-linux",
        "venv",
        "node_modules",
        "__pycache__",
        "archive",
        ".data",
        "client_files",
    }
)
# -ArgumentList values that interpolate a variable without wrapping it in quotes.
UNQUOTED_ARGLIST_PATTERN: re.Pattern[str] = re.compile(
    r"-ArgumentList\s+(?P<args>[^\r\n#]+)", re.IGNORECASE
)
QUOTED_VAR_PATTERN: re.Pattern[str] = re.compile(r"""(['"]).*?\$.*?\1|-f\s*\$""")
BARE_VAR_PATTERN: re.Pattern[str] = re.compile(r"\$[A-Za-z_][\w.:\[\]]*")
WMIC_PATTERN: re.Pattern[str] = re.compile(r"\bwmic\b", re.IGNORECASE)
# Generated files landing on C: by default is a recurring incident (AGENTS 5.5.1): a project's data
# lives wherever -DestinationPath put it, but a hardcoded C:\ literal or an unscoped tempfile
# call ignores that and fills the boot drive instead.
HARDCODED_C_DRIVE_PATTERN: re.Pattern[str] = re.compile(r"""(['"])[Cc]:[\\/]""")
TEMPFILE_OS_DEFAULT_PATTERN: re.Pattern[str] = re.compile(r"\btempfile\.gettempdir\s*\(")
TEMPFILE_NO_DIR_PATTERN: re.Pattern[str] = re.compile(
    r"\btempfile\.(mkstemp|mkdtemp|NamedTemporaryFile|TemporaryDirectory|TemporaryFile)\s*\("
)
# `-LiteralPath` exists precisely SO THAT wildcards are not expanded. Pairing it with a `*`
# matches a file literally named `*`, finds nothing, and copies nothing -- without throwing,
# even under $ErrorActionPreference='Stop'. Near-miss (NEON PowerPoint creator, 2026-07-13):
# a migration snippet did `Copy-Item -LiteralPath "$vendor\*.md"` and then renamed the source
# away, i.e. copy nothing -> destroy the original -> point at the void, all reporting success.
# Only the IMMEDIATE argument is inspected: `-LiteralPath $dir -Filter '*.md'` is correct.
LITERALPATH_ARG_PATTERN: re.Pattern[str] = re.compile(
    r"-LiteralPath\s+(?P<arg>\"[^\"]*\"|'[^']*'|\S+)", re.IGNORECASE
)
NPM_SHIM_PATTERN: re.Pattern[str] = re.compile(r"(?<!\w)(npx\s|\bvite\.cmd|\btsc\.cmd|\bvitest\.cmd)")
REGISTER_ROW_PATTERN: re.Pattern[str] = re.compile(r"\[(\d{4})\]\(([^)]+)\)")
FILENAME_STAMP_PATTERN: re.Pattern[str] = re.compile(r"_(\d{6})_(\d{4})")


@dataclass(frozen=True)
class Finding:
    """A single lint finding."""

    check: str
    severity: str
    message: str
    path: str


@dataclass
class CheckResult:
    """Outcome of one governance check."""

    name: str
    title: str
    findings: list[Finding] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    def add(self, severity: str, message: str, path: Path | str) -> None:
        path_text = rel_path(path) if isinstance(path, Path) else path
        self.findings.append(Finding(self.name, severity, message, path_text))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def rel_path(path: Path) -> str:
    """Render a path relative to the repo root, posix-style, for reporting."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_knowledge_config(root: Path) -> dict:
    """Read the `knowledge:` section of config.yaml (empty dict on any failure).

    Paths and thresholds live in config, never in the script (AGENTS 5.1), so this
    check stays portable across the fleet and vendor-neutral (the Adapter Rule).
    """
    config_path = root / "config.yaml"
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


def parse_filename_stamp(name: str) -> datetime | None:
    """Parse the last _YYMMDD_HHMM stamp in a filename as an aware datetime.

    Stamps are written in local time; returns None if absent or invalid.
    """
    matches = FILENAME_STAMP_PATTERN.findall(name)
    if not matches:
        return None
    date_part, time_part = matches[-1]
    try:
        naive = datetime(
            2000 + int(date_part[0:2]),
            int(date_part[2:4]),
            int(date_part[4:6]),
            int(time_part[0:2]),
            int(time_part[2:4]),
        )
    except ValueError:
        return None
    return naive.astimezone()


def mtime_utc(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


def to_utc_datetime(value: object) -> datetime | None:
    """Coerce a YAML scalar (datetime or ISO string) to an aware datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def is_master_template(root: Path) -> bool:
    """True when this repo is the canonical master template itself."""
    config_path = root / "_bmad" / "config.toml"
    if not config_path.is_file():
        return False
    match = re.search(
        r'^\s*project_name\s*=\s*"([^"]*)"',
        read_text(config_path),
        re.MULTILINE,
    )
    return match is not None and match.group(1) == TEMPLATE_PROJECT_NAME


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_adr_register(root: Path) -> CheckResult:
    """ADR files and the decision register must agree, IDs sequential from 0001."""
    result = CheckResult("adr-register", "ADR register consistency")
    adr_dir = root / "docs" / "ADR"
    if not adr_dir.is_dir():
        result.add(SEVERITY_ERROR, "docs/ADR directory not found", adr_dir)
        return result

    adr_names: list[str] = sorted(p.name for p in adr_dir.glob("*.md") if ADR_FILE_PATTERN.match(p.name))

    register_path = adr_dir / "ADR_decision_register.md"
    if not register_path.is_file():
        result.add(SEVERITY_ERROR, "ADR_decision_register.md not found", register_path)
        return result

    rows = REGISTER_ROW_PATTERN.findall(read_text(register_path))
    target_counts: dict[str, int] = {}
    for _label, raw_target in rows:
        target_name = Path(unquote(raw_target.split("#", 1)[0].strip())).name
        target_counts[target_name] = target_counts.get(target_name, 0) + 1

    for name in adr_names:
        count = target_counts.get(name, 0)
        if count == 0:
            result.add(
                SEVERITY_ERROR,
                f"ADR file has no row in the decision register: {name}",
                register_path,
            )
        elif count > 1:
            result.add(
                SEVERITY_ERROR,
                f"ADR file has {count} register rows (expected exactly one): {name}",
                register_path,
            )

    known_names = set(adr_names)
    for target_name in sorted(target_counts):
        if target_name not in known_names:
            result.add(
                SEVERITY_ERROR,
                f"register row links to a missing ADR file: {target_name}",
                register_path,
            )

    ids: list[int] = [int(name[:4]) for name in adr_names]
    duplicates = sorted({adr_id for adr_id in ids if ids.count(adr_id) > 1})
    for adr_id in duplicates:
        result.add(
            SEVERITY_ERROR,
            f"duplicate ADR id {adr_id:04d} across multiple files",
            adr_dir,
        )
    if ids:
        expected = set(range(1, max(ids) + 1))
        gaps = sorted(expected - set(ids))
        for adr_id in gaps:
            result.add(
                SEVERITY_ERROR,
                f"gap in ADR id sequence: {adr_id:04d} is missing",
                adr_dir,
            )
    return result


def check_upgrade_packs(root: Path) -> CheckResult:
    """Unapplied upgrade packs in docs/upgrades (skipped on the master template)."""
    result = CheckResult("upgrade-packs", "Pending upgrade packs")
    if is_master_template(root):
        result.skipped = True
        result.skip_reason = "repo is the master template (canonical upgrade pack library)"
        return result

    upgrades_dir = root / "docs" / "upgrades"
    if not upgrades_dir.is_dir():
        return result

    now = datetime.now(UTC)
    for path in sorted(upgrades_dir.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if any(fnmatch.fnmatch(name, pattern) for pattern in UPGRADE_EXCLUDE_GLOBS):
            continue
        if not any(fnmatch.fnmatch(name, pattern) for pattern in UPGRADE_INCLUDE_GLOBS):
            continue
        stamp = parse_filename_stamp(name) or mtime_utc(path)
        age_days = (now - stamp).total_seconds() / 86400.0
        if age_days > UPGRADE_PACK_MAX_AGE_DAYS:
            result.add(
                SEVERITY_ERROR,
                f"pending upgrade pack is {int(age_days)} day(s) old "
                f"(limit {UPGRADE_PACK_MAX_AGE_DAYS}); apply or archive it",
                path,
            )
        else:
            result.add(
                SEVERITY_WARNING,
                f"pending upgrade pack awaiting application ({int(age_days)} day(s) old)",
                path,
            )
    return result


def check_absorbed_packs(root: Path) -> CheckResult:
    """Template-only: packs recorded by EVERY fleet ledger should be pruned."""
    result = CheckResult("absorbed-packs", "Fully-absorbed upgrade packs (prunable)")
    if not is_master_template(root):
        result.skipped = True
        result.skip_reason = "only applicable to the master template"
        return result

    upgrades = root / "docs" / "upgrades"
    if not upgrades.is_dir():
        return result

    fleet: list[Path] = []
    for entry in sorted(root.parent.iterdir()):
        if not entry.is_dir() or entry.name.startswith(("_", ".")):
            continue
        if (entry / "AGENTS.md").is_file() and (entry / "docs" / "upgrades").is_dir():
            fleet.append(entry)
    if not fleet:
        return result

    ledgers: list[str] = []
    for project in fleet:
        ledger = project / "docs" / "upgrades" / "upgrades_ledger.md"
        try:
            ledgers.append(ledger.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            ledgers.append("")

    for path in sorted(upgrades.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if any(fnmatch.fnmatch(name, pattern) for pattern in UPGRADE_EXCLUDE_GLOBS):
            continue
        if not any(fnmatch.fnmatch(name, pattern) for pattern in UPGRADE_INCLUDE_GLOBS):
            continue
        if all(name in ledger for ledger in ledgers):
            result.add(
                SEVERITY_WARNING,
                f"recorded by all {len(fleet)} fleet ledgers - prunable "
                "(agent runs: apply_upgrade.py prune)",
                path,
            )
    return result


def check_sprint_status(root: Path) -> CheckResult:
    """sprint-status.yaml must be fresher than the newest story and placeholder-free."""
    result = CheckResult("sprint-status", "sprint-status.yaml freshness")
    artifacts_dir = root / "_bmad-output" / "implementation-artifacts"
    status_path = artifacts_dir / "sprint-status.yaml"
    if not status_path.is_file():
        return result

    text = read_text(status_path)

    if not is_master_template(root) and TEMPLATE_PROJECT_NAME in text:
        result.add(
            SEVERITY_ERROR,
            f"contains the literal '{TEMPLATE_PROJECT_NAME}' in a non-template project "
            "(unsubstituted template placeholder)",
            status_path,
        )

    last_updated: datetime | None = None
    if yaml is not None:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            result.add(
                SEVERITY_WARNING,
                f"does not parse as YAML: {exc}",
                status_path,
            )
            data = None
        if isinstance(data, dict):
            last_updated = to_utc_datetime(data.get("last_updated"))
    else:
        match = re.search(r"^last_updated:\s*(.+?)\s*$", text, re.MULTILINE)
        if match:
            last_updated = to_utc_datetime(match.group(1))
    if last_updated is None:
        last_updated = mtime_utc(status_path)

    story_paths = [p for p in artifacts_dir.glob("*.story.md") if p.is_file()]
    if story_paths:
        newest_story = max(story_paths, key=lambda p: p.stat().st_mtime)
        lag = mtime_utc(newest_story) - last_updated
        if lag > timedelta(days=SPRINT_STATUS_MAX_LAG_DAYS):
            result.add(
                SEVERITY_WARNING,
                f"last_updated trails the newest story ({newest_story.name}) by "
                f"{int(lag.total_seconds() / 86400)} day(s) "
                f"(limit {SPRINT_STATUS_MAX_LAG_DAYS}); update sprint-status.yaml",
                status_path,
            )
    return result


def check_dead_links(root: Path) -> CheckResult:
    """Relative markdown link targets in AGENTS.md and README.md must exist."""
    result = CheckResult("dead-links", "Dead relative links")
    for rel_name in LINK_CHECK_FILES:
        md_path = root / rel_name
        if not md_path.is_file():
            continue
        for raw_target in MARKDOWN_LINK_PATTERN.findall(read_text(md_path)):
            target = raw_target.strip()
            if target.startswith("<") and ">" in target:
                target = target[1 : target.index(">")]
            if ' "' in target:  # drop optional link title
                target = target.split(' "', 1)[0]
            lowered = target.lower()
            if not target or any(lowered.startswith(p) for p in SKIPPED_LINK_PREFIXES):
                continue
            plain = unquote(target.split("#", 1)[0]).strip()
            if not plain:
                continue
            candidate = md_path.parent / plain
            if not candidate.exists():
                result.add(
                    SEVERITY_ERROR,
                    f"dead relative link '{raw_target.strip()}' in {rel_name}",
                    md_path,
                )
    return result


def check_template_leakage(root: Path) -> CheckResult:
    """Cloned repos must not carry the template's name or URL-encoded path."""
    result = CheckResult("template-leakage", "Template-path leakage")
    if is_master_template(root):
        result.skipped = True
        result.skip_reason = "repo is the master template itself"
        return result

    for rel_name in LEAKAGE_CHECK_FILES:
        path = root / rel_name
        if not path.is_file():
            continue
        text = read_text(path)
        for needle in (TEMPLATE_PROJECT_NAME, TEMPLATE_NAME_URLENCODED):
            count = text.count(needle)
            if count:
                result.add(
                    SEVERITY_ERROR,
                    f"found {count} occurrence(s) of '{needle}' (unclean clone)",
                    path,
                )
    return result


def check_config_yaml(root: Path) -> CheckResult:
    """config.yaml must parse and its paths.*_dir entries must exist."""
    result = CheckResult("config-yaml", "config.yaml integrity")
    config_path = root / "config.yaml"
    if not config_path.is_file():
        result.add(SEVERITY_WARNING, "config.yaml not found at repo root", config_path)
        return result
    if yaml is None:
        result.add(
            SEVERITY_WARNING,
            "pyyaml is not installed; config.yaml could not be validated",
            config_path,
        )
        return result
    try:
        data = yaml.safe_load(read_text(config_path))
    except yaml.YAMLError as exc:
        result.add(SEVERITY_WARNING, f"does not parse as YAML: {exc}", config_path)
        return result
    if not isinstance(data, dict):
        result.add(SEVERITY_WARNING, "top level is not a mapping", config_path)
        return result

    paths_section = data.get("paths")
    if not isinstance(paths_section, dict):
        return result
    for key in sorted(paths_section):
        if not (isinstance(key, str) and key.endswith("_dir")):
            continue
        value = paths_section[key]
        if not isinstance(value, str) or not value.strip():
            result.add(
                SEVERITY_WARNING,
                f"paths.{key} is not a usable path string",
                config_path,
            )
            continue
        if not (root / value).is_dir():
            result.add(
                SEVERITY_WARNING,
                f"paths.{key} -> '{value}' is not an existing directory",
                config_path,
            )
    return result


def path_is_inside(candidate: Path, root: Path) -> bool:
    """True iff `candidate` lives under `root`. Never raises."""
    try:
        return candidate.resolve(strict=False).is_relative_to(root.resolve(strict=False))
    except (OSError, ValueError):
        return False


def path_kind_matches(candidate: Path, kind: str) -> bool:
    """is_dir()/is_file() that cannot raise.

    On Windows these *raise* WinError 1920 on a dangling link rather than returning
    False (AGENTS 5.5.1), and a check that dies is a check that never reported.
    """
    try:
        return candidate.is_dir() if kind == "dir" else candidate.is_file()
    except OSError:
        return False


def check_knowledge_paths(root: Path) -> CheckResult:
    """Every configured knowledge.* path must resolve to something real.

    check_config_yaml deliberately validates only `paths.*_dir`, and the `knowledge:`
    keys were named specifically to avoid that sweep (they are not data directories).
    That left a hole the D:\\Projects relocation walked straight into (AGENTS 6): a
    SIBLING-RELATIVE `skills_registry` still *resolved* after the move -- just to
    nothing. memory_lint's skills checks then SKIP on a missing registry, so the
    linter reported a clean `0 error(s), 0 warning(s)` over a broken knowledge base.

    Severity splits on WHERE the path lands, because that is what is deterministic.
    A path inside the repo must exist wherever the repo is checked out, so a missing
    one is an ERROR. A path outside the repo (the shared skills registry is a separate
    git repo) legitimately does not exist on a CI runner, so it is a WARNING -- which
    still moves the summary off `0 warning(s)`, and that is what kills the false green.

    `architecture_map` is deliberately absent: check_architecture_map already owns it,
    and two checks reporting one defect is noise.
    """
    result = CheckResult("knowledge-paths", "knowledge.* paths resolve")
    config_path = root / "config.yaml"

    if yaml is None:
        result.skipped = True
        result.skip_reason = "pyyaml is not installed; config.yaml could not be validated"
        return result
    if not config_path.is_file():
        result.skipped = True
        result.skip_reason = "config.yaml not found at repo root"
        return result

    config = load_knowledge_config(root)
    if not config:
        result.skipped = True
        result.skip_reason = "config.yaml has no knowledge: section"
        return result

    for key, kind in (("memory_store", "dir"), ("skills_registry", "dir")):
        raw = config.get(key)
        if raw is None:
            continue
        if not isinstance(raw, str) or not raw.strip():
            result.add(SEVERITY_ERROR, f"knowledge.{key} is not a usable path string", config_path)
            continue

        declared = Path(raw)
        resolved = declared if declared.is_absolute() else (root / declared)
        if path_kind_matches(resolved, kind):
            continue

        inside = path_is_inside(resolved, root)
        if inside:
            result.add(
                SEVERITY_ERROR,
                f"knowledge.{key} -> '{raw}' is not an existing {kind} "
                f"(resolves inside the repo to {rel_path(resolved)})",
                config_path,
            )
        else:
            result.add(
                SEVERITY_WARNING,
                f"knowledge.{key} -> '{raw}' is not an existing {kind} (resolves outside the repo "
                f"to {resolved}). Expected on a CI runner; on a dev machine it means the path is "
                f"dangling -- and memory_lint's skills checks SKIP silently while it is",
                config_path,
            )
    return result


ADR_REFERENCE_PATTERN: re.Pattern[str] = re.compile(r"\bADR-\d{4}\b")

# Files a clone inherits verbatim, where a master ADR number is meaningless.
# `tests/` is excluded: its ADR ids are fixture data the authority-resolution tests
# assert on, not pointers. `docs/ADR/` is excluded: ADRs legitimately cite each other.
ADR_REF_SCAN_FILES: tuple[str, ...] = ("AGENTS.md", "README.md")
ADR_REF_SCAN_DIRS: tuple[str, ...] = ("scripts/utilities", ".claude/hooks", "backend")
# Files a clone inherits and then legitimately makes its OWN. A fleet project citing its
# own ADRs in config.yaml is correct, so scanning these everywhere would cry wolf on the
# very references we want people to write. They are therefore scanned in the MASTER ONLY,
# where the invariant is absolute: whatever the master ships is what every clone starts
# with, so a number here is a number nobody chose. Fixing it at source is the only place
# it can be fixed once (AGENTS 11, Golden Image).
#
# Measured 2026-08-15, and this is why the list is not just AGENTS.md and the scripts: the
# master shipped its coverage-ratchet ADR id in all three of these files. Four fleet
# projects had renumbered them by hand; NEON Vision AI had renumbered two and missed
# pyproject.toml, which still carried the master's line verbatim -- where that number is an
# unrelated decision about MCP tiering. The one file nothing checked is the one that stayed
# wrong, which is the argument for the check rather than for more care.
ADR_REF_SCAN_TEMPLATE_ONLY_FILES: tuple[str, ...] = (
    "config.yaml",
    "pyproject.toml",
    "docs/coverage_baseline.json",
)
# Upgrade packs are COPIED into every fleet project, so a master ADR number in one resolves
# to an unrelated local decision. NEON video creator hit this: the migration pack's header
# cited a number that is a rendering decision there. `upgrades_ledger.md` is excluded -- it is
# a per-project historical record whose old rows legitimately name that project's own ADRs.
ADR_REF_SCAN_GLOBS: tuple[tuple[str, str], ...] = (("docs/upgrades", "*.md"),)
LEDGER_FILENAME: str = "upgrades_ledger.md"


def check_adr_references(root: Path) -> CheckResult:
    """Nothing a clone inherits may cite a specific ADR number.

    ADR ids are per-project: a clone starts an empty register and numbers its own from
    0001, so a master number means nothing there. Worse, once the clone's register grows
    past that number the reference starts to *resolve* -- to an unrelated decision.

    Measured 2026-07-28: NEON video creator has 52 of its own ADRs, so every one of the
    nine master ids cited by the inherited scripts resolved there, all to the wrong
    document. LINT-IGNORE: the next line quotes the defect, it does not commit it.
    "route dev-cache off OS drive (ADR-0016)" pointed at agentic-swarm-for-data-pipelines.
    Expert tippers hit the same the moment it wrote its own fifteenth ADR: a coverage lint
    message began pointing at an approved ADR about sync roots instead. A dangling pointer
    is detectable; a resolving-but-wrong one is not.

    Cite the AGENTS section that owns the rule instead -- section numbers are identical
    in every project that holds this constitution.
    """
    result = CheckResult("adr-refs", "No ADR numbers in inherited files")

    targets: list[Path] = [root / name for name in ADR_REF_SCAN_FILES]
    if is_master_template(root):
        targets.extend(root / name for name in ADR_REF_SCAN_TEMPLATE_ONLY_FILES)
    for rel in ADR_REF_SCAN_DIRS:
        directory = root / rel
        if directory.is_dir():
            targets.extend(sorted(directory.rglob("*.py")))
    for rel, pattern in ADR_REF_SCAN_GLOBS:
        directory = root / rel
        if directory.is_dir():
            targets.extend(sorted(p for p in directory.glob(pattern) if p.name != LEDGER_FILENAME))

    for path in targets:
        try:
            if not path.is_file():
                continue
        except OSError:  # dangling link (AGENTS 5.5.1)
            continue
        # LINT-IGNORE on the PRECEDING line, matching the convention used by
        # flag_literalpath_wildcards -- the natural place to write an exemption.
        suppressed = False
        for lineno, line in enumerate(read_text(path).splitlines(), start=1):
            if suppressed:
                suppressed = "LINT-IGNORE" in line.upper()
                continue
            if "LINT-IGNORE" in line.upper():
                suppressed = True
                continue
            for match in ADR_REFERENCE_PATTERN.findall(line):
                result.add(
                    SEVERITY_ERROR,
                    f"line {lineno} cites {match}; a clone numbers its own ADRs from 0001, so this "
                    "means nothing there and will eventually resolve to an unrelated decision. "
                    "Cite the AGENTS section that owns the rule",
                    path,
                )
    return result


# Script extensions a hook command may name without a directory prefix. The hook host
# runs from the project root, so a bare `guard.py` is a real repo-relative path.
HOOK_SCRIPT_SUFFIXES: tuple[str, ...] = (".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".ps1")


def _hook_config_files(root: Path) -> list[Path]:
    """Vendor adapter files that may register hooks.

    The Adapter Rule (AGENTS 2) keeps rules vendor-neutral. The rule here is "a
    registered hook must be able to execute"; knowing that a hook host keeps its
    registrations in a `settings*.json` inside a dot-directory is adapter knowledge,
    so it is isolated in this one helper.
    """
    files: list[Path] = []
    try:
        directories = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("."))
    except OSError:  # dangling link (AGENTS 5.5.1)
        return files
    for directory in directories:
        if directory.name.lower() in WALK_EXCLUDE_DIRS:
            continue
        files.extend(sorted(directory.glob("settings*.json")))
    return files


def _iter_hook_commands(config: object) -> list[str]:
    """Every `command` string under a `hooks` block, whatever the event names are."""
    commands: list[str] = []
    if not isinstance(config, dict):
        return commands
    hooks = config.get("hooks")
    if not isinstance(hooks, dict):
        return commands
    for entries in hooks.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks") or []:
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    commands.append(hook["command"])
    return commands


def _has_unquoted_backslash(command: str) -> bool:
    r"""True when a backslash sits outside single quotes, where the shell eats it.

    Inside single quotes a backslash is literal, so a hook piping through
    `grep -qE '\.env'` is correct and must not be failed. Everything else -- bare or
    double-quoted -- is the defect: in POSIX sh a backslash is still special inside
    double quotes.
    """
    in_single = False
    for char in command:
        if char == "'":
            in_single = not in_single
        elif char == "\\" and not in_single:
            return True
    return False


def _is_checkable_hook_path(token: str) -> bool:
    """True when a command token is a repo-relative path this check can verify."""
    if token.startswith("-"):
        return False  # a flag
    if any(char.isspace() for char in token):
        return False  # `sh -c "<whole subcommand>"` arrives as one token; not a path
    if "$" in token or "%" in token or "{" in token:
        return False  # variable expansion; not resolvable statically
    # `Path("/usr/bin/python3").is_absolute()` is False on WINDOWS (no drive), so the
    # POSIX form is tested explicitly. Without this the token is joined onto the repo
    # root and ERRORs locally while passing on a Linux runner.
    if token.startswith("/") or token.startswith("\\") or re.match(r"^[A-Za-z]:", token):
        return False
    if Path(token).is_absolute():
        return False
    # A bare `guard.py` IS repo-relative (the hook host runs from the project root), so
    # checking only tokens containing "/" would wave through a missing script -- exactly
    # the fail-open this check exists to prevent.
    if "/" not in token and not token.endswith(HOOK_SCRIPT_SUFFIXES):
        return False  # a bare command resolved via PATH
    # Environment directories are git-ignored and platform-specific (see below).
    return token.split("/", 1)[0].lower() not in WALK_EXCLUDE_DIRS


def check_hook_wiring(root: Path) -> CheckResult:
    """A registered governance hook must actually be able to run.

    A hook registered with backslash paths never executes: a POSIX shell consumes
    `\\S` and `\\h` as escapes, the command is not found, and the process exits 127 --
    while a PreToolUse hook blocks only on exit **2**. Every other status is treated as
    allow, so the guard fails open silently on every invocation. Nothing is logged, and
    a reader of the configuration sees a correctly configured control. No unit test of
    the underlying rule can see this: the rule is fine, the wiring is what is broken.

    Deliberate exemption, stated rather than hidden: paths inside environment
    directories (`.venv`, `node_modules`, ...) are NOT existence-checked. They are
    git-ignored and platform-specific -- a Windows `.venv/Scripts/python.exe` is
    legitimately absent on a Linux runner -- so checking them would fail the gate for
    a reason that is not the defect. The backslash rule applies to every token.

    Residual gap this check CANNOT close: an interpreter that exists but is the wrong
    one, or a PATH name that does not resolve. Both need execution, not inspection.
    """
    result = CheckResult("hook-wiring", "registered hooks can actually execute")

    configs = _hook_config_files(root)
    if not configs:
        result.skipped = True
        result.skip_reason = "no vendor hook configuration files in the repository"
        return result

    checked_any = False
    for config_path in configs:
        try:
            config = json.loads(read_text(config_path))
        except (json.JSONDecodeError, ValueError):
            result.add(
                SEVERITY_ERROR,
                "hook configuration is not valid JSON, so its hooks cannot be registered",
                config_path,
            )
            continue

        commands = _iter_hook_commands(config)
        if commands:
            checked_any = True
        for command in commands:
            if _has_unquoted_backslash(command):
                result.add(
                    SEVERITY_ERROR,
                    (
                        f"hook command uses backslash paths and will NOT run: {command!r} - "
                        "the shell consumes them as escapes, the command is not found, and the "
                        "hook exits 127, which is treated as ALLOW. Use forward slashes"
                    ),
                    config_path,
                )
                continue
            try:
                tokens = shlex.split(command)
            except ValueError:
                result.add(
                    SEVERITY_ERROR,
                    (
                        f"hook command cannot be parsed by a shell: {command!r} - "
                        "unbalanced quoting means it will never run"
                    ),
                    config_path,
                )
                continue
            for token in tokens:
                if not _is_checkable_hook_path(token):
                    continue
                if not (root / token).exists():
                    result.add(
                        SEVERITY_ERROR,
                        (
                            f"hook command references a path that does not exist: {token!r} "
                            f"in {command!r} - the hook will exit non-zero and fail open"
                        ),
                        config_path,
                    )

    # Only SKIP when there is genuinely nothing to say. Reporting `[SKIP] ... registers
    # no hooks` while the check has already emitted a blocking ERROR is a report that
    # contradicts its own findings.
    if not checked_any and not result.findings:
        result.skipped = True
        result.skip_reason = "vendor configuration present but registers no hooks"
    return result


#: Marks a live prompt/schema artifact. The stem up to and including the marker is the
#: identity; whatever follows is version noise (AGENTS 5.4).
# Widened 2026-08-29 (prompt_archive_check_defects pack): `__prompt` without the
# trailing underscores is a compliant shape in at least one fleet project
# (`10_writer__prompt.txt`), and the old `__prompt__` marker could not SEE those
# files at all -- an invisible live prompt is exempt from the whole check.
# A superset match: every `__prompt__` name also contains `__prompt`.
PROMPT_ARTIFACT_MARKERS: tuple[str, ...] = ("__prompt", "__schema")
#: `_YYMMDD_HHMM` immediately before the extension -- the pre-2026-08-16 live convention.
PROMPT_TIMESTAMP_PATTERN: re.Pattern[str] = re.compile(r"_\d{6}_\d{4}$")


def _prompt_artifact_stem(name: str) -> str | None:
    """Return the identity stem of a prompt/schema filename, or None if it is neither.

    Identity is "the whole name minus its version stamp", NOT "everything up to the
    marker". The obvious implementation splits on the marker and keeps the prefix --
    which works for ``10_agent__prompt__260711_0035.txt`` and breaks badly for the
    equally-valid ``__prompt__blog_fact_extractor_260728_2200.md``, where the identity
    is AFTER the marker: every artifact in that project collapses to the stem
    ``__prompt__``, so one archived file would vouch for every other prompt beside it.

    Stripping the stamp instead handles both layouts:

    * ``10_agent__prompt__.txt``                    -> ``10_agent__prompt__``
    * ``10_agent__prompt___260711_0036.txt``        -> ``10_agent__prompt__``
    * ``__prompt__blog_fact_extractor_260728_2200`` -> ``__prompt__blog_fact_extractor``

    Stem matching -- never name equality -- is what lets an un-timestamped live file
    find its timestamped archived copies.
    """
    if not any(marker in name for marker in PROMPT_ARTIFACT_MARKERS):
        return None
    bare = name.rsplit(".", 1)[0] if "." in name else name
    # Strip stamps REPEATEDLY, not once: archiving a grandfathered live file
    # (`..._260711_0035.txt`) under AGENTS 5.4 appends a second stamp
    # (`..._260711_0035_260711_0036.txt`), and a single-pass strip left one stamp
    # behind -- so a CORRECTLY archived legacy file read as having no archive at
    # all, a confirmed false ERROR (prompt_archive_check_defects pack, verified at
    # HEAD 2026-08-29). Then normalise trailing underscores, because the separator
    # count differs between conventions (`__prompt__<stamp>` vs `__prompt___<stamp>`)
    # and would otherwise split one identity in two.
    while True:
        stripped = PROMPT_TIMESTAMP_PATTERN.sub("", bare)
        if stripped == bare:
            break
        bare = stripped
    return bare.rstrip("_")


def check_prompt_archive(root: Path) -> CheckResult:
    """Every live prompt/schema must already have an archived copy (AGENTS 5.4).

    Archive-on-write, not archive-on-supersession. The old rule asked the author to
    preserve the previous version at the exact moment they were replacing it -- the one
    moment their attention is entirely on the new text. It failed the way every
    "remember to clean up afterwards" rule fails: silently, leaving no artefact behind
    to prove anything went missing. One project reached 8 live files with 7 having no
    archived copy at all, and nothing ever reported a problem.

    Two severities, deliberately asymmetric:

    * **ERROR -- a live file with no archived copy.** This is the actual loss of
      history, and it is what the rule exists to prevent.
    * **WARNING -- a live file whose name still carries a timestamp.** Measured across
      the fleet on 2026-08-16: 5 of 6 projects follow the OLD convention correctly and
      their loaders match on those exact names (one hardcodes
      ``__schema__260522_2222.txt``; two glob ``__prompt__..._*``). Renaming 27 files
      would break prompt loading in three live projects for no functional gain, so
      existing names are grandfathered and this can never be an ERROR. New projects
      start clean because the template ships clean.

    Scoped PER AGENT: the archived copy must live in that agent's own ``archive/``.
    Without that, one well-archived agent vouches for every other and the check reads
    as passing while covering nothing.
    """
    result = CheckResult("prompt-archive", "live prompts have archived copies")

    modules_dir = root / "backend" / "ai_modules"
    if not modules_dir.is_dir():
        result.skipped = True
        result.skip_reason = "no backend/ai_modules/ in this project"
        return result

    try:
        agents = sorted(p for p in modules_dir.iterdir() if p.is_dir())
    except OSError:  # dangling link (AGENTS 5.5.1)
        agents = []

    checked_any = False
    for agent in agents:
        archive_dir = agent / "archive"
        archived_stems: set[str] = set()
        if archive_dir.is_dir():
            for archived in archive_dir.iterdir():
                if not archived.is_file():
                    continue
                stem = _prompt_artifact_stem(archived.name)
                if stem:
                    archived_stems.add(stem)

        for live in sorted(agent.iterdir()):
            if not live.is_file():
                continue
            stem = _prompt_artifact_stem(live.name)
            if stem is None:
                continue
            checked_any = True

            if stem not in archived_stems:
                result.add(
                    SEVERITY_ERROR,
                    (
                        f"live prompt/schema '{live.name}' has NO archived copy in "
                        f"{agent.name}/archive/ - write one now, stamped from the file's own "
                        "mtime (a backfill stamped 'today' fabricates the provenance the "
                        "archive exists to provide)"
                    ),
                    live,
                )

            bare = live.name[: -len(live.suffix)] if live.suffix else live.name
            if PROMPT_TIMESTAMP_PATTERN.search(bare):
                result.add(
                    SEVERITY_WARNING,
                    (
                        f"live prompt/schema '{live.name}' carries a timestamp (the pre-2026-08-16 "
                        "convention). New agents should use a bare name for a stable import path - "
                        "but existing files are GRANDFATHERED: loaders match on these names, so do "
                        "not rename without updating them. WARNING only, never an error"
                    ),
                    live,
                )

    if not checked_any and not result.findings:
        result.skipped = True
        result.skip_reason = "backend/ai_modules/ present but holds no prompt/schema artifacts"
    return result


def _config_section(root: Path, section: str) -> dict:
    """Read one top-level section of config.yaml (empty dict on any failure)."""
    config_path = root / "config.yaml"
    if not config_path.is_file():
        return {}
    try:
        data = yaml.safe_load(read_text(config_path))
    except yaml.YAMLError:
        return {}
    value = (data or {}).get(section)
    return value if isinstance(value, dict) else {}


def check_sprint_drift(root: Path) -> CheckResult:
    """sprint-status.yaml must agree with the story files on disk (AGENTS 6).

    `sync_sprint_status.py check` existed for exactly this and nothing ran it at
    session close, so a registry could fall behind its own story files until a
    human noticed (owner comment C6, 2026-08-29). Drift is an ERROR: the registry
    is the sole numbering authority, and a stale one understates every metric.
    """
    result = CheckResult("sprint-drift", "sprint-status.yaml agrees with story files")
    try:
        import sync_sprint_status
    except ImportError:
        result.add(SEVERITY_ERROR, "sync_sprint_status.py is missing from scripts/utilities", root)
        return result

    directory = sync_sprint_status.artifacts_dir(root)
    status_path = directory / "sprint-status.yaml"
    if not status_path.is_file():
        result.skipped = True
        result.skip_reason = "no sprint-status.yaml (no BMAD implementation artifacts yet)"
        return result

    stories, _warnings = sync_sprint_status.collect_stories(directory)
    registry = sync_sprint_status.load_registry(status_path)
    if registry is None:
        result.add(SEVERITY_ERROR, "sprint-status.yaml exists but cannot be parsed", status_path)
        return result
    existing = registry.get("development_status")
    existing = existing if isinstance(existing, dict) else {}
    registry_stories = {
        str(k): str(v) for k, v in existing.items()
        if sync_sprint_status.STORY_KEY_RE.match(str(k))
    }

    disk_keys = {s.key for s in stories}
    for story in stories:
        if story.key not in registry_stories:
            result.add(
                SEVERITY_ERROR,
                f"story on disk but not in the registry: {story.key} - run sync_sprint_status.py sync",
                status_path,
            )
        elif registry_stories[story.key] != story.status:
            result.add(
                SEVERITY_ERROR,
                f"stale status for {story.key}: registry '{registry_stories[story.key]}' vs disk "
                f"'{story.status}' - run sync_sprint_status.py sync",
                status_path,
            )
    for key in sorted(registry_stories):
        if key not in disk_keys:
            result.add(
                SEVERITY_ERROR,
                f"registry story entry has no file on disk: {key} - run sync_sprint_status.py sync",
                status_path,
            )
    return result


#: Filename shape of a per-story review artifact (AGENTS 4 step 6): the glob is
#: deliberately loose about the stamp so a hand-named review still counts.
REVIEW_DIR_NAME: str = "code review"


def check_story_lifecycle(root: Path) -> CheckResult:
    """A story is not done without its review; an epic is not done without its retro.

    AGENTS 4 step 6 (owner decisions C3/D14, 2026-08-29). Review evidence is a
    persisted artifact -- `docs/code review/story-<id>-review*.md` -- because a
    review nobody can point at afterwards is the assumed-as-verified shape.
    Stories completed BEFORE the rule's adoption are grandfathered via
    `governance.review_artifact_exempt` in config.yaml (a mapping of story id to
    the reason, never a bare list -- same convention as _KNOWN_ID_GAPS).
    """
    result = CheckResult("story-lifecycle", "done stories have reviews; done epics have retros")
    try:
        import sync_sprint_status
    except ImportError:
        result.skipped = True
        result.skip_reason = "sync_sprint_status.py is missing; sprint-drift reports that"
        return result

    status_path = sync_sprint_status.artifacts_dir(root) / "sprint-status.yaml"
    if not status_path.is_file():
        result.skipped = True
        result.skip_reason = "no sprint-status.yaml (no BMAD implementation artifacts yet)"
        return result
    registry = sync_sprint_status.load_registry(status_path)
    existing = (registry or {}).get("development_status")
    existing = existing if isinstance(existing, dict) else {}
    if not existing:
        result.skipped = True
        result.skip_reason = "registry has no rows yet (fresh project)"
        return result

    exempt_raw = _config_section(root, "governance").get("review_artifact_exempt")
    exempt: dict[str, str] = (
        {str(k): str(v) for k, v in exempt_raw.items()} if isinstance(exempt_raw, dict) else {}
    )

    review_dir = root / "docs" / REVIEW_DIR_NAME
    checked = 0
    for key, value in existing.items():
        key_s, value_s = str(key), str(value)
        story_match = re.match(r"^(\d+)-(\d+)-", key_s)
        if story_match and value_s == "done":
            checked += 1
            story_id = f"{story_match.group(1)}-{story_match.group(2)}"
            if story_id in exempt:
                continue
            pattern = f"story-{story_id}-review*.md"
            found = list(review_dir.glob(pattern)) if review_dir.is_dir() else []
            found += (
                list((review_dir / "archive").glob(pattern))
                if (review_dir / "archive").is_dir()
                else []
            )
            if not found:
                result.add(
                    SEVERITY_ERROR,
                    f"story {key_s} is done but docs/{REVIEW_DIR_NAME}/{pattern} does not exist "
                    "(AGENTS 4 step 6). Run the review and write the artifact, or add the story "
                    "to governance.review_artifact_exempt with the reason",
                    status_path,
                )
        epic_match = re.match(r"^epic-(\d+)$", key_s)
        if epic_match and value_s == "done":
            checked += 1
            retro_key = f"epic-{epic_match.group(1)}-retrospective"
            retro = str(existing.get(retro_key, ""))
            if retro != "done":
                result.add(
                    SEVERITY_ERROR,
                    f"{key_s} is done but {retro_key} is "
                    f"{'missing' if not retro else retro!r} (AGENTS 4 step 6): an epic closes "
                    "with its retrospective run and findings implemented",
                    status_path,
                )
    if checked == 0 and not result.findings:
        result.skipped = True
        result.skip_reason = "no done stories or epics yet - nothing for this check to hold"
    return result


def check_frontend_testing(root: Path) -> CheckResult:
    """A web UI ships with Playwright E2E + vitest + ratcheted coverage, or it errors.

    AGENTS 5.7 (owner comment C5, 2026-08-29: "strictly enforcing exhaustive
    testing via Playwright"). Detection is deliberately narrow -- a `frontend/`
    directory or root `package.json` -- so backend-only projects SKIP rather than
    wave a vacuous pass (AGENTS 4.1 axis 7).
    """
    result = CheckResult("frontend-testing", "web UIs carry Playwright + vitest + coverage wiring")

    frontend_dir = root / "frontend"
    package_json = None
    for candidate in (frontend_dir / "package.json", root / "package.json"):
        if candidate.is_file():
            package_json = candidate
            break
    if package_json is None:
        result.skipped = True
        result.skip_reason = "no web frontend detected (no frontend/package.json or package.json)"
        return result

    ui_root = package_json.parent
    package_text = read_text(package_json)

    def _exists_any(*globs: str) -> bool:
        for pattern in globs:
            try:
                if any(ui_root.glob(pattern)) or any(root.glob(pattern)):
                    return True
            except OSError:
                continue
        return False

    if not _exists_any("playwright.config.*", "e2e/playwright.config.*"):
        result.add(
            SEVERITY_ERROR,
            "web frontend has no playwright.config.* - E2E testing is mandatory for UI "
            "projects (AGENTS 5.7); the scaffold-frontend-testing skill stamps it",
            package_json,
        )
    spec_files = [
        p for pattern in ("e2e/**/*.spec.*", "tests/e2e/**/*.spec.*", "**/*.e2e.spec.*")
        for base in (ui_root, root)
        for p in base.glob(pattern)
        if p.is_file()
    ]
    if not spec_files:
        result.add(
            SEVERITY_ERROR,
            "web frontend has no E2E spec files (searched e2e/**/*.spec.*, "
            "tests/e2e/**/*.spec.*) - a Playwright config with zero journeys tests nothing",
            package_json,
        )
    if "vitest" not in package_text and not _exists_any("vitest.config.*"):
        result.add(
            SEVERITY_ERROR,
            "web frontend has no vitest wiring - the unit/component base of the pyramid "
            "(AGENTS 5.7)",
            package_json,
        )
    coverage = _config_section(root, "testing").get("coverage")
    extra = (coverage or {}).get("extra_coverage_xml") if isinstance(coverage, dict) else None
    if not extra:
        result.add(
            SEVERITY_ERROR,
            "frontend coverage is not wired into the ratchet: testing.coverage."
            "extra_coverage_xml is empty in config.yaml (AGENTS 5.7)",
            root / "config.yaml",
        )
    return result


def check_memory_inheritance_declared(root: Path) -> CheckResult:
    """Template only: every memory page must declare whether a clone inherits it.

    AGENTS 7 splits the template's knowledge in two: OPERATING knowledge, which a child
    needs to work inside this structure, and PROVENANCE, which records how the template
    itself was built. `bootstrap_project.ps1` keeps only pages marked
    `metadata.inherit: true` and fails closed on anything else.

    Fail-closed alone is not enough, because the failure is silent in the wrong direction:
    an undeclared page is dropped without complaint, so a genuinely cross-project page
    could go missing from every future clone and nobody would notice. Requiring the
    declaration here makes the choice explicit at authoring time.

    Template-scoped on purpose: the flag only means anything in the repo that gets cloned,
    and the fleet's ~50 existing pages predate it -- demanding it everywhere would fail
    lint in every project for no benefit.
    """
    result = CheckResult("memory-inherit", "Memory pages declare clone inheritance")
    if not is_master_template(root):
        result.skipped = True
        result.skip_reason = "only applicable to the master template (the repo that gets cloned)"
        return result
    if yaml is None:
        result.skipped = True
        result.skip_reason = "pyyaml is not installed; frontmatter could not be parsed"
        return result

    config = load_knowledge_config(root)
    mem_store = config.get("memory_store", "docs/memory")
    memory_dir = root / mem_store if not Path(mem_store).is_absolute() else Path(mem_store)
    if not memory_dir.is_dir():
        result.skipped = True
        result.skip_reason = f"memory store not found at {rel_path(memory_dir)}"
        return result

    for page in sorted(memory_dir.glob("*.md")):
        if page.name == "MEMORY.md":
            continue
        text = read_text(page)
        parts = text.split("---")
        if len(parts) < 3:
            result.add(SEVERITY_WARNING, "no parseable frontmatter; cannot read metadata.inherit", page)
            continue
        try:
            front = yaml.safe_load(parts[1])
        except yaml.YAMLError as exc:
            result.add(SEVERITY_WARNING, f"frontmatter does not parse: {exc}", page)
            continue
        meta = front.get("metadata") if isinstance(front, dict) else None
        value = meta.get("inherit") if isinstance(meta, dict) else None
        if value is None:
            result.add(
                SEVERITY_ERROR,
                "does not declare metadata.inherit (true = operating knowledge a clone needs; "
                "false = provenance about how this template was built). Undeclared pages are "
                "dropped from clones silently, so say which it is (AGENTS 7)",
                page,
            )
        elif not isinstance(value, bool):
            result.add(
                SEVERITY_ERROR,
                f"metadata.inherit must be a boolean, got {value!r}",
                page,
            )
    return result


def check_loose_stale_files(root: Path) -> CheckResult:
    """Timestamped working files must be archived within the allowed age."""
    result = CheckResult("loose-files", "Loose stale timestamped files")
    now = datetime.now(UTC)
    for rel_dir in LOOSE_FILE_DIRS:
        directory = root / rel_dir
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            stamp = parse_filename_stamp(path.name)
            if stamp is None:
                continue
            age_days = (now - stamp).total_seconds() / 86400.0
            if age_days > LOOSE_FILE_MAX_AGE_DAYS:
                result.add(
                    SEVERITY_WARNING,
                    f"loose file is {int(age_days)} day(s) old (limit {LOOSE_FILE_MAX_AGE_DAYS}); archive it",
                    path,
                )
    return result


def walk_source_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    """Yield committed-source files with the given suffixes, skipping vendor/archive trees.

    Uses ``os.walk`` with in-place pruning rather than ``rglob`` so excluded trees are
    never descended into, and guards every probe with ``OSError``: a dangling legacy
    symlink *raises* WinError 1920 instead of returning False (AGENTS 5.5.1), and one such
    link anywhere in the tree would otherwise kill the whole lint run.
    """
    this_file = Path(__file__).resolve()
    matches: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _err: None):
        dirnames[:] = [d for d in dirnames if d.lower() not in WALK_EXCLUDE_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() not in suffixes:
                continue
            try:
                if not path.is_file() or path.resolve() == this_file:
                    # The linter names the very patterns it hunts for; scanning itself
                    # is a false positive.
                    continue
            except OSError:
                continue
            matches.append(path)
    return sorted(matches)


def check_script_encoding(root: Path) -> CheckResult:
    """PowerShell 5.1 decodes BOM-less files as ANSI: shell scripts must be pure ASCII.

    A UTF-8 em-dash read as cp1252 becomes a smart quote - a string delimiter - which
    silently swallows following code into a runaway string. No error is raised.
    """
    result = CheckResult("script-ascii", "Shell scripts are pure ASCII")
    for path in walk_source_files(root, SHELL_SCRIPT_SUFFIXES):
        data = path.read_bytes()
        offending = {byte for byte in data if byte > 127}
        if not offending:
            continue
        line_no = data[: data.index(bytes([min(offending)]))].count(b"\n") + 1
        result.add(
            SEVERITY_ERROR,
            f"non-ASCII byte(s) {sorted(offending)[:3]} first seen near line {line_no}; "
            "PowerShell 5.1 reads BOM-less files as ANSI and can silently corrupt parsing",
            path,
        )
    return result


def flag_literalpath_wildcards(result: CheckResult, path: Path, text: str, *, fenced_only: bool = False) -> None:
    """`-LiteralPath` + a wildcard copies NOTHING, silently. It is always a bug.

    Statically detectable and unambiguous, so it belongs in CI rather than in prose -- the
    prose warning had already been written, and the bug shipped anyway.

    In markdown (upgrade packs), only **fenced code** is audited: a pack that warns about this
    footgun has to be able to *show* it in prose. A deliberate counter-example inside a fence
    carries an explicit ``LINT-IGNORE`` comment -- explicit, and impossible to trip by accident.
    """
    in_fence = False
    suppressed = False  # set by a LINT-IGNORE on the PRECEDING line (the natural place to write it)
    for line_no, line in enumerate(text.splitlines(), start=1):
        if fenced_only and line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if fenced_only and not in_fence:
            continue
        if "LINT-IGNORE" in line.upper():
            suppressed = True  # suppresses this line AND the next
            continue
        was_suppressed, suppressed = suppressed, False
        if was_suppressed:
            continue
        match = LITERALPATH_ARG_PATTERN.search(line)
        if match and any(ch in match.group("arg") for ch in "*?"):
            result.add(
                SEVERITY_ERROR,
                f"line {line_no}: -LiteralPath is given a wildcard, which it does NOT expand - "
                "it matches nothing and silently copies nothing. Use -Path for wildcards",
                path,
            )


def _is_c_drive_literal_exempt(path: Path) -> bool:
    """True where a literal C: path is INPUT DATA rather than a destination.

    temp_and_disk_discipline S5. The literal check flags any "C:\\..." string. In
    application code that is a real defect. In **tests** it is usually input data -- a
    fixture asserting on Windows path-escaping, or a WSL->Windows conversion
    expectation -- and in **generated artifacts** it is unactionable noise.

    The originating project had 53 such warnings, 50 of them noise, and that volume is
    exactly why its 3 genuine `tempfile`-with-no-`dir=` findings sat unfixed for three
    days. **Narrowing beats suppressing: a check nobody reads is worse than no check,
    because it looks like coverage.** Note the scope is deliberately asymmetric -- only
    the LITERAL check is narrowed; the tempfile call-shape checks below still apply
    everywhere, including tests, because that shape is actionable whoever writes it.
    """
    parts = {p.lower() for p in path.parts}
    if "tests" in parts or path.name.lower().startswith("test_"):
        return True
    return path.name.lower().endswith("_generated.py")


def flag_c_drive_and_tempfile_defaults(result: CheckResult, path: Path, text: str) -> None:
    """Flag application code that writes generated files onto the OS drive (AGENTS 5.5.1).

    Conservative, single-line heuristics -- same wart as ``flag_literalpath_wildcards``: a path
    built across an intermediate variable, or a multi-line ``tempfile`` call whose ``dir=`` kwarg
    lands on a later line, is not caught. A deliberate counter-example carries ``LINT-IGNORE``.
    """
    literal_exempt = _is_c_drive_literal_exempt(path)
    suppressed = False  # set by a LINT-IGNORE on the PRECEDING line (the natural place to write it)
    for line_no, line in enumerate(text.splitlines(), start=1):
        if "LINT-IGNORE" in line.upper():
            suppressed = True  # suppresses this line AND the next
            continue
        was_suppressed, suppressed = suppressed, False
        if was_suppressed:
            continue
        if not literal_exempt and HARDCODED_C_DRIVE_PATTERN.search(line):
            result.add(
                SEVERITY_WARNING,
                f"line {line_no}: hardcodes a C: path; generated/temp files belong on the "
                "project's own drive (see bootstrap_project.ps1's dev-cache/temp redirect), "
                "never a literal C:\\",
                path,
            )
        if TEMPFILE_OS_DEFAULT_PATTERN.search(line):
            result.add(
                SEVERITY_WARNING,
                f"line {line_no}: tempfile.gettempdir() resolves to the OS default (usually "
                "C:); pass an explicit dir= under the project's own data/temp path instead",
                path,
            )
        match = TEMPFILE_NO_DIR_PATTERN.search(line)
        if match and "dir=" not in line:
            result.add(
                SEVERITY_WARNING,
                f"line {line_no}: tempfile.{match.group(1)}() with no dir= falls back to the "
                "OS default temp path (usually C:); pass dir= explicitly",
                path,
            )


def check_windows_execution_traps(root: Path) -> CheckResult:
    """Static audits for the native-Windows traps that fail silently rather than loudly."""
    result = CheckResult("windows-traps", "Native-Windows execution traps")

    # Upgrade packs are executable instructions: an agent runs the snippets inside them, so a
    # silent no-op in a pack is as dangerous as one in a script - more so, since it is copied
    # into every project. Audit them alongside the scripts.
    for pack in sorted((root / "docs" / "upgrades").glob("*.md")):
        flag_literalpath_wildcards(result, pack, read_text(pack), fenced_only=True)

    for path in walk_source_files(root, SHELL_SCRIPT_SUFFIXES):
        text = read_text(path)
        flag_literalpath_wildcards(result, path, text)
        for line_no, line in enumerate(text.splitlines(), start=1):
            match = UNQUOTED_ARGLIST_PATTERN.search(line)
            if match:
                args = match.group("args")
                if BARE_VAR_PATTERN.search(QUOTED_VAR_PATTERN.sub("", args)):
                    result.add(
                        SEVERITY_ERROR,
                        f"line {line_no}: -ArgumentList interpolates an unquoted variable; "
                        "Start-Process does not quote arguments, so spaced paths split "
                        "(use ('\"{0}\"' -f $path))",
                        path,
                    )
            if NPM_SHIM_PATTERN.search(line):
                result.add(
                    SEVERITY_WARNING,
                    f"line {line_no}: npm .cmd shim / npx invocation mis-parses '&' in the "
                    "project path; call the JS entrypoint directly (node <bin>.js)",
                    path,
                )

    for path in walk_source_files(root, (".py",)):
        text = read_text(path)
        flag_c_drive_and_tempfile_defaults(result, path, text)
        if "fcntl" in text and re.search(r"except ImportError[^\n]*:\s*\n\s*return True", text):
            result.add(
                SEVERITY_ERROR,
                "POSIX-only lock falls back to 'return True' on Windows: the protection is a "
                "silent no-op. Implement msvcrt.locking or fail loudly",
                path,
            )
        if WMIC_PATTERN.search(text):
            result.add(
                SEVERITY_WARNING,
                "wmic is removed on Windows 11 24H2+ and fails silently; prefer tasklist/psutil",
                path,
            )

    pytest_ini = root / "pytest.ini"
    pyproject = root / "pyproject.toml"
    if pytest_ini.is_file() and pyproject.is_file():
        if "[tool.pytest.ini_options]" in read_text(pyproject):
            result.add(
                SEVERITY_ERROR,
                "pytest.ini exists, so [tool.pytest.ini_options] in pyproject.toml is silently "
                "ignored; consolidate all pytest config into pytest.ini",
                pyproject,
            )

    if pyproject.is_file():
        uses_zoneinfo = any(
            "zoneinfo" in read_text(path) for path in walk_source_files(root, (".py",))
        )
        if uses_zoneinfo and "tzdata" not in read_text(pyproject):
            result.add(
                SEVERITY_ERROR,
                "zoneinfo is used but tzdata is not a declared dependency; Windows ships no OS "
                "timezone database, so this works under WSL and fails natively",
                pyproject,
            )

    return result


ARCHITECTURE_ALIAS_RE: re.Pattern[str] = re.compile(r"architecture", re.IGNORECASE)
LAST_REVIEWED_RE: re.Pattern[str] = re.compile(
    r"^last_reviewed:\s*(\d{4}-\d{2}-\d{2})\s*$", re.IGNORECASE | re.MULTILINE
)


def check_architecture_map(root: Path) -> CheckResult:
    """The architecture map must be SINGULAR and demonstrably alive (AGENTS 5.8).

    Two things here are mechanically checkable, and we check only those:

    1. **Exactly one map.** A second architecture document is not extra diligence, it
       is a fork: two files that disagree, with no rule for which wins. (One fleet
       project had drifted to four.)
    2. **A `last_reviewed:` date that ages out.** "Is the map true?" cannot be settled
       by a script, so we do not pretend to. What a script *can* enforce is that a
       human or agent recently asserted it is true, and shout when nobody has.

    Freshness-vs-code is deliberately NOT inferred from mtimes: a git checkout rewrites
    them wholesale, as does any sync client or backup agent, so such a check would be
    confidently wrong. (The rule predates the move off OneDrive and survives it -- the
    premise was never specific to one sync client.)
    """
    result = CheckResult("architecture-map", "Architecture map is singular and current")
    config = load_knowledge_config(root)
    rel_map = str(config.get("architecture_map") or "_bmad-output/planning-artifacts/ARCHITECTURE.md")
    max_age_days = int(config.get("architecture_max_age_days") or 90)

    map_path = root / rel_map
    planning_dir = map_path.parent
    if not planning_dir.is_dir():
        result.skipped = True
        result.skip_reason = f"no planning-artifacts directory at {rel_path(planning_dir)}"
        return result

    if not map_path.is_file():
        result.add(
            SEVERITY_WARNING,
            "no architecture map - the map you read to orient before touching "
            "unfamiliar code does not exist",
            map_path,
        )
        return result

    # 1. Singular.
    for other in sorted(planning_dir.rglob("*")):
        if not other.is_file() or other == map_path:
            continue
        if other.suffix.lower() != ".md":
            continue
        if ARCHITECTURE_ALIAS_RE.search(other.name):
            result.add(
                SEVERITY_WARNING,
                f"a second architecture document - fold it into {map_path.name} and "
                "archive it; two maps that disagree are worse than none",
                other,
            )

    # 2. Demonstrably alive.
    text = read_text(map_path)
    match = LAST_REVIEWED_RE.search(text)
    if not match:
        result.add(
            SEVERITY_WARNING,
            "no `last_reviewed: YYYY-MM-DD` in the frontmatter - nothing asserts this "
            "map still matches reality",
            map_path,
        )
        return result

    try:
        reviewed = datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        result.add(SEVERITY_WARNING, f"last_reviewed '{match.group(1)}' is not a date", map_path)
        return result

    age = (datetime.now(UTC) - reviewed).days
    if age > max_age_days:
        result.add(
            SEVERITY_WARNING,
            f"last reviewed {age} days ago (budget {max_age_days}) - re-read it against "
            "the code and restamp, or it is stale by definition",
            map_path,
        )
    return result


def check_test_temp_root(root: Path) -> CheckResult:
    """Warn when the configured pytest temp root exceeds its ceiling (AGENTS 5.7).

    temp_and_disk_discipline S4c. This is the BACKSTOP, not the fix: S1 (session-scope
    fixtures that copy bulk data and are only read) is what actually stops the garbage
    being generated. This check is what tells you S1 has regressed.

    WARNING, never ERROR, and deliberately: an oversized temp root is a smell -- almost
    always a function-scoped fixture doing a `shutil.copytree` of a directory that has
    quietly grown -- not a broken build. It is also a PEAK-PER-RUN measure, since pytest
    clears an explicit `--basetemp` at session start.

    Scoped to EXACTLY the configured path. A sweep that guesses at "some temp dir"
    eventually deletes something it should not, so an unset `testing.temp_root` skips
    rather than searching. A check that did not run is not a check that passed, so the
    skip is reported (AGENTS 6).
    """
    result = CheckResult("test-temp-root", "Test temp-root size ceiling")

    config_path = root / "config.yaml"
    testing_cfg: dict = {}
    if yaml is not None and config_path.is_file():
        try:
            data = yaml.safe_load(read_text(config_path))
        except yaml.YAMLError:
            data = None
        if isinstance(data, dict) and isinstance(data.get("testing"), dict):
            testing_cfg = data["testing"]

    temp_root_str = str(testing_cfg.get("temp_root") or "").strip()
    if not temp_root_str:
        result.skipped = True
        result.skip_reason = "testing.temp_root not configured in config.yaml"
        return result

    temp_root = Path(temp_root_str)
    if not temp_root.is_absolute():
        temp_root = root / temp_root
    try:
        if not temp_root.is_dir():
            result.skipped = True
            result.skip_reason = f"temp root does not exist at {temp_root_str} (nothing to measure)"
            return result
    except OSError as exc:  # dangling link / WinError 1920 -- is_dir() RAISES, AGENTS 5.5.1
        result.skipped = True
        result.skip_reason = f"could not stat temp root {temp_root_str}: {exc}"
        return result

    try:
        max_gb = float(testing_cfg.get("temp_root_max_gb", 2.0))
    except (TypeError, ValueError):
        max_gb = 2.0

    total = 0
    for path in temp_root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue  # a file vanishing mid-walk is normal in a temp tree
    used_gb = total / (1024 ** 3)
    if used_gb > max_gb:
        result.add(
            SEVERITY_WARNING,
            f"test temp root holds {used_gb:.2f} GB, over the {max_gb:.2f} GB ceiling "
            "(testing.temp_root_max_gb). Usually a function-scoped fixture copying bulk "
            "data per-test: session-scope any fixture that copies data it only READS",
            temp_root,
        )
    return result


def check_coverage_wiring(root: Path) -> CheckResult:
    """The branch-and-line coverage scaffolding must be wired in (AGENTS 5.7).

    This check enforces WIRING, never a coverage number: whether the config block,
    the gate script, the pyproject coverage config, and the tracked baseline all
    exist. Judging whether coverage is *sufficient* is coverage_gate.py's job (and,
    ultimately, 4.1's) -- a linter that asserted a percentage would be the vanity
    metric AGENTS 5.7 exists to avoid. All findings are WARNING: a fleet project that
    has not yet applied the pack is nudged, not CI-blocked.
    """
    result = CheckResult("coverage-wiring", "Branch-and-line coverage wiring")

    config_path = root / "config.yaml"
    coverage_cfg: dict = {}
    if yaml is not None and config_path.is_file():
        try:
            data = yaml.safe_load(read_text(config_path))
        except yaml.YAMLError:
            data = None
        if isinstance(data, dict):
            testing = data.get("testing")
            if isinstance(testing, dict) and isinstance(testing.get("coverage"), dict):
                coverage_cfg = testing["coverage"]

    if not coverage_cfg:
        result.add(
            SEVERITY_WARNING,
            "no testing.coverage block in config.yaml; the coverage gate (AGENTS 5.7) is not "
            "configured (apply the coverage_gate upgrade pack)",
            config_path,
        )
        return result

    gate = root / "scripts" / "utilities" / "coverage_gate.py"
    if not gate.is_file():
        result.add(SEVERITY_WARNING, "coverage_gate.py is missing from scripts/utilities", gate)

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = read_text(pyproject)
        if "[tool.coverage.run]" not in text:
            result.add(
                SEVERITY_WARNING,
                "pyproject.toml has no [tool.coverage.run] section; branch coverage is not enabled",
                pyproject,
            )
        if "pytest-cov" not in text:
            result.add(
                SEVERITY_WARNING,
                "pytest-cov is not a declared dependency; the coverage gate cannot generate a report",
                pyproject,
            )

    baseline_rel = coverage_cfg.get("baseline_file")
    if isinstance(baseline_rel, str) and baseline_rel.strip():
        baseline = root / baseline_rel
        if not baseline.is_file():
            result.add(
                SEVERITY_WARNING,
                f"testing.coverage.baseline_file -> '{baseline_rel}' does not exist (the ratchet "
                "floor is untracked)",
                baseline,
            )
    return result


def check_memory_cache(root: Path) -> CheckResult:
    """Run objective checks from memory_lint.py (schema, index-drift, size cap, authority existence)."""
    result = CheckResult("memory-cache", "Memory cache schema and integrity")

    try:
        from scripts.utilities import memory_lint
    except ImportError:
        try:
            import memory_lint
        except ImportError:
            result.skipped = True
            result.skip_reason = "could not import memory_lint.py helper"
            return result

    config = load_knowledge_config(root)
    mem_store = config.get("memory_store")
    if not mem_store:
        result.skipped = True
        result.skip_reason = "knowledge.memory_store not configured in config.yaml"
        return result

    memory_dir = root / mem_store if not Path(mem_store).is_absolute() else Path(mem_store)
    if not memory_dir.is_dir():
        result.skipped = True
        result.skip_reason = f"memory store directory not found at {rel_path(memory_dir)}"
        return result

    registry_str = config.get("skills_registry", ".agent/skills")
    registry = root / registry_str if not Path(registry_str).is_absolute() else Path(registry_str)
    max_bytes = int(config.get("memory_max_page_bytes", memory_lint.DEFAULT_MAX_PAGE_BYTES))

    # Run the checks
    lint_results = memory_lint.run_checks(
        repo_root=root,
        memory_dir=memory_dir,
        registry=registry,
        max_page_bytes=max_bytes,
        config=config
    )

    for lr in lint_results:
        # A SKIPPED sub-check is not a passing sub-check (AGENTS 5.5.1). memory_lint
        # prints its skip reasons when run directly, but forwarding only `findings`
        # discarded them here -- so a skills registry that no longer resolved showed up
        # as a clean PASS. That is exactly the false green the D:\Projects relocation
        # produced (AGENTS 6): the "does this page cite a real skill?" check had simply
        # stopped running, and nothing said so.
        if getattr(lr, "skipped", False):
            result.findings.append(Finding(
                check=f"memory-{lr.name}",
                severity=SEVERITY_WARNING,
                message=(
                    f"{lr.title}: SKIPPED -- {lr.skip_reason or 'no reason given'} "
                    "(a check that did not run is not a check that passed)"
                ),
                path=rel_path(memory_dir),
            ))
            continue
        for f in lr.findings:
            result.findings.append(Finding(
                check=f"memory-{lr.name}",
                severity=f.severity,
                message=f"{lr.title}: {f.message}",
                path=f.path
            ))

    return result


CHECKS: tuple[Callable[[Path], CheckResult], ...] = (
    # First on purpose: a repo whose guards cannot run should say so before it reports
    # anything else, because every check below it is advisory by comparison.
    check_hook_wiring,
    check_adr_register,
    check_upgrade_packs,
    check_absorbed_packs,
    check_sprint_status,
    check_dead_links,
    check_template_leakage,
    check_config_yaml,
    check_knowledge_paths,
    check_adr_references,
    check_prompt_archive,
    check_memory_inheritance_declared,
    check_architecture_map,
    check_loose_stale_files,
    check_script_encoding,
    check_windows_execution_traps,
    check_coverage_wiring,
    check_sprint_drift,
    check_story_lifecycle,
    check_frontend_testing,
    check_test_temp_root,
    check_memory_cache,
)


# ---------------------------------------------------------------------------
# Reporting and entry point
# ---------------------------------------------------------------------------


def run_checks(root: Path) -> list[CheckResult]:
    return [check(root) for check in CHECKS]


def print_human_report(results: list[CheckResult], strict: bool) -> None:
    print("Governance lint")
    print(f"Repo root: {REPO_ROOT}")
    print(f"Mode: {'strict (warnings fail)' if strict else 'standard'}")
    print()
    for result in results:
        error_count = sum(1 for f in result.findings if f.severity == SEVERITY_ERROR)
        warning_count = sum(1 for f in result.findings if f.severity == SEVERITY_WARNING)
        if result.skipped:
            status = "SKIP"
        elif error_count:
            status = "FAIL"
        elif warning_count:
            status = "WARN"
        else:
            status = "PASS"
        print(f"[{status}] {result.title} ({result.name})")
        if result.skipped and result.skip_reason:
            print(f"       skipped: {result.skip_reason}")
        for finding in result.findings:
            print(f"       {finding.severity}: {finding.message} [{finding.path}]")
    print()


def main(argv: list[str] | None = None) -> int:
    # Never let odd console encodings (Windows cp1252 pipes) crash the linter.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")

    parser = argparse.ArgumentParser(
        prog="governance_lint",
        description="Deterministic governance rule checker for this repository.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit findings as a machine-readable JSON list",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat WARNING findings as failures",
    )
    args = parser.parse_args(argv)

    results = run_checks(REPO_ROOT)
    findings = [finding for result in results for finding in result.findings]
    errors = [f for f in findings if f.severity == SEVERITY_ERROR]
    warnings = [f for f in findings if f.severity == SEVERITY_WARNING]

    failed = bool(errors) or (args.strict and bool(warnings))

    if args.as_json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        print_human_report(results, args.strict)
        print(f"Summary: {len(errors)} error(s), {len(warnings)} warning(s)")
        print(f"Result: {'FAIL' if failed else 'PASS'}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
