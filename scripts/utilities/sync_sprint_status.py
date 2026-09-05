r"""Derive sprint-status.yaml from on-disk story files instead of trusting agents.

``_bmad-output/implementation-artifacts/sprint-status.yaml`` is a registry of
epic/story statuses. Historically agents were trusted to keep it in sync with
the ``*.story.md`` files and this leaked. This utility makes the story files
the single source of truth:

* Story files are named ``<epic>-<story>-<slug>.story.md`` and carry a
  ``Status: <value>`` line near the top (some legacy files omit it; those are
  flagged and assumed ``ready-for-dev`` since the file exists on disk).
* ``sync``  regenerates sprint-status.yaml: correct project name from
  ``_bmad/config.toml`` (core.project_name), fresh ``last_updated``, one entry
  per story file found. Files on disk that are unregistered, and registry
  entries whose files are missing, are flagged. Epic entries are RE-DERIVED
  every run from the stories plus the epics document's roster (changes are
  flagged as drift); only retrospective entries are preserved as-is, having
  no derivation source.
* ``check`` exits 1 (printing the drift) if the current file disagrees with
  disk; designed to be called by governance lint / CI.

Exit codes:
    0  success / no drift
    1  error, or (for check) drift detected
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

import yaml

STORY_FILE_RE: re.Pattern[str] = re.compile(
    r"^(?P<epic>\d+)-(?P<story>\d+)-(?P<slug>.+)\.story\.md$"
)
# Matches "Status: done", "**Status:** done", etc. at the start of a line.
STATUS_LINE_RE: re.Pattern[str] = re.compile(
    r"^\*{0,2}Status\*{0,2}\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
# A story heading in the epics document: "### Story 1.2: <title>" (three or four
# hashes -- both depths occur in real epics documents; NEVER widen to #{3,}, which
# would also match deeper headings that are not stories).
EPIC_ROSTER_RE: re.Pattern[str] = re.compile(
    r"^#{3,4}\s+Story\s+(?P<epic>\d+)[.-](?P<story>\d+)\s*:", re.MULTILINE
)
EPIC_KEY_RE: re.Pattern[str] = re.compile(r"^epic-(?P<epic>\d+)$")
RETRO_KEY_RE: re.Pattern[str] = re.compile(r"^epic-(?P<epic>\d+)-retrospective$")
STORY_KEY_RE: re.Pattern[str] = re.compile(r"^\d+-\d+-.+$")

VALID_STATUSES: tuple[str, ...] = ("backlog", "ready-for-dev", "in-progress", "review", "done")
DEFAULT_STATUS: str = "ready-for-dev"

STATUS_DEFINITIONS_BLOCK: str = """# STATUS DEFINITIONS:
# ==================
# Epic Status:
#   - backlog: Epic not yet started
#   - in-progress: Epic actively being worked on
#   - done: All stories in epic completed
#
# Story Status:
#   - backlog: Story only exists in epic file
#   - ready-for-dev: Story file created in stories folder
#   - in-progress: Developer actively working on implementation
#   - review: Ready for code review (via Dev's code-review workflow)
#   - done: Story completed
"""


class StoryInfo(NamedTuple):
    """A story file discovered on disk."""

    key: str
    epic: int
    story: int
    status: str
    status_missing: bool
    path: Path


def get_project_root() -> Path:
    """Return the absolute path of the project root (repo root)."""
    return Path(__file__).resolve().parent.parent.parent


def artifacts_dir(root: Path) -> Path:
    """Return the implementation artifacts directory."""
    return root / "_bmad-output" / "implementation-artifacts"


def read_project_name(root: Path) -> str | None:
    """Read core.project_name from _bmad/config.toml, or None on any failure."""
    config_path = root / "_bmad" / "config.toml"
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        name = config.get("core", {}).get("project_name")
        return name if isinstance(name, str) else None
    except (OSError, tomllib.TOMLDecodeError):
        return None


def parse_story_status(text: str) -> str | None:
    """Extract the story status from file content; None if no Status line."""
    match = STATUS_LINE_RE.search(text)
    if not match:
        return None
    value = match.group("value").strip().strip("`*").strip()
    return value.lower()


def collect_stories(directory: Path) -> tuple[list[StoryInfo], list[str]]:
    """Scan *.story.md files. Returns (stories, warnings)."""
    stories: list[StoryInfo] = []
    warnings: list[str] = []
    if not directory.is_dir():
        warnings.append(f"Artifacts directory not found: {directory}")
        return stories, warnings

    for path in sorted(directory.glob("*.story.md"), key=lambda p: p.name.lower()):
        match = STORY_FILE_RE.match(path.name)
        if not match:
            warnings.append(
                f"Story file does not match <epic>-<story>-<slug>.story.md: {path.name}"
            )
            continue
        text = path.read_text(encoding="utf-8")
        status = parse_story_status(text)
        status_missing = status is None
        if status_missing:
            status = DEFAULT_STATUS
            warnings.append(
                f"No 'Status:' field in {path.name}; assuming '{DEFAULT_STATUS}'."
            )
        elif status not in VALID_STATUSES:
            warnings.append(
                f"Unrecognised status '{status}' in {path.name} "
                f"(expected one of: {', '.join(VALID_STATUSES)})."
            )
        key = path.name[: -len(".story.md")]
        stories.append(
            StoryInfo(
                key=key,
                epic=int(match.group("epic")),
                story=int(match.group("story")),
                status=str(status),
                status_missing=status_missing,
                path=path,
            )
        )
    stories.sort(key=lambda s: (s.epic, s.story, s.key))
    return stories, warnings


def load_registry(path: Path) -> dict[str, Any] | None:
    """Load the current sprint-status.yaml, or None if missing/unreadable."""
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def format_timestamp(value: Any) -> str:
    """Render a timestamp value as ISO-8601 Zulu (matching the existing file)."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def utc_now_stamp() -> str:
    """Fresh UTC timestamp in the file's ISO-8601 Zulu format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def epic_roster(root: Path) -> tuple[dict[int, int], str | None]:
    """How many stories each epic is SUPPOSED to have, read from the epics document.

    Returns (roster, reason_it_is_empty). The reason distinguishes three states a
    silent {} would conflate: no epics document at all, more than one (ambiguous --
    guessing between two rosters could bless the wrong one), and a document with no
    Story headings the pattern recognises.
    """
    directory = root / "_bmad-output" / "planning-artifacts"
    candidates = sorted(directory.glob("*epic*.md")) if directory.is_dir() else []
    if not candidates:
        return {}, "no epics document under _bmad-output/planning-artifacts/"
    if len(candidates) > 1:
        names = ", ".join(p.name for p in candidates)
        return {}, f"more than one epics document ({names}); roster ambiguous"
    try:
        text = candidates[0].read_text(encoding="utf-8")
    except OSError as exc:
        return {}, f"cannot read {candidates[0].name}: {exc}"
    roster: dict[int, int] = {}
    for match in EPIC_ROSTER_RE.finditer(text):
        epic = int(match.group("epic"))
        roster[epic] = roster.get(epic, 0) + 1
    if not roster:
        return {}, f"{candidates[0].name} contains no 'Story N.M:' headings"
    return roster, None


def derive_epic_status(story_statuses: list[str], roster_size: int | None = None) -> str:
    """Derive an epic status from its stories.

    *roster_size* is how many stories the epic is SUPPOSED to have (from the epics
    document). Without it, an epic whose first two stories are done reads as done --
    a story FILE only exists once someone has written that story, so deriving from
    files alone marks an epic complete while most of its planned stories are
    unwritten. Unwritten stories are unstarted work, not absent work. None keeps
    the old behaviour for callers with no roster.
    """
    if roster_size is not None and len(story_statuses) < roster_size:
        return "in-progress" if any(s != "backlog" for s in story_statuses) else "backlog"
    if story_statuses and all(s == "done" for s in story_statuses):
        return "done"
    if any(s != "backlog" for s in story_statuses):
        return "in-progress"
    return "backlog"


def build_development_status(
    stories: list[StoryInfo], existing: dict[str, Any], roster: dict[int, int] | None = None,
    roster_problem: str | None = None,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Merge disk reality with the existing registry.

    Returns (ordered key/status pairs, drift/flag messages). Story entries come
    from disk; retrospective entries are preserved (no on-disk counterpart);
    registry story entries with no file are flagged and dropped; unknown keys are
    preserved at the end.

    Epic entries are RE-DERIVED every run, never preserved: the old
    preserve-existing branch latched an epic's value forever, so an epic marked
    done after its first stories could never be corrected -- and hand-editing
    generated output is forbidden, so nothing could fix it. Stacked with
    derive-from-files (see derive_epic_status), an epic went done at two of ten
    stories and stayed there. A changed value is reported as drift, loudly.
    """
    flags: list[str] = []
    if roster is None and roster_problem:
        # A silent fallback to the old files-only derivation is exactly the
        # AGENTS 5.5.1 shape; say what is missing and why it matters.
        flags.append(
            f"Epic roster unavailable ({roster_problem}); epic statuses derived from "
            "story FILES alone, which cannot see unwritten stories."
        )
    roster = roster or {}
    stories_by_epic: dict[int, list[StoryInfo]] = {}
    for story in stories:
        stories_by_epic.setdefault(story.epic, []).append(story)

    existing_epics: dict[int, str] = {}
    existing_retros: dict[int, str] = {}
    existing_stories: dict[str, str] = {}
    extras: list[tuple[str, str]] = []
    for key, value in existing.items():
        key_str = str(key)
        value_str = str(value)
        epic_match = EPIC_KEY_RE.match(key_str)
        retro_match = RETRO_KEY_RE.match(key_str)
        if epic_match:
            existing_epics[int(epic_match.group("epic"))] = value_str
        elif retro_match:
            existing_retros[int(retro_match.group("epic"))] = value_str
        elif STORY_KEY_RE.match(key_str):
            existing_stories[key_str] = value_str
        else:
            extras.append((key_str, value_str))
            flags.append(f"Preserving unrecognised registry entry: {key_str}: {value_str}")

    disk_keys = {s.key for s in stories}
    for key in existing_stories:
        if key not in disk_keys:
            flags.append(f"Registry entry has no story file on disk (dropped): {key}")
    for story in stories:
        if story.key not in existing_stories:
            flags.append(
                f"Story file on disk was unregistered (added): {story.key} = {story.status}"
            )
        elif existing_stories[story.key] != story.status:
            flags.append(
                f"Status drift for {story.key}: registry '{existing_stories[story.key]}' "
                f"-> disk '{story.status}'"
            )

    ordered: list[tuple[str, str]] = []
    all_epics = sorted(set(stories_by_epic) | set(existing_epics) | set(existing_retros))
    for epic in all_epics:
        epic_stories = stories_by_epic.get(epic, [])
        roster_size = roster.get(epic)
        if roster_size is not None and len(epic_stories) > roster_size:
            flags.append(
                f"epic-{epic} has {len(epic_stories)} story file(s) but the epics document "
                f"lists only {roster_size} -- the roster is behind, or a story is misfiled."
            )
        derived = derive_epic_status([s.status for s in epic_stories], roster_size)
        previous = existing_epics.get(epic)
        if previous is None:
            flags.append(f"New epic entry derived from its stories: epic-{epic} = {derived}")
        elif previous != derived:
            flags.append(
                f"Epic status drift: epic-{epic} registry '{previous}' -> derived '{derived}' "
                "(epics re-derive every run; the old latching behaviour preserved a wrong "
                "value forever)."
            )
        ordered.append((f"epic-{epic}", derived))
        for story in epic_stories:
            ordered.append((story.key, story.status))
        if epic in existing_retros:
            ordered.append((f"epic-{epic}-retrospective", existing_retros[epic]))
    ordered.extend(extras)
    return ordered, flags


