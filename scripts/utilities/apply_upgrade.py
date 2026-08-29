r"""Deterministic lifecycle utility for upgrade instruction packs.

Upgrade packs are markdown files (``upgrade_instructions_*.md`` or
``*_setup_guide_*.md``) that live in ``docs/upgrades/``. The master template
disseminates them to sibling projects; receiving projects apply them and then
run the closing action here, which deterministically records the pack in
``docs/upgrades/upgrades_ledger.md``, deletes the pack file, and stages both
paths with git. Previously these closing actions were trusted to agents and
leaked; this script makes them atomic and repeatable.

Subcommands:
    list          Show packs present in docs/upgrades/ and their ledger state.
    record        Closing action: ledger row + pack deletion + git add
                  (atomic; rolls back on any failure). In the MASTER TEMPLATE the
                  pack is RETAINED, not deleted -- docs/upgrades/ is the canonical
                  library and removal is `prune`'s job (--delete-pack overrides).
    disseminate   Template-only: copy new packs to sibling fleet projects.
    prune         Template-only: delete packs from the live library once EVERY
                  fleet project's ledger records them (git history keeps the
                  file; the template ledger gets a Pruned row).

Fleet discovery is POSITIONAL -- immediate siblings of the project root. Relocating
the template therefore changes which fleet it can see, so `disseminate` and `prune`
refuse to act on a fleet smaller than `fleet.expected_min_projects` in config.yaml
(AGENTS 5.5.1). A discovery of zero is an error, never a quiet success.

Exit codes:
    0  success
    1  error (bad arguments, failed step after rollback, aborted by user)
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - degraded mode when pyyaml is absent
    yaml = None  # type: ignore[assignment]

# Filename patterns that identify a disseminatable upgrade pack.
PACK_PATTERNS: tuple[str, ...] = ("upgrade_instructions_*.md", "*_setup_guide_*.md")

# Permanent reference docs that must never be treated as packs (lowercase).
PERMANENT_DOCS: frozenset[str] = frozenset(
    {
        "upgrades_ledger.md",
        "archiving_instructions.md",
        "cross_project_optimization_guide.md",
        "global_hermes_skill_candidates.md",
    }
)

LEDGER_NAME: str = "upgrades_ledger.md"

LEDGER_HEADER: str = (
    "# Project Upgrades Ledger\n"
    "\n"
    "This ledger tracks all master template upgrade instructions that have "
    "been generated and/or applied to this project. Execution agents MUST "
    "append a new row to this table upon successfully completing an upgrade "
    "instruction set.\n"
    "\n"
    "| Date | Upgrade File | Status | Notes |\n"
    "| :--- | :--- | :--- | :--- |\n"
)

TEMPLATE_PROJECT_NAME: str = "_NEON dev stack"

# Trailing timestamp convention in pack filenames, e.g. _260629_2317.md
STAMP_RE: re.Pattern[str] = re.compile(r"_(\d{6})_(\d{4})\.md$")


def get_project_root() -> Path:
    """Return the absolute path of the project root (repo root)."""
    return Path(__file__).resolve().parent.parent.parent


def upgrades_dir(root: Path) -> Path:
    """Return the docs/upgrades directory for a given project root."""
    return root / "docs" / "upgrades"


def is_pack(filename: str) -> bool:
    """Return True iff *filename* is an upgrade pack by naming convention."""
    lower = filename.lower()
    if lower in PERMANENT_DOCS:
        return False
    return any(fnmatch.fnmatchcase(lower, pattern) for pattern in PACK_PATTERNS)


def find_packs(directory: Path) -> list[Path]:
    """Return sorted list of pack files present in *directory*."""
    if not directory.is_dir():
        return []
    return sorted(
        (p for p in directory.iterdir() if p.is_file() and is_pack(p.name)),
        key=lambda p: p.name.lower(),
    )


def read_ledger_text(directory: Path) -> str | None:
    """Return ledger file content for *directory*, or None if it is missing."""
    ledger = directory / LEDGER_NAME
    if not ledger.is_file():
        return None
    return ledger.read_text(encoding="utf-8")


#: 0-based index of the "Upgrade File" cell in a ledger table row
#: (`| Date | Upgrade File | Status | Notes |`).
LEDGER_FILE_COLUMN: int = 1


def ledger_table_rows(ledger_text: str | None) -> list[list[str]]:
    """Split the ledger into table rows, each a list of stripped cell strings.

    Header and divider rows (cells made of `-` and `:`) are excluded, so callers
    see only data rows.
    """
    rows: list[list[str]] = []
    if not ledger_text:
        return rows
    for line in ledger_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(cell and set(cell) <= set(":- ") for cell in cells):
            continue  # divider row
        rows.append(cells)
    return rows


def ledger_contains(ledger_text: str | None, filename: str) -> bool:
    """True iff some row RECORDS *filename* in its Upgrade File cell.

    Equality on the cell (backticks stripped) -- never `in` on the file text, and
    never `in` on the cell. A row whose free-text Notes merely MENTION a pack
    ("superseded by `upgrade_instructions_X.md`") is an ordinary, correct thing to
    write, and under the old whole-file substring match it made `record` take the
    idempotent path: pack deleted, no row written, two reassuring [OK] lines. The
    same match drove `prune` (which deletes across the fleet) and `disseminate`
    (which would skip delivering to a project that had only ever mentioned the
    name). AGENTS 6 makes the ledger row the definition of "applied"; only a row
    can say a pack was applied.
    """
    for cells in ledger_table_rows(ledger_text):
        if len(cells) > LEDGER_FILE_COLUMN and cells[LEDGER_FILE_COLUMN].strip("`") == filename:
            return True
    return False


def pack_timestamp(path: Path) -> str:
    """Human-readable timestamp for a pack: filename stamp, else file mtime."""
    match = STAMP_RE.search(path.name)
    if match:
        d, t = match.group(1), match.group(2)
        return f"20{d[0:2]}-{d[2:4]}-{d[4:6]} {t[0:2]}:{t[2:4]}"
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return mtime.strftime("%Y-%m-%d %H:%M") + " (mtime)"


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a simple ASCII table."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    sep = "+".join("-" * (w + 2) for w in widths)
    sep = f"+{sep}+"
    header_line = "|" + "|".join(f" {h.ljust(w)} " for h, w in zip(headers, widths)) + "|"
    print(sep)
    print(header_line)
    print(sep)
    for row in rows:
        print("|" + "|".join(f" {c.ljust(w)} " for c, w in zip(row, widths)) + "|")
    print(sep)


def confirm(prompt: str) -> bool:
    """Interactive y/N confirmation. Returns True iff the user accepted."""
    response = input(f"{prompt} (y/N): ")
    return response.strip().lower().startswith("y")


def run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess:
    """Run a git command in *root* capturing output; never raises on rc != 0."""
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        check=False,
        capture_output=True,
        # Explicit codec, never text=True: text=True decodes with the locale codec (cp1252
        # on Windows, where five byte values are undefined), and it decodes BOTH streams
        # whether or not a caller reads them -- so a repository path or git message outside
        # cp1252 breaks this call. It does NOT raise here, which is the part worth knowing:
        # under capture_output the pipes are read on reader threads, the decode error is
        # raised in a thread and swallowed, and this returns a CompletedProcess whose
        # .stdout and .stderr are both None. The failure then lands on whichever caller
        # first touches them, wearing a TypeError that names nothing (AGENTS 5.5.1).
        encoding="utf-8",
        errors="replace",
    )


def git_path_is_ignored(root: Path, rel_path: str) -> bool:
    """Return True iff git reports *rel_path* as ignored."""
    result = run_git(root, ["check-ignore", "-q", rel_path])
    return result.returncode == 0


def git_path_is_tracked(root: Path, rel_path: str) -> bool:
    """Return True iff *rel_path* is tracked by git."""
    result = run_git(root, ["ls-files", "--error-unmatch", "--", rel_path])
    return result.returncode == 0


def stage_paths(root: Path, rel_paths: list[str]) -> None:
    """git add the given paths (relative to *root*). Raises RuntimeError on failure."""
    to_add = [p for p in rel_paths if not git_path_is_ignored(root, p)]
    if not to_add:
        print("[OK] Nothing to stage (all paths gitignored).")
        return
    result = run_git(root, ["add", "--", *to_add])
    if result.returncode != 0:
        raise RuntimeError(
            f"git add failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    print(f"[OK] Staged via git add: {', '.join(to_add)}")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def cmd_list(_args: argparse.Namespace) -> int:
    """Show packs in docs/upgrades/ with timestamps and ledger state."""
    root = get_project_root()
    directory = upgrades_dir(root)
    if not directory.is_dir():
        print(f"[ERROR] Upgrades directory not found: {directory}")
        return 1

    packs = find_packs(directory)
    ledger_text = read_ledger_text(directory)
    if ledger_text is None:
        print(f"[WARN] No ledger found at docs/upgrades/{LEDGER_NAME}")

    # Report the SUBJECT SET, not just the matches. `is_pack()` is a naming filter,
    # and a real delivered pack with a nonconforming name simply does not exist to
    # this command -- the origin project held one for weeks with no ledger row under
    # any spelling, and `list` printed the same clean bill it prints for an empty
    # directory. A count of zero is only meaningful beside the count examined.
    all_md = sorted(
        p for p in directory.glob("*.md") if p.is_file() and p.name != LEDGER_NAME
    )
    unrecognised = [p.name for p in all_md if not is_pack(p.name)]
    print(
        f"Examined {len(all_md)} .md file(s) in docs/upgrades/ "
        f"({len(packs)} recognised as packs, {len(unrecognised)} not)."
    )
    for name in unrecognised:
        print(
            f"  [UNRECOGNISED] {name} - does not match PACK_PATTERNS, so record/"
            "disseminate/prune cannot see it. Rename it or archive it; do not leave it invisible."
        )

    if not packs:
        print("[OK] No upgrade packs present in docs/upgrades/.")
        return 0

    rows: list[list[str]] = []
    for pack in packs:
        recorded = "recorded" if ledger_contains(ledger_text, pack.name) else "NOT recorded"
        rows.append([pack.name, pack_timestamp(pack), recorded])

    print(f"Upgrade packs in {directory}:")
    print_table(["Pack File", "Timestamp", "Ledger"], rows)
    return 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


def sanitize_notes(notes: str) -> str:
    """Make free-text notes safe for a single markdown table cell."""
    return notes.replace("\r", " ").replace("\n", " ").replace("|", "/").strip()


def build_ledger_row(filename: str, status: str, notes: str) -> str:
    """Return a ledger table row matching the existing table format."""
    date = datetime.now().strftime("%Y-%m-%d")
    return f"| {date} | `{filename}` | {status.capitalize()} | {sanitize_notes(notes)} |"


def append_ledger_row(ledger_path: Path, existing_text: str | None, row: str) -> None:
    """Write the ledger with *row* inserted INSIDE the table; creates it if missing.

    "Append to the end of the file" and "append to the table" are the same thing
    only while the table happens to be the last thing in the file. A ledger with a
    trailing prose section would gain a line markdown renders as TEXT, not a row --
    reported [OK], invisible to `ledger_contains`, pack deleted anyway. Insert
    after the last actual table row; start a table when there is none.
    """
    if existing_text is None:
        new_text = LEDGER_HEADER + row + "\n"
    else:
        lines = existing_text.rstrip("\n").split("\n")
        last_row_index = -1
        for index, line in enumerate(lines):
            if line.strip().startswith("|"):
                last_row_index = index
        if last_row_index == -1:
            # No table anywhere: start one at the end so the row is a real row.
            header_lines = LEDGER_HEADER.strip("\n").split("\n")
            lines.extend(["", header_lines[-2], header_lines[-1], row])
        else:
            lines.insert(last_row_index + 1, row)
        new_text = "\n".join(lines) + "\n"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(new_text, encoding="utf-8")


def cmd_record(args: argparse.Namespace) -> int:
    """Closing action: ledger row + pack deletion + git add, atomically."""
    root = get_project_root()
    directory = upgrades_dir(root)
    filename: str = args.pack_filename

    if Path(filename).name != filename:
        print(f"[ERROR] Expected a bare filename, not a path: {filename}")
        return 1
    if filename.lower() in PERMANENT_DOCS:
        print(f"[ERROR] Refusing to record a permanent reference doc: {filename}")
        return 1
    if not filename.lower().endswith(".md"):
        print(f"[ERROR] Upgrade packs are markdown files (*.md): {filename}")
        return 1

    pack_path = directory / filename
    if not pack_path.is_file():
        print(f"[ERROR] Pack file not present, refusing to record: {pack_path}")
        return 1
    if not is_pack(filename):
        print(f"[WARN] '{filename}' does not match standard pack naming patterns; proceeding anyway.")

    ledger_path = directory / LEDGER_NAME
    original_ledger = read_ledger_text(directory)
    already_recorded = ledger_contains(original_ledger, filename)
    row = build_ledger_row(filename, args.status, args.notes)

    rel_ledger = ledger_path.relative_to(root).as_posix()
    rel_pack = pack_path.relative_to(root).as_posix()

    # In the MASTER TEMPLATE, docs/upgrades/ IS the canonical pack library: a pack lives
    # there until `prune` confirms every fleet ledger has recorded it. Deleting it here
    # would destroy the only copy before the fleet ever received it -- which is exactly
    # what the location-migration pack's own closing step would have done.
    # `disseminate` and `prune` already refuse to run outside the template; `record` had
    # no such guard, so the safe behaviour is the default and deletion is opt-in.
    is_template = read_project_name(root) == TEMPLATE_PROJECT_NAME
    retain_pack = is_template and not args.delete_pack

    print(f"Closing action for pack: {filename}")
    if already_recorded:
        print(f"  1. Ledger row: SKIP (already referenced in {LEDGER_NAME})")
    elif original_ledger is None:
        print(f"  1. Create {rel_ledger} with header and row: {row}")
    else:
        print(f"  1. Append to {rel_ledger}: {row}")
    if retain_pack:
        print(
            f"  2. RETAIN {rel_pack} -- this is the master template's canonical library copy; "
            "removing it is `prune`'s job, once every fleet ledger records it. "
            "Pass --delete-pack to override."
        )
        print(f"  3. git add {rel_ledger}")
    else:
        print(f"  2. Delete {rel_pack}")
        print(f"  3. git add {rel_ledger} {rel_pack}")

    if args.dry_run:
        print("[DRY-RUN] No changes made.")
        return 0

    if not args.yes and not confirm("Proceed?"):
        print("Aborting.")
        return 1

    pack_bytes = pack_path.read_bytes()
    pack_was_tracked = git_path_is_tracked(root, rel_pack)
    ledger_written = False
    pack_deleted = False
    try:
        if not already_recorded:
            append_ledger_row(ledger_path, original_ledger, row)
            ledger_written = True
            print(f"[OK] Ledger row appended to {rel_ledger}")
        else:
            print("[OK] Ledger row already present; not duplicating.")

        stage_targets = [rel_ledger]
        if retain_pack:
            print(f"[OK] Retained {rel_pack} (master template canonical library copy)")
        else:
            pack_path.unlink()
            pack_deleted = True
            print(f"[OK] Deleted {rel_pack}")
            if pack_was_tracked:
                stage_targets.append(rel_pack)
        stage_paths(root, stage_targets)
    except Exception as exc:  # noqa: BLE001 - roll back on any failure
        print(f"[ERROR] {exc}")
        if pack_deleted:
            try:
                pack_path.write_bytes(pack_bytes)
                print(f"[ROLLBACK] Restored {rel_pack}")
            except OSError as restore_exc:
                print(f"[ROLLBACK-FAILED] Could not restore {rel_pack}: {restore_exc}")
        if ledger_written:
            try:
                if original_ledger is None:
                    ledger_path.unlink()
                    print(f"[ROLLBACK] Removed newly-created {rel_ledger}")
                else:
                    ledger_path.write_text(original_ledger, encoding="utf-8")
                    print(f"[ROLLBACK] Restored {rel_ledger}")
            except OSError as restore_exc:
                print(f"[ROLLBACK-FAILED] Could not restore {rel_ledger}: {restore_exc}")
        return 1

    print(f"[OK] Pack '{filename}' recorded and closed out.")
    return 0


# ---------------------------------------------------------------------------
# disseminate
# ---------------------------------------------------------------------------


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


def read_expected_min_projects(root: Path) -> int | None:
    """`fleet.expected_min_projects` from config.yaml; None if it cannot be determined.

    Fleet discovery is POSITIONAL (siblings of the project root), so the answer to
    "how big is the fleet?" silently changes when the template moves. The
    D:\\Projects relocation left the template with zero discovered siblings, which made
    `disseminate` a no-op that exited 0 and would have made `prune` delete packs the
    fleet never received as soon as one project moved in beside it.

    None means "cannot evaluate the guard" and is reported, never silently ignored.
    """
    config_path = root / "config.yaml"
    if yaml is None or not config_path.is_file():
        return None
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    section = data.get("fleet")
    if not isinstance(section, dict):
        return None
    value = section.get("expected_min_projects")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def assert_fleet_is_whole(root: Path, projects: list[Path], command: str) -> int:
    """Refuse a fleet-wide command when discovery found fewer projects than expected.

    Returns 0 to proceed, 1 to abort. A split fleet is the dangerous state: half the
    projects are invisible, so `disseminate` reaches nobody and `prune` reads
    "absorbed by all N" against a denominator that is simply wrong.
    """
    expected = read_expected_min_projects(root)
    if expected is None:
        print(
            "[WARN] fleet.expected_min_projects is not configured (or pyyaml is missing); "
            "the split-fleet guard is INACTIVE. Verify the discovered list below by hand."
        )
        return 0
    if expected == 0:
        return 0
    if len(projects) >= expected:
        return 0
    print(
        f"[ERROR] Split fleet: {command} discovered {len(projects)} project(s) but "
        f"fleet.expected_min_projects is {expected}.\n"
        f"        Fleet discovery is positional -- only immediate siblings of "
        f"{root.parent} are visible.\n"
        f"        Projects living elsewhere would be silently skipped by 'disseminate' and "
        f"silently counted as absorbed by 'prune'.\n"
        f"        Finish the relocation (or correct fleet.expected_min_projects) before "
        f"running {command}. See AGENTS 6 (deterministic governance)."
    )
    return 1


def discover_fleet_projects(root: Path) -> list[Path]:
    """Sibling folders with both AGENTS.md and docs/upgrades/ (skip _*/.* names)."""
    parent = root.parent
    projects: list[Path] = []
    for entry in sorted(parent.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir():
            continue
        if entry.name.startswith(("_", ".")):
            continue
        if entry.resolve() == root.resolve():
            continue
        if not (entry / "AGENTS.md").is_file():
            continue
        if not (entry / "docs" / "upgrades").is_dir():
            continue
        projects.append(entry)
    return projects


def same_content(source: Path, target: Path) -> bool:
    """True iff the two pack files carry the same instructions.

    Compared on normalised text, not bytes: the fleet spans repos with different
    line-ending settings, and a CRLF/LF difference is not a stale pack. Unreadable
    target => treat as different, so we refresh rather than silently skip.
    """
    try:
        a = source.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        b = target.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    except OSError:
        return False
    return a.strip() == b.strip()


def cmd_disseminate(args: argparse.Namespace) -> int:
    """Copy new packs from the template to each fleet project's docs/upgrades/."""
    root = get_project_root()

    project_name = read_project_name(root)
    if project_name != TEMPLATE_PROJECT_NAME:
        print(
            f"[ERROR] ONLY the master template disseminates - no fleet project, ever "
            f"(owner rule, 2026-08-29; AGENTS 6/9).\n"
            f"        This project is {project_name!r}, not '{TEMPLATE_PROJECT_NAME}'.\n"
            "        A fleet project may only DRAFT upgrade packs and push them to the master's\n"
            "        docs/upgrades/ for review. Do not ask for permission to disseminate;\n"
            "        the answer is already no."
        )
        return 1

    packs = find_packs(upgrades_dir(root))
    if not packs:
        print("[OK] No upgrade packs in the template's docs/upgrades/; nothing to disseminate.")
        return 0

    # --only scopes the run to exactly the packs the user approved. Without it, dissemination
    # ships WHATEVER is in the library at the moment it runs -- and the library is an inbox:
    # fleet projects drop packs here for review, so one that arrived minutes ago rides along
    # unnoticed. AGENTS 9 makes approval specific to "that specific dissemination", and until
    # this flag existed the command could not express anything narrower than "everything".
    if args.only:
        requested = {name.strip() for arg in args.only for name in arg.split(",") if name.strip()}
        available = {pack.name for pack in packs}
        unknown = sorted(requested - available)
        if unknown:
            print(
                "[ERROR] --only names pack(s) not in the library: " + ", ".join(unknown) + "\n"
                "        Refusing rather than silently disseminating a smaller set than you "
                "asked for (AGENTS 5.5.1).\n"
                "        Available: " + ", ".join(sorted(available))
            )
            return 1
        packs = [pack for pack in packs if pack.name in requested]
        withheld = sorted(available - requested)
        if withheld:
            print(f"Scoped by --only to {len(packs)} pack(s). WITHHELD, deliberately:")
            for name in withheld:
                print(f"  - {name}")

    projects = discover_fleet_projects(root)
    if not projects:
        print(
            "[ERROR] No fleet projects discovered (siblings with AGENTS.md and docs/upgrades/).\n"
            "        Dissemination reached nobody. That is a failure, not a no-op (AGENTS 5.5.1) -- "
            "the packs are still pending everywhere."
        )
        return 1
    if assert_fleet_is_whole(root, projects, "disseminate") != 0:
        return 1

    print(f"Discovered {len(projects)} fleet project(s):")
    for project in projects:
        print(f"  - {project.name}")
    print(f"Template packs considered: {len(packs)}")

    # Build the copy plan. Only ever writes inside <sibling>/docs/upgrades/.
    plan: dict[str, dict[str, list[str]]] = {}
    for project in projects:
        target_dir = upgrades_dir(project)
        target_ledger = read_ledger_text(target_dir)
        buckets: dict[str, list[str]] = {"copy": [], "update": [], "exists": [], "ledger": []}
        for pack in packs:
            target = target_dir / pack.name
            if target.exists():
                # A name match is NOT an up-to-date match. A pack revised after it was
                # first disseminated (a correction, a sharpened warning) would otherwise
                # be silently skipped forever, leaving the fleet holding a stale copy it
                # believes is current - a silent-success failure (AGENTS 5.5.1).
                if same_content(pack, target):
                    buckets["exists"].append(pack.name)
                else:
                    buckets["update"].append(pack.name)
            elif ledger_contains(target_ledger, pack.name):
                buckets["ledger"].append(pack.name)
            else:
                buckets["copy"].append(pack.name)
        plan[project.name] = buckets

    rows = [
        [
            name,
            str(len(buckets["copy"])),
            str(len(buckets["update"])),
            str(len(buckets["exists"])),
            str(len(buckets["ledger"])),
        ]
        for name, buckets in plan.items()
    ]
    print("\nDissemination plan:")
    print_table(
        ["Project", "To Copy", "To Refresh (stale)", "Skip (identical)", "Skip (in ledger)"], rows
    )

    total_copies = sum(len(b["copy"]) + len(b["update"]) for b in plan.values())
    for name, buckets in plan.items():
        for pack_name in buckets["copy"]:
            print(f"  [PLAN] {name}: copy {pack_name}")
        for pack_name in buckets["update"]:
            print(f"  [PLAN] {name}: REFRESH {pack_name} (their copy is stale)")
        # A recorded pack's file is deleted, so CONTENT comparison is impossible there.
        # If the pack was corrected after that project recorded it, dissemination cannot
        # reach it -- the trap that has now required a hand-delivery in two separate
        # sessions (08-16 and 08-17). Say so, by name, instead of hiding it in a count.
        for pack_name in buckets["ledger"]:
            print(
                f"  [RECORDED-SKIP] {name}: {pack_name} is recorded there and its copy is "
                "deleted. If this pack changed since, hand-deliver the new version - "
                "disseminate cannot tell."
            )

    if total_copies == 0:
        print("[OK] All fleet projects are up to date; nothing to copy.")
        return 0

    if args.dry_run:
        print(f"[DRY-RUN] Would copy {total_copies} file(s). No changes made.")
        return 0

    # Dissemination is the user's decision, never the agent's (AGENTS.md 9).
    # It writes instructions into every fleet project, and those instructions get
    # ACTED ON - a pack disseminated in error is not a stray file, it is work the
    # whole fleet performs. `--yes` only silences the prompt; it must never be
    # mistaken for approval, which is why approval is a separate, explicit flag.
    #
    # Honesty about what this can and cannot do: an agent can pass this flag as
    # easily as any other. It is a deliberate speed bump and an audit trail, not a
    # cryptographic gate. The rule is what binds; this makes the rule hard to
    # forget and impossible to satisfy by accident.
    if not args.approved_by_user:
        print(
            "\n[STOP] Dissemination needs the user's explicit approval and did not get it.\n"
            "       Nothing was copied.\n\n"
            "       Show the user the plan above - which packs, to which projects, and why -\n"
            "       and get their approval. Only then re-run with --approved-by-user.\n"
            "       Do NOT pass the flag on your own initiative; --yes is not approval."
        )
        return 1

    if not args.yes and not confirm(f"Copy {total_copies} pack file(s) to fleet projects?"):
        print("Aborting.")
        return 1

    failures = 0
    for project in projects:
        target_dir = upgrades_dir(project)
        buckets = plan[project.name]
        for pack_name in buckets["copy"] + buckets["update"]:
            refreshed = pack_name in buckets["update"]
            source = upgrades_dir(root) / pack_name
            dest = target_dir / pack_name
            try:
                shutil.copy2(str(source), str(dest))
                verb = "REFRESHED (was stale)" if refreshed else "Copied"
                print(f"[OK] {verb} {pack_name} -> {project.name}/docs/upgrades/")
            except OSError as exc:
                failures += 1
                print(f"[ERROR] Failed to copy {pack_name} to {project.name}: {exc}")

    if failures:
        print(f"[ERROR] {failures} copy operation(s) failed.")
        return 1
    print(f"[OK] Disseminated {total_copies} file(s) to {len(projects)} project(s).")
    return 0


