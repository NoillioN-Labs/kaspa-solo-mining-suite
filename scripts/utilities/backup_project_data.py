"""
scripts/utilities/backup_project_data.py
=========================================

Mirror selected, category-scoped project data to an external destination.

WHY THIS EXISTS. Projects that used to live on a cloud-synced path had an
*incidental* backup of their git-ignored data. Moving to a plain local path removed
it, and nothing replaced it -- which nobody notices, because git keeps working and
git is what everyone checks. The data at risk is exactly the data git does not hold:
`client_files/` (raw client source material, git-ignored by AGENTS 3) and `.data/`
(databases, artifacts). Neither is regenerable from the repo.

CONFIGURATION (config.yaml `backup`), because a template cannot know your data
layout or where you keep backups::

    backup:
      destination_path: ""          # REQUIRED. Never guessed.
      categories:                   # name -> glob, relative to repo root
        client_files: "client_files/**/*"
        data: ".data/**/*"
        database_backups: ".data/backups/**/*"
      include:                      # every category is OFF until explicitly enabled
        client_files: false
        data: false
        database_backups: false

The first two categories are the ones AGENTS 3 gives every project. The third exists
SEPARATELY FROM `data` on purpose: `.data/**/*` byte-copies the LIVE database
mid-write and produces a torn -- possibly unopenable -- file that looks exactly like a
backup and is discovered to be worthless at the worst possible moment, while
`.data/backups/**/*` copies only files written through the SQLite online backup API
(backup_db.py), which are consistent by construction. Add your own (renders, exports,
model weights) as extra `categories` entries; the rule is *mirror the artefacts a
consistent-snapshot mechanism produced, never byte-copy a file something else is
writing*.

**A single trailing `*` is deliberately non-recursive** where a category must exclude
a sibling subdirectory; filtering to `.is_file()` then drops any directory the glob
level happens to match.

DESTINATION IS ALWAYS AN EXPLICIT CHOICE. AGENTS 9 makes external destinations
"ask first", so this refuses to run until `backup.destination_path` is set or
`--destination` is passed. It will never guess one.

Dry-run by default (AGENTS 5.1). **One-way and additive only** -- it never deletes
anything at the destination *because the source no longer has it*. Surviving a
source-side loss is the entire point; a mirror that propagates deletions is a sync,
and a sync will happily replicate your mistake.

`--prune-destination` is NOT a relaxation of that rule, and the distinction is the
whole design::

    propagated deletion (a sync)   triggered by: the source file disappeared
                                   worst case:   `rm -rf` at source wipes the offsite copy too

    independent retention (here)   triggered by: the DESTINATION holds more than its policy
                                   worst case:   keeps the same N files the local policy keeps
                                   reads:        the destination directory ONLY -- never the source

Without it, an additive mirror of a daily 500MB database snapshot grows without bound
(~15GB/month). Nothing ever fails meanwhile -- no error, no warning, no exit code --
so the cheapest fix in the moment is to switch the whole thing off, and a backup nobody
can afford to keep running is not a backup. With it, the destination applies the same
grandfather-father-son policy (`config.yaml database_backups`) computed purely from its
own contents, so no source-side catastrophe can reach it.

Usage
-----
    python scripts/utilities/backup_project_data.py
    python scripts/utilities/backup_project_data.py --execute
    python scripts/utilities/backup_project_data.py --destination D:\\Backups\\proj --execute
    python scripts/utilities/backup_project_data.py --prune-destination --execute
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Categories every project has under AGENTS 3, plus the snapshot-only category the
#: producer (backup_db.py) writes into. Projects extend this via config.
#: `database_backups` is deliberately NOT the same thing as `data`: `.data/**/*`
#: byte-copies the LIVE database mid-write and yields a torn file that looks like a
#: backup, while `.data/backups/**/*` holds only files written through the SQLite
#: online backup API, which are consistent by construction. It ships OFF like every
#: other category, but it has to EXIST here -- load_enabled_categories() iterates
#: these keys, so a category that is not a default (or a config override) can never be
#: switched on at all, and _RETAINED_CATEGORY_DIRS keys retention on this exact name.
#: Fallback only -- the real value comes from `database_backups.backup_dir` (config.yaml).
_DEFAULT_BACKUP_DIR: str = ".data/backups"

_DEFAULT_CATEGORIES: dict[str, str] = {
    "client_files": "client_files/**/*",
    "data": ".data/**/*",
    "database_backups": f"{_DEFAULT_BACKUP_DIR}/**/*",
}


def _load_backup_config(config_path: Path | None = None) -> dict:
    """The `backup:` block of config.yaml (empty dict on any failure)."""
    try:
        import yaml
    except ImportError:
        return {}

    path = config_path or (PROJECT_ROOT / "config.yaml")
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError):
        return {}
    block: Any = loaded.get("backup")
    return block if isinstance(block, dict) else {}


def database_backup_dir(config_path: Path | None = None) -> str:
    """Repo-relative directory the producer writes snapshots into.

    ONE source of truth, read from the same `database_backups:` block the producer and
    the pruner use. Hardcoding it here is the identical defect this module already
    documents for `filename_prefix`, just wearing a path: a project that sets
    `backup_dir` gets a mirror whose glob matches nothing and a retention pass pointed at
    an empty directory -- copying nothing, pruning nothing, exit 0 both times.
    """
    try:
        import yaml
    except ImportError:
        return _DEFAULT_BACKUP_DIR
    path = config_path or (PROJECT_ROOT / "config.yaml")
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError):
        return _DEFAULT_BACKUP_DIR
    block = loaded.get("database_backups")
    value = block.get("backup_dir") if isinstance(block, dict) else None
    return str(value).replace("\\", "/").rstrip("/") if value else _DEFAULT_BACKUP_DIR


def destination_relative_backup_dir(
    config_path: Path | None = None, project_root: Path | None = None
) -> str | None:
    """`backup_dir` expressed relative to the project root, or None if it cannot be.

    `backup_dir` is documented as "relative to repo root, or absolute", and an absolute
    one is a live hazard in BOTH consumers:

      * `destination_root / Path("/abs/dir")` DISCARDS destination_root -- pathlib
        rebases on an absolute right operand. Retention would then delete from the
        SOURCE tree. That is the propagated-deletion failure this module exists to make
        impossible, arriving through a config value rather than through code.
      * `Path.glob("/abs/**/*")` raises NotImplementedError, out of a function this
        module documents as raising nothing.

    So: rebase an absolute path onto the project root when it lies inside, and return
    None when it does not -- there is no destination-relative meaning for a directory
    outside the tree being mirrored, and guessing one is how you delete the wrong files.
    """
    raw = Path(database_backup_dir(config_path))
    if not raw.is_absolute():
        return raw.as_posix()
    root = Path(project_root or PROJECT_ROOT)
    try:
        return raw.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def load_categories(config_path: Path | None = None) -> dict[str, str]:
    """Category name -> glob. Config entries extend and override the defaults."""
    configured = _load_backup_config(config_path).get("categories")
    categories = dict(_DEFAULT_CATEGORIES)
    rel = destination_relative_backup_dir(config_path)
    # An unusable backup_dir falls back to the default rather than building an absolute
    # glob: Path.glob rejects those with NotImplementedError, and this function is called
    # from one documented as raising nothing.
    categories["database_backups"] = f"{rel or _DEFAULT_BACKUP_DIR}/**/*"
    if isinstance(configured, dict):
        categories.update({str(k): str(v) for k, v in configured.items() if v})
    return categories


def load_destination(config_path: Path | None = None) -> str | None:
    value = _load_backup_config(config_path).get("destination_path")
    return value if isinstance(value, str) and value.strip() else None


def load_enabled_categories(config_path: Path | None = None) -> list[str]:
    """Category names explicitly enabled via `backup.include.<name>: true`.

    An unconfigured category is OFF, never guessed on: copying a directory the owner
    did not name -- to a destination outside the project -- is exactly the kind of
    thing AGENTS 9 requires asking about first.
    """
    categories = load_categories(config_path)
    include = _load_backup_config(config_path).get("include")
    include = include if isinstance(include, dict) else {}
    return [name for name in categories if include.get(name) is True]


def discover_category_files(category: str, project_root: Path, categories: dict[str, str]) -> list[Path]:
    """Every real file matching `category`'s glob, deduplicated and sorted."""
    pattern = categories[category]
    return sorted({p for p in project_root.glob(pattern) if p.is_file()})