def yaml_scalar(value: str) -> str:
    """Render a string as a YAML scalar, quoting only when needed."""
    if re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_ ./\-]*", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_sprint_status(
    project: str,
    project_key: str,
    tracking_system: str,
    story_location: str,
    generated: str,
    last_updated: str,
    development_status: list[tuple[str, str]],
) -> str:
    """Render the full sprint-status.yaml content, preserving the file's schema."""
    scalars = (
        f"generated: {generated}\n"
        f"last_updated: {last_updated}\n"
        f"project: {yaml_scalar(project)}\n"
        f"project_key: {yaml_scalar(project_key)}\n"
        f"tracking_system: {yaml_scalar(tracking_system)}\n"
        f"story_location: {yaml_scalar(story_location)}\n"
    )
    comment_mirror = "".join(f"# {line}\n" for line in scalars.rstrip("\n").split("\n"))
    if development_status:
        body = "development_status:\n"
        for key, status in development_status:
            body += f"  {key}: {status}\n"
    else:
        # A registry with no rows is the CORRECT state for a freshly bootstrapped
        # project, so it must still parse back as a mapping. A bare
        # ``development_status:`` parses to ``None``, forcing every reader to
        # special-case a second spelling of "empty"; ``{}`` round-trips to the same
        # type ``load_registry`` hands back for a populated file, and matches the
        # literal bootstrap_project.ps1 writes for a new clone.
        body = "development_status: {}\n"
    return f"{comment_mirror}\n{STATUS_DEFINITIONS_BLOCK}\n{scalars}\n{body}"


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