# ---------------------------------------------------------------------------
# prune
# ---------------------------------------------------------------------------


def compute_pack_absorption(root: Path) -> tuple[list[Path], dict[str, list[str]]]:
    """Map each template pack to the fleet projects that have NOT recorded it.

    Returns (packs, pending_map) where pending_map[pack_name] lists the names
    of fleet projects whose ledger lacks a row for that pack. A pack with an
    empty pending list is fully absorbed and safe to prune.
    """
    packs = find_packs(upgrades_dir(root))
    projects = discover_fleet_projects(root)
    pending_map: dict[str, list[str]] = {}
    for pack in packs:
        pending: list[str] = []
        for project in projects:
            ledger_text = read_ledger_text(upgrades_dir(project))
            if not ledger_contains(ledger_text, pack.name):
                pending.append(project.name)
        pending_map[pack.name] = pending
    return packs, pending_map


def cmd_prune(args: argparse.Namespace) -> int:
    """Delete template packs whose ledger row exists in EVERY fleet project."""
    root = get_project_root()

    project_name = read_project_name(root)
    if project_name != TEMPLATE_PROJECT_NAME:
        print(
            f"[ERROR] ONLY the master template prunes its pack library - no fleet project, ever "
            f"(owner rule, 2026-08-29; AGENTS 6/9).\n"
            f"        This project is {project_name!r}, not '{TEMPLATE_PROJECT_NAME}'."
        )
        return 1

    projects = discover_fleet_projects(root)
    if not projects:
        print(
            "[ERROR] No fleet projects discovered; refusing to prune (absorption unverifiable).\n"
            "        'Nothing discovered' is not 'everything absorbed'."
        )
        return 1
    if assert_fleet_is_whole(root, projects, "prune") != 0:
        return 1

    packs, pending_map = compute_pack_absorption(root)
    if not packs:
        print("[OK] No upgrade packs in the template's docs/upgrades/; nothing to prune.")
        return 0

    absorbed = [p for p in packs if not pending_map[p.name]]
    print(f"Fleet projects checked: {len(projects)} ({', '.join(pr.name for pr in projects)})")
    rows = [
        [
            pack.name,
            f"absorbed ({len(projects)}/{len(projects)})"
            if not pending_map[pack.name]
            else f"pending in: {', '.join(pending_map[pack.name])}",
        ]
        for pack in packs
    ]
    print_table(["Pack File", "Absorption"], rows)

    if not absorbed:
        print("[OK] No pack is recorded by every fleet project yet; nothing to prune.")
        return 0

    if args.dry_run:
        print(f"[DRY-RUN] Would prune {len(absorbed)} pack(s). No changes made.")
        return 0

    if not args.yes and not confirm(f"Prune {len(absorbed)} fully-absorbed pack(s) from the template?"):
        print("Aborting.")
        return 1

    directory = upgrades_dir(root)
    ledger_path = directory / LEDGER_NAME
    failures = 0
    for pack in absorbed:
        try:
            row = build_ledger_row(
                pack.name,
                "pruned",
                f"Absorbed by all {len(projects)} fleet projects (ledger rows verified); "
                "removed from the live library. Recoverable via git history.",
            )
            append_ledger_row(ledger_path, read_ledger_text(directory), row)
            pack.unlink()
            stage_paths(root, [f"docs/upgrades/{LEDGER_NAME}", f"docs/upgrades/{pack.name}"])
            print(f"[OK] Pruned {pack.name}")
        except (OSError, RuntimeError) as exc:
            failures += 1
            print(f"[ERROR] Failed to prune {pack.name}: {exc}")

    if failures:
        print(f"[ERROR] {failures} prune operation(s) failed.")
        return 1
    print(f"[OK] Pruned {len(absorbed)} pack(s); template ledger updated.")
    return 0


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic lifecycle utility for upgrade instruction packs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="Show packs in docs/upgrades/ and ledger state.")

    record_parser = subparsers.add_parser(
        "record", help="Closing action: ledger row + pack deletion + git add."
    )
    record_parser.add_argument("pack_filename", type=str, help="Pack filename (bare, no path).")
    record_parser.add_argument(
        "--status",
        choices=["applied", "partial", "skipped"],
        default="applied",
        help="Outcome to record in the ledger (default: applied).",
    )
    record_parser.add_argument("--notes", type=str, default="", help="Optional ledger notes.")
    record_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt.")
    record_parser.add_argument("--dry-run", action="store_true", help="Preview without acting.")
    record_parser.add_argument(
        "--delete-pack",
        action="store_true",
        help=(
            "Delete the pack file even in the master template. Off by default there: "
            "docs/upgrades/ is the canonical library and removal is `prune`'s job."
        ),
    )

    disseminate_parser = subparsers.add_parser(
        "disseminate",
        help="Template-only: copy approved packs to fleet projects. Requires --approved-by-user.",
    )
    disseminate_parser.add_argument(
        "--dry-run", action="store_true", help="Preview the copy plan without acting."
    )
    disseminate_parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="PACK[,PACK...]",
        help=(
            "Disseminate ONLY these pack filenames (repeatable, or comma-separated). "
            "Use whenever the user approved specific packs rather than the whole library: "
            "docs/upgrades/ is also the inbox for packs the fleet sends back for review, so "
            "an unscoped run ships whatever happens to be sitting there. Unknown names are a "
            "hard error, never a silently smaller run."
        ),
    )
    disseminate_parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip the interactive confirmation prompt."
    )
    disseminate_parser.add_argument(
        "--approved-by-user",
        action="store_true",
        help=(
            "REQUIRED. Assert that the user has seen this specific dissemination and approved it. "
            "Dissemination pushes instructions into every fleet project, so it is the user's call, "
            "never the agent's (AGENTS.md 9). Without this flag the command prints the plan and stops."
        ),
    )

    prune_parser = subparsers.add_parser(
        "prune", help="Template-only: delete packs recorded by every fleet ledger."
    )
    prune_parser.add_argument(
        "--dry-run", action="store_true", help="Preview the prune plan without acting."
    )
    prune_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt.")

    args = parser.parse_args()
    handlers = {
        "list": cmd_list,
        "record": cmd_record,
        "disseminate": cmd_disseminate,
        "prune": cmd_prune,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