def mirror_files(
    files: list[Path], project_root: Path, destination_root: Path, *, execute: bool
) -> dict[str, int]:
    """Copy each file (by its path relative to project_root) into destination_root
    when the destination copy is missing, older, or A DIFFERENT SIZE. Never deletes at
    the destination because the source no longer has the file.

    SIZE IS PART OF THE FRESHNESS TEST, and the copy is atomic. Both exist because of
    the same defect, reproduced in a fleet project without any monkeypatching: kill a
    copy mid-flight (reboot, sync-client restart, ENOSPC) and ``shutil.copy2`` leaves a
    TRUNCATED file at the destination whose mtime -- written now, while the source
    snapshot was written minutes ago -- is NEWER than the source's. An mtime-only test
    then reports it "already current" every night thereafter. Measured: a 123 MB
    snapshot became a 16.8 MB stub that SQLite rejects as "database disk image is
    malformed", reported healthy forever after one loud night.

    Worse at scale: a genuinely full destination raises on the FIRST write of each
    file, by which point ``open(dst, 'wb')`` has already created a 0-byte file -- for
    EVERY file in the batch. One disk-full night could convert the whole mirror,
    including the irreplaceable hand-named snapshots, into 0-byte files that would then
    be called "already current" and never re-copied.

    So: copy to ``<name>.partial`` and ``os.replace()`` only on success (atomic on
    Windows and POSIX for a same-directory rename), and unlink the partial if the copy
    raises. A failed copy leaves NOTHING that could be mistaken for a backup -- AGENTS
    5.5.1's "a fallback that silently returns success is a latent incident", applied to
    bytes rather than to control flow.
    """
    copied = skipped = failed = 0
    for path in files:
        rel = path.relative_to(project_root)
        dest_file = destination_root / rel
        try:
            src_stat = path.stat()
            up_to_date = (
                dest_file.exists()
                and dest_file.stat().st_size == src_stat.st_size
                and dest_file.stat().st_mtime >= src_stat.st_mtime
            )
        except OSError:
            up_to_date = False
        if up_to_date:
            skipped += 1
            continue
        copied += 1
        if not execute:
            continue
        partial = dest_file.with_name(dest_file.name + ".partial")
        try:
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, partial)
            os.replace(partial, dest_file)
        except OSError as exc:
            print(f"[WARN] could not copy {path} -> {dest_file}: {exc}")
            copied -= 1
            failed += 1
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                # Leaving a .partial is untidy but harmless: it can never be mistaken
                # for a backup, which is the property that matters.
                pass
    return {"copied": copied, "skipped": skipped, "failed": failed}