def cmd_sync(args: argparse.Namespace) -> int:
    """Regenerate sprint-status.yaml from the story files on disk."""
    root = get_project_root()
    directory = artifacts_dir(root)
    status_path = directory / "sprint-status.yaml"

    stories, warnings = collect_stories(directory)
    for warning in warnings:
        print(f"[WARN] {warning}")

    registry = load_registry(status_path)
    if registry is None and status_path.is_file():
        print(f"[WARN] Could not parse existing {status_path.name}; regenerating from scratch.")
    registry = registry or {}
    existing_ds = registry.get("development_status")
    if not isinstance(existing_ds, dict):
        existing_ds = {}

    project = read_project_name(root)
    if project is None:
        project = str(registry.get("project", "UNKNOWN"))
        print(
            "[WARN] Could not read core.project_name from _bmad/config.toml; "
            f"keeping '{project}'."
        )

    now = utc_now_stamp()
    generated = format_timestamp(registry.get("generated", now))
    project_key = str(registry.get("project_key", "NOKEY"))
    tracking_system = str(registry.get("tracking_system", "file-system"))
    story_location = str(
        registry.get("story_location", "_bmad-output/implementation-artifacts")
    )

    roster, roster_problem = epic_roster(root)
    development_status, flags = build_development_status(
        stories, existing_ds, roster or None, roster_problem
    )
    for flag in flags:
        print(f"[INFO] {flag}")

    old_project = registry.get("project")
    if old_project is not None and str(old_project) != project:
        print(f"[INFO] Project name corrected: '{old_project}' -> '{project}'")

    content = render_sprint_status(
        project=project,
        project_key=project_key,
        tracking_system=tracking_system,
        story_location=story_location,
        generated=generated,
        last_updated=now,
        development_status=development_status,
    )

    print(
        f"Registry: {len(stories)} story file(s) on disk, "
        f"{len(development_status)} development_status entries."
    )
    if args.dry_run:
        print(f"[DRY-RUN] Would write {status_path}:")
        print("-" * 60)
        print(content.rstrip("\n"))
        print("-" * 60)
        return 0

    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(content, encoding="utf-8", newline="\n")
    print(f"[OK] Wrote {status_path}")
    return 0


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


def cmd_check(_args: argparse.Namespace) -> int:
    """Exit 1 if sprint-status.yaml disagrees with disk, printing the drift."""
    root = get_project_root()
    directory = artifacts_dir(root)
    status_path = directory / "sprint-status.yaml"

    drift: list[str] = []
    stories, warnings = collect_stories(directory)
    for warning in warnings:
        print(f"[WARN] {warning}")

    registry = load_registry(status_path)
    if registry is None:
        print(f"[DRIFT] Missing or unparseable registry: {status_path}")
        print("[FAIL] sprint-status.yaml disagrees with disk (1 issue).")
        return 1

    project = read_project_name(root)
    registry_project = str(registry.get("project", ""))
    if project is not None and registry_project != project:
        drift.append(
            f"Project name is '{registry_project}' but _bmad/config.toml "
            f"core.project_name is '{project}' (placeholder/stale)."
        )
    elif project is None:
        print("[WARN] Could not read core.project_name from _bmad/config.toml; skipping name check.")

    existing_ds = registry.get("development_status")
    if not isinstance(existing_ds, dict):
        existing_ds = {}
    registry_stories: dict[str, str] = {
        str(k): str(v) for k, v in existing_ds.items() if STORY_KEY_RE.match(str(k))
    }

    for story in stories:
        if story.key not in registry_stories:
            drift.append(f"Story on disk but not in registry: {story.key} ({story.status})")
        elif registry_stories[story.key] != story.status:
            suffix = " [no Status field in file; assumed]" if story.status_missing else ""
            drift.append(
                f"Stale status for {story.key}: registry '{registry_stories[story.key]}' "
                f"vs disk '{story.status}'{suffix}"
            )
    disk_keys = {s.key for s in stories}
    for key in sorted(registry_stories):
        if key not in disk_keys:
            drift.append(f"Registry story entry has no file on disk: {key}")

    # Epic rows drift too, now that they re-derive (2026-08-29): a stale epic value
    # used to pass `check` forever because only STORY_KEY_RE rows were compared, so
    # the CI-enforced arm blessed exactly the value `sync` would correct. Compare
    # each epic row against the same derivation sync uses.
    roster, _roster_problem = epic_roster(root)
    stories_by_epic: dict[int, list[str]] = {}
    for story in stories:
        stories_by_epic.setdefault(story.epic, []).append(story.status)
    for key, value in existing_ds.items():
        epic_match = EPIC_KEY_RE.match(str(key))
        if not epic_match:
            continue
        epic = int(epic_match.group("epic"))
        derived = derive_epic_status(stories_by_epic.get(epic, []), roster.get(epic))
        if str(value) != derived:
            drift.append(
                f"Stale epic status for {key}: registry '{value}' vs derived '{derived}'"
            )

    if drift:
        for line in drift:
            print(f"[DRIFT] {line}")
        print(f"[FAIL] sprint-status.yaml disagrees with disk ({len(drift)} issue(s)).")
        print("Run: python scripts/utilities/sync_sprint_status.py sync")
        return 1

    print("[OK] sprint-status.yaml matches the story files on disk.")
    return 0


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Derive sprint-status.yaml from on-disk story files."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser(
        "sync", help="Regenerate sprint-status.yaml from *.story.md files."
    )
    sync_parser.add_argument(
        "--dry-run", action="store_true", help="Print the would-be file without writing."
    )

    subparsers.add_parser(
        "check", help="Exit 1 if sprint-status.yaml disagrees with disk (for CI/lint)."
    )

    args = parser.parse_args()
    handlers = {"sync": cmd_sync, "check": cmd_check}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