#: Categories whose destination copies are subject to independent GFS retention, mapped
#: to the destination-relative directory the policy applies to. Keyed by CATEGORY NAME,
#: not by directory, so a project that adds a `renders` or `exports` category does not
#: silently acquire a deleter over it -- it declares the intent here instead.
#: Retention applies to these CATEGORIES. The directory is NOT hardcoded here -- it is
#: read from `database_backups.backup_dir` at call time (see database_backup_dir), so a
#: project that relocates its snapshots keeps both halves pointed at the same place.
_RETAINED_CATEGORIES: frozenset[str] = frozenset({"database_backups"})


def prune_destination_backups(
    destination_root: Path,
    *,
    execute: bool,
    config_path: Path | None = None,
    enabled_categories: list[str] | None = None,
) -> dict[str, int]:
    """Apply the local GFS retention policy to the DESTINATION's own contents.

    Reads nothing from the source tree -- see the module docstring for why that single
    fact is the difference between retention and a sync. Delegates selection to
    `prune_db_backups.select_backups_to_prune`, which matches only
    `<database_backups.filename_prefix>_<YYYYMMDD>_<HHMMSS>.db`, so hand-named snapshots
    living in the same folder are copied but never candidates. That protection is
    inherited deliberately: each hand-named snapshot is the last known-good state before
    a destructive repair, which makes them the most valuable files in the folder.

    RETENTION ONLY EVER APPLIES TO A CATEGORY THAT IS ACTUALLY BEING MIRRORED. Without
    that gate, setting `include.database_backups: false` -- the documented way to turn
    the mirror OFF -- converts the job into a pure destination-side DELETER: it stops
    copying and keeps deleting, quietly eroding the offsite set it no longer maintains.
    Turning a feature off must not leave half of it running.
    """
    # Two import styles because this module is reached two ways: as part of the package
    # (a scheduled job importing scripts.utilities.*) and via a bare sys.path insertion
    # of scripts/utilities (the test suite's convention). Neither is wrong; assuming
    # only one is. BOTH failing is reported loudly and as failed=-1, never a quiet 0:
    # "the retention pass did not run" must not read like "there was nothing to prune"
    # (AGENTS 5.5.1).
    try:
        from scripts.utilities.prune_db_backups import (
            _load_config,
            prune,
            select_backups_to_prune,
        )
    except ImportError:
        try:
            from prune_db_backups import (  # type: ignore[no-redef]
                _load_config,
                prune,
                select_backups_to_prune,
            )
        except ImportError:
            print("[WARN] prune_db_backups unavailable; destination retention skipped.")
            return {"candidates": 0, "deleted": 0, "failed": -1}

    enabled = (
        enabled_categories
        if enabled_categories is not None
        else load_enabled_categories(config_path)
    )
    try:
        retention = _load_config(config_path)
    except Exception as exc:  # noqa: BLE001 -- see below; yaml raises its own hierarchy
        # A malformed config.yaml must not escape as an exception. This function is
        # documented as never raising and runs AFTER files have already been copied, so
        # a traceback here destroys the report of a backup that did land. Fail the way
        # everything else in this module fails: loudly, with the -1 "did not run"
        # sentinel, never a quiet zero (AGENTS 5.5.1).
        print(f"[WARN] cannot read retention config ({type(exc).__name__}); "
              "destination retention skipped.")
        return {"candidates": 0, "deleted": 0, "failed": -1}
    daily_count = retention["daily_count"]
    weekly_count = retention["weekly_count"]
    # THE PREFIX MUST COME FROM THE SAME CONFIG BLOCK THE PRODUCER WRITES WITH.
    # select_backups_to_prune and prune both DEFAULT to "backup", so a defaulted prefix
    # here matches nothing at a destination whose files are named anything else: no
    # candidates printed, nothing deleted, {0, 0, 0} returned, exit 0 -- a no-op wearing
    # the appearance of a working retention policy, on top of a mirror that keeps
    # growing. Pass it to BOTH call sites: passing it only to the selection would make
    # the log name a set of files that is not the set being deleted, which is worse.
    filename_prefix = retention["filename_prefix"]
    totals = {"candidates": 0, "deleted": 0, "failed": 0}
    for category in sorted(_RETAINED_CATEGORIES):
        if category not in enabled:
            continue
        rel_dir = destination_relative_backup_dir(config_path)
        if rel_dir is None:
            print(
                "[WARN] database_backups.backup_dir is absolute and outside the project; "
                "it has no destination-relative meaning, so retention is skipped rather "
                "than aimed at a guessed directory."
            )
            totals["failed"] = -1
            continue
        target = destination_root / Path(rel_dir)
        if not target.is_dir():
            continue
        # Name the files, don't just count them: this is a DELETE against an external
        # destination, and prune_db_backups.main() already sets the precedent of listing
        # every candidate before acting.
        candidates = select_backups_to_prune(
            target,
            daily_count=daily_count,
            weekly_count=weekly_count,
            filename_prefix=filename_prefix,
        )
        if candidates:
            verb = "pruning" if execute else "would prune"
            print(
                f"  destination retention ({category}): {verb} {len(candidates)} file(s) "
                f"under {daily_count}/day + {weekly_count}/week, prefix '{filename_prefix}'"
            )
            for path in sorted(candidates):
                print(f"      {path.name}")
        result = prune(
            target,
            daily_count=daily_count,
            weekly_count=weekly_count,
            execute=execute,
            filename_prefix=filename_prefix,
        )
        for key in totals:
            totals[key] += result[key]
    return totals


def mirror_enabled_categories(
    destination_root: Path | None = None,
    *,
    execute: bool,
    prune_destination: bool = False,
    project_root: Path | None = None,
    config_path: Path | None = None,
    verify_landed: Path | None = None,
) -> dict[str, int]:
    """Mirror every enabled category and (optionally) apply destination retention.

    Returns aggregate counts plus `destination_pruned` and `verified`. RAISES NOTHING:
    a caller embedded in a scheduled backup job (backup_db.py writes the snapshot, this
    copies it off-machine) needs a result it can REPORT ON, not an exception that fails
    an otherwise-good backup.

    `failed == -1` is an explicit sentinel for "no destination configured" and for a
    configured destination that does not exist. Both mean *nothing was attempted*, which
    must never be reportable as success.

    `verify_landed` is the source path of the artefact this run exists to protect. It
    turns "a new backup exists, therefore copy it off-machine" from a claim into a
    check. A guard keyed on `copied == 0` would be wrong, because a legitimate re-run
    gives copied=0/skipped=15; the question is never "did we copy anything" but "did
    THIS backup land" (AGENTS 4.1 axis 3).
    """
    root = project_root or PROJECT_ROOT
    categories = load_categories(config_path)
    enabled = load_enabled_categories(config_path)
    totals = {
        "copied": 0, "skipped": 0, "failed": 0,
        "destination_pruned": 0, "categories": len(enabled), "verified": 0,
    }

    destination_str = (
        str(destination_root) if destination_root else load_destination(config_path)
    )
    if not destination_str:
        totals["failed"] = -1  # sentinel: nothing was attempted, and that is a failure to report
        return totals
    dest_root = Path(destination_str)

    # A destination that does not exist must NOT be fabricated. mirror_files calls
    # mkdir(parents=True) per file, so a typo'd or unmounted destination would silently
    # create a brand-new empty tree ON THE LOCAL DISK, copy into it, and report complete
    # success -- while the "off-machine" copy sat on the very disk it exists to survive
    # and the real offsite set was orphaned elsewhere.
    if not dest_root.is_dir():
        print(
            f"[REFUSED] backup destination does not exist: {dest_root}. Not creating "
            "it -- an auto-created destination is indistinguishable from a typo, and "
            "would report a fully successful backup into the wrong place."
        )
        totals["failed"] = -1
        return totals

    for category in enabled:
        files = discover_category_files(category, root, categories)
        result = mirror_files(files, root, dest_root, execute=execute)
        totals["copied"] += result["copied"]
        totals["skipped"] += result["skipped"]
        totals["failed"] += result["failed"]

    # The enabled-category gate lives in prune_destination_backups (one place, one
    # test). An `and enabled` here as well would be a SECOND opinion about the same fact
    # that no mutation can kill -- removing it changes no behaviour, which is precisely
    # what makes it noise rather than defence.
    if prune_destination:
        pruned = prune_destination_backups(
            dest_root, execute=execute, config_path=config_path, enabled_categories=enabled
        )
        totals["destination_pruned"] = pruned["deleted"]
        # A skipped retention pass is a FAILURE TO REPORT ON, counted as one -- not
        # max(..., 0), which clamps the -1 sentinel to nothing and hands an embedded
        # caller `failed: 0` for a pass that never ran. The sentinel must not decrement
        # the count either, hence the branch rather than a raw sum. Same shape as main().
        totals["failed"] += 1 if pruned["failed"] < 0 else pruned["failed"]

    if verify_landed is not None and execute:
        try:
            rel = Path(verify_landed).resolve().relative_to(Path(root).resolve())
            landed = dest_root / rel
            if landed.exists() and landed.stat().st_size == Path(verify_landed).stat().st_size:
                totals["verified"] = 1
        except (OSError, ValueError):
            totals["verified"] = 0
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--destination", type=str, default=None,
        help="Override config.yaml's backup.destination_path for this run.",
    )
    parser.add_argument("--execute", action="store_true", help="Actually copy (default: dry-run).")
    parser.add_argument(
        "--prune-destination", action="store_true",
        help=(
            "After mirroring, apply the config.yaml database_backups GFS policy to the "
            "DESTINATION's own contents. Never consults the source, so a source-side "
            "deletion can never propagate. --execute still governs whether anything is "
            "actually deleted."
        ),
    )
    args = parser.parse_args(argv)

    categories = load_categories()
    destination_str = args.destination or load_destination()
    if not destination_str:
        print(
            "[REFUSED] No backup destination configured. Set backup.destination_path in "
            "config.yaml, or pass --destination <path>. This script will never guess one "
            "(AGENTS 9: ask first for external destinations)."
        )
        return 1

    enabled = load_enabled_categories()
    if not enabled:
        print(
            "[OK] No backup.include categories are enabled in config.yaml; nothing to do. "
            f"Available: {', '.join(categories)}."
        )
        return 0

    destination_root = Path(destination_str)
    # The SAME refusal mirror_enabled_categories makes, because this is the entry point the
    # module's own Usage block tells people to run. Guarding only the library function left
    # the documented CLI fabricating an unmounted destination on the local disk, copying into
    # it and exiting 0 with "Copied N file(s)" -- a fully successful backup onto the very disk
    # it exists to survive. A guard that covers one of two call sites is not a guard.
    if not destination_root.is_dir():
        print(
            f"[REFUSED] backup destination does not exist: {destination_root}. Not creating "
            "it -- an auto-created destination is indistinguishable from a typo, and would "
            "report a fully successful backup into the wrong place."
        )
        return 1

    print(f"Destination: {destination_root}")
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print(f"Categories: {', '.join(enabled)}")

    total_copied = total_skipped = total_failed = 0
    for category in enabled:
        files = discover_category_files(category, PROJECT_ROOT, categories)
        result = mirror_files(files, PROJECT_ROOT, destination_root, execute=args.execute)
        total_copied += result["copied"]
        total_skipped += result["skipped"]
        total_failed += result["failed"]
        print(
            f"  {category}: {len(files)} file(s) -- "
            f"{result['copied']} to copy, {result['skipped']} already current, "
            f"{result['failed']} failed"
        )

    if args.prune_destination:
        pruned = prune_destination_backups(destination_root, execute=args.execute)
        # A -1 here means the pruner could not be imported: nothing was attempted.
        # Adding it raw would DECREMENT the failure count -- one failed copy plus one
        # skipped retention pass would sum to 0 and exit clean. Count it as its own
        # failure so "did not run" can never read as green (AGENTS 4.1 axis 6).
        total_failed += 1 if pruned["failed"] < 0 else pruned["failed"]
        if not pruned["candidates"]:
            print("  destination retention: nothing to prune.")

    verb = "Copied" if args.execute else "[DRY-RUN] Would copy"
    print(f"\n{verb} {total_copied} file(s); {total_skipped} already current; {total_failed} failed.")
    if not args.execute:
        print("Re-run with --execute to actually copy.")
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
