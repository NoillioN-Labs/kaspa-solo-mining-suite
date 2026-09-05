#!/usr/bin/env python3
"""Branch-and-line coverage gate (AGENTS 5.7).

Coverage's job here is to be the *deterministic arm* of AGENTS 4.1 axis 3 -- "a
passing test that never exercised the path proves nothing". It does NOT chase a
percentage. It enforces two things a script can enforce honestly:

  1. Diff coverage -- every new/changed executable line must be covered.
  2. Ratchet     -- total coverage may not fall below the tracked baseline.

Line/branch percentages are reported for insight but never turned into a target
(Goodhart): a fixed "80% or fail" gate rewards tests-for-coverage and punishes
legacy code. New code covered + no regression is the governance-shaped metric.

Usage:
    python scripts/utilities/coverage_gate.py [--run] [--json] [--update-baseline]

    --run              Run the FULL pytest suite with coverage first, producing the
                       Cobertura XML the gate reads. Without it, the gate reads the
                       existing report at testing.coverage.coverage_xml.
    --update-baseline  Write the current line/branch percentages to the baseline
                       file (raise the ratchet floor). Never lowers a set floor
                       unless --force is given.
    --force            Allow --update-baseline to lower an existing floor.
    --json             Emit the metrics as a machine-readable JSON object.

Exit codes:
    0 -- pass, OR any outcome in advisory mode (mode: advisory never blocks).
    1 -- a hard failure in gating mode (diff coverage below floor, total regressed
         below baseline, or the coverage report is missing/unreadable).

Configuration lives in config.yaml under testing.coverage (AGENTS 5.1); nothing is
hardcoded here. Output is ASCII-only so it survives Windows cp1252 pipes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - degraded mode when pyyaml missing
    yaml = None  # type: ignore[assignment]

# Repo root = two levels up from scripts/utilities/.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG: dict = {
    "mode": "advisory",
    "branch": True,
    "source": ["backend"],
    "diff_base": "origin/master",
    "min_diff_coverage_pct": 90.0,
    "ratchet_tolerance_pct": 0.5,
    "baseline_file": "docs/coverage_baseline.json",
    "coverage_xml": ".data/test_artifacts/coverage.xml",
    "extra_coverage_xml": [],  # additional Cobertura reports to aggregate (e.g. frontend vitest)
}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class FileCoverage:
    """Executable and covered line numbers for one source file."""

    executable: set[int] = field(default_factory=set)
    covered: set[int] = field(default_factory=set)


@dataclass
class CoverageReport:
    """Merged Cobertura data: per-file line hits plus aggregate branch counts.

    Line coverage is derived from the per-file executable/covered sets (exact, and
    correct when several reports are merged); branch coverage from the Cobertura
    root counts, which are summed across reports.
    """

    files: dict[str, FileCoverage] = field(default_factory=dict)
    branches_covered: int = 0
    branches_valid: int = 0

    @property
    def line_pct(self) -> float:
        executable = sum(len(fc.executable) for fc in self.files.values())
        covered = sum(len(fc.covered) for fc in self.files.values())
        return covered / executable * 100.0 if executable else 0.0

    @property
    def branch_pct(self) -> float:
        return self.branches_covered / self.branches_valid * 100.0 if self.branches_valid else 0.0

    def merge(self, other: CoverageReport) -> None:
        """Fold another report in: union line data per file, sum branch counts."""
        for name, fc in other.files.items():
            target = self.files.setdefault(name, FileCoverage())
            target.executable |= fc.executable
            target.covered |= fc.covered
        self.branches_covered += other.branches_covered
        self.branches_valid += other.branches_valid


@dataclass
class GateResult:
    """Outcome of one gate evaluation."""

    line_pct: float | None = None
    branch_pct: float | None = None
    diff_covered: int = 0
    diff_total: int = 0
    diff_pct: float | None = None
    baseline_line_pct: float | None = None
    baseline_branch_pct: float | None = None
    messages: list[tuple[str, str]] = field(default_factory=list)  # (severity, text)
    failed: bool = False  # a HARD failure occurred (gates on it only when mode == gating)

    def note(self, severity: str, text: str) -> None:
        self.messages.append((severity, text))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_coverage_config(root: Path) -> dict:
    """Read testing.coverage from config.yaml, defaulting any missing key."""
    config = dict(DEFAULT_CONFIG)
    config_path = root / "config.yaml"
    if yaml is None or not config_path.is_file():
        return config
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8", errors="replace"))
    except yaml.YAMLError:
        return config
    section = (data or {}).get("testing", {}) if isinstance(data, dict) else {}
    coverage = section.get("coverage", {}) if isinstance(section, dict) else {}
    if isinstance(coverage, dict):
        for key, value in coverage.items():
            if key in config and value is not None:
                config[key] = value
    return config


# ---------------------------------------------------------------------------
# Cobertura parsing
# ---------------------------------------------------------------------------


def _is_dir(path: Path) -> bool:
    """`Path.is_dir()` that cannot take the gate down (AGENTS 5.5.1).

    On Windows these probes *raise* WinError 1920 near legacy symlinks and reparse
    points rather than returning False, and a path-probing helper is exactly where
    that lands -- an exception here would kill the whole run over a file it was only
    asking about.
    """
    try:
        return path.is_dir()
    except OSError:
        return False


def _is_file(path: Path) -> bool:
    """`Path.is_file()` with the same WinError 1920 guard as :func:`_is_dir`."""
    try:
        return path.is_file()
    except OSError:
        return False


def source_prefixes(xml_root: ET.Element, repo_root: Path | None) -> list[str]:
    """Repo-relative prefixes for the report's <sources> roots, in document order.

    Returns ``[""]`` when the roots cannot be placed inside the repository (a report
    from another machine, or one with no <sources> element), leaving filenames
    untouched -- degrading to the old behaviour rather than guessing.
    """
    prefixes: list[str] = []
    for source in xml_root.iter("source"):
        text = (source.text or "").strip()
        if not text:
            continue
        candidate = Path(text.replace("\\", "/"))
        rel: str | None = None
        if repo_root is not None:
            try:
                rel = candidate.resolve().relative_to(repo_root.resolve()).as_posix()
            except (ValueError, OSError):
                # Report written elsewhere (a CI checkout at a different absolute
                # path): fall back to the longest trailing segment that IS a
                # directory here.
                parts = candidate.parts
                for start in range(len(parts)):
                    suffix = Path(*parts[start:]).as_posix()
                    if suffix and _is_dir(repo_root / suffix):
                        rel = suffix
                        break
        if rel is not None and rel not in (".", ""):
            prefixes.append(rel)
    return prefixes or [""]


def _resolve_filename(filename: str, prefixes: list[str], repo_root: Path | None) -> str:
    """Attach the source-root prefix that actually locates *filename* on disk.

    Cobertura writes ``class/@filename`` relative to whichever source root matched the
    file, NOT relative to the repository -- so `--cov=backend` yields ``ingest.py``,
    while `git diff` yields ``backend/ingest.py``. Without this, the diff arm's lookup
    misses every single time and every added line is skipped by a branch whose comment
    explains it away as "docs, config, tests".
    """
    if prefixes == [""]:
        return filename
    if repo_root is not None:
        for prefix in prefixes:
            if _is_file(repo_root / prefix / filename):
                return f"{prefix}/{filename}"
    # Unresolvable on disk: a single root is unambiguous, several are not. Guessing
    # between two roots would attribute coverage to the wrong file, which is worse
    # than leaving it unmatched.
    if len(prefixes) == 1:
        return f"{prefixes[0]}/{filename}"
    return filename


def parse_cobertura(xml_path: Path, repo_root: Path | None = None) -> CoverageReport:
    """Parse a Cobertura coverage.xml into overall rates and per-file line hits.

    *repo_root* lets filenames be resolved back to repo-relative paths via the
    report's own <sources> roots; without it the keys stay exactly as written, which
    is correct for a report whose roots cannot be located here.

    Raises FileNotFoundError if the report is absent and ET.ParseError if it is
    malformed -- both are surfaced loudly by the caller, never swallowed into a
    green result (AGENTS 5.5.1).
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    prefixes = source_prefixes(root, repo_root)

    def _int(attr: str) -> int:
        try:
            return int(root.get(attr, "0") or 0)
        except ValueError:
            return 0

    files: dict[str, FileCoverage] = {}
    for cls in root.iter("class"):
        filename = cls.get("filename")
        if not filename:
            continue
        # Normalise to posix so it matches `git diff` paths on every platform, then
        # re-attach the source root the file actually lives under.
        key = _resolve_filename(filename.replace("\\", "/"), prefixes, repo_root)
        fc = files.setdefault(key, FileCoverage())
        for line in cls.iter("line"):
            try:
                number = int(line.get("number", ""))
                hits = int(line.get("hits", "0"))
            except ValueError:
                continue
            fc.executable.add(number)
            if hits > 0:
                fc.covered.add(number)
    return CoverageReport(
        files=files,
        branches_covered=_int("branches-covered"),
        branches_valid=_int("branches-valid"),
    )


def read_reports(root: Path, rel_paths: list[str]) -> tuple[CoverageReport, list[str], list[str]]:
    """Parse and merge every Cobertura path. Returns (merged, missing_rels, malformed_rels).

    A missing/malformed report is recorded and skipped, never silently treated as
    zero coverage -- the caller decides whether that is fatal (AGENTS 5.5.1).
    """
    merged = CoverageReport()
    missing: list[str] = []
    malformed: list[str] = []
    for rel in rel_paths:
        try:
            merged.merge(parse_cobertura(root / rel, repo_root=root))
        except FileNotFoundError:
            missing.append(rel)
        except ET.ParseError:
            malformed.append(rel)
    return merged, missing, malformed


# ---------------------------------------------------------------------------
# Diff coverage
# ---------------------------------------------------------------------------


def git_added_lines(root: Path, base: str) -> dict[str, set[int]] | None:
    """Return {posix_path: {added_line_no, ...}} for the diff against `base`.

    Returns None when the base ref cannot be resolved (fresh repo, shallow CI
    checkout, unknown remote) -- an honest "cannot compute", never a false zero.
    """
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", base],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None

    def _run_diff(merge_base: bool) -> subprocess.CompletedProcess[str] | None:
        # --merge-base, not the bare tip form. `git diff <base>` charges this branch
        # with every line changed ON the base since the fork point, so under the
        # batched-push discipline (AGENTS 8) each story's reported diff coverage
        # swallows the previous story's lines. git < 2.30 does not know the flag, so
        # the caller retries without it: a slightly wider scope is a wrong number, but
        # returning None would silently disable the gate's PRIMARY arm entirely.
        scope = ["--merge-base", base] if merge_base else [base]
        try:
            return subprocess.run(
                [
                    "git",
                    # core.quotepath=false: git otherwise C-escapes any non-ASCII path
                    # (`"b/backend/caf\303\251.py"`), which can never match the Cobertura
                    # filename, so every added line in such a file is silently dropped from
                    # diff coverage -- an emoji in a FILENAME, not just in a diff body.
                    "-c",
                    "core.quotepath=false",
                    "diff",
                    "--unified=0",
                    "--no-color",
                    *scope,
                    "--",
                    ".",
                ],
                cwd=root,
                check=True,
                capture_output=True,
                # NOT text=True: that decodes with the LOCALE codec, which on Windows is cp1252.
                #
                # MEASURED 2026-08-17, because two earlier versions of this comment were both
                # wrong and each sent the reader somewhere different. cp1252 leaves exactly
                # 0x81/0x8D/0x8F/0x90/0x9D undefined, and a character only raises if its UTF-8
                # encoding CONTAINS one of those bytes -- Cyrillic Yo (U+0401 -> D0 81) does;
                # em-dash, the curly quote, emoji, CJK, U+2028 and U+0085 all do NOT. Those
                # decode to silent mojibake instead, which is the worse half: a corrupted path
                # simply stops matching the Cobertura filename and the line vanishes from diff
                # coverage with nothing raised (AGENTS 5.5.1). errors="replace" keeps a byte we
                # cannot decode from taking the whole gate down; the parser reads only the ASCII
                # structural markers, so a replacement character in a CONTENT line costs nothing.
                #
                # That last sentence is true of bytes and NOT of line boundaries, which is why the
                # loop below splits on "\n" rather than using str.splitlines() -- see there.
                encoding="utf-8",
                errors="replace",
            )
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            return None

    proc = _run_diff(merge_base=True) or _run_diff(merge_base=False)
    if proc is None:
        return None

    # Belt-and-braces, and NOT the dead branch it looks like. With the explicit codec above
    # a decode cannot fail, so nothing should reach this -- but the guard is what stands
    # between any FUTURE decode failure and an error that names nothing. On Windows,
    # capture_output reads the pipes on READER THREADS: a decode error is raised inside the
    # thread, never re-raised, so no `except` around the call above can see it and
    # `proc.stdout` simply arrives as None. That is exactly the reported symptom of the bug
    # this function was fixed for -- a traceback belonging to nobody, then an AttributeError
    # pointing at the parser. Confirmed by mutation: restore text=True and this branch fires.
    # Return the honest "cannot compute" this function documents, never a crash.
    if proc.stdout is None:
        return None

    added: dict[str, set[int]] = {}
    current: str | None = None
    # split("\n"), NOT splitlines(). str.splitlines() also breaks on U+0085, U+2028, U+2029,
    # \v, \f and \x1c-\x1e -- none of which git uses as a line terminator, all of which can
    # appear in a diffed file's CONTENT. Decoding as UTF-8 is what makes them reachable: read
    # as cp1252 those bytes are ordinary characters, so the old locale decode was accidentally
    # safe here and the fix above would have introduced the hole. A content line carrying
    # U+0085 followed by text shaped like "@@ -1,0 +900,3 @@" would then be parsed as a real
    # hunk header, fabricating 900 added lines that dilute diff coverage until a genuinely
    # uncovered line reads as a PASS. Found by adversarial review, not by the suite.
    for raw in proc.stdout.split("\n"):
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            current = None if target == "/dev/null" else target[2:] if target.startswith("b/") else target
        elif raw.startswith("@@") and current is not None:
            # @@ -old,cnt +new,cnt @@
            try:
                plus = raw.split("+", 1)[1].split(" ", 1)[0]
                start_s, _, count_s = plus.partition(",")
                start = int(start_s)
                count = int(count_s) if count_s else 1
            except (IndexError, ValueError):
                continue
            for offset in range(count):
                added.setdefault(current, set()).add(start + offset)
    return added


def untracked_files_under_source(root: Path, config: dict) -> list[str]:
    """Untracked files beneath the measured source roots (posix, sorted).

    `git ls-files --others --exclude-standard` lists exactly what `git diff` cannot
    see. Scoped to the configured source roots so a stray scratch file elsewhere
    does not cry wolf. Failures return [] -- this feeds a WARN, and inventing a
    warning from a broken probe would train people to ignore the real one.
    """
    sources = [str(s) for s in (config.get("source") or []) if str(s).strip()]
    if not sources:
        return []
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "--others",
             "--exclude-standard", "--", *sources],
            cwd=root,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return []
    if proc.stdout is None:  # reader-thread decode failure arrives as None (AGENTS 5.5.1)
        return []
    return sorted(line.strip() for line in proc.stdout.split("\n") if line.strip())


def compute_diff_coverage(
    added: dict[str, set[int]], report: CoverageReport
) -> tuple[int, int, list[str]]:
    """Intersect added lines with executable/covered lines. Returns (covered, total, uncovered_labels)."""
    covered = 0
    total = 0
    uncovered: list[str] = []
    for path, lines in added.items():
        fc = report.files.get(path)
        if fc is None:
            continue  # not a measured source file (docs, config, tests excluded from source)
        for number in sorted(lines):
            if number not in fc.executable:
                continue  # blank line, comment, or non-executable
            total += 1
            if number in fc.covered:
                covered += 1
            else:
                uncovered.append(f"{path}:{number}")
    return covered, total, uncovered


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def load_baseline(root: Path, config: dict) -> dict:
    path = root / str(config["baseline_file"])
    if not path.is_file():
        return {"line_pct": None, "branch_pct": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return {"line_pct": None, "branch_pct": None}
    return data if isinstance(data, dict) else {"line_pct": None, "branch_pct": None}


def write_baseline(root: Path, config: dict, report: CoverageReport, *, force: bool) -> tuple[bool, str]:
    """Persist current percentages as the ratchet floor. Refuses to lower unless forced."""
    path = root / str(config["baseline_file"])
    existing = load_baseline(root, config)
    old_line = existing.get("line_pct")
    if isinstance(old_line, (int, float)) and report.line_pct < old_line and not force:
        return False, (
            f"refusing to LOWER the baseline ({report.line_pct:.2f}% < {old_line:.2f}%); "
            "pass --force if the drop is intentional"
        )
    payload = {
        "line_pct": round(report.line_pct, 2),
        "branch_pct": round(report.branch_pct, 2),
        "updated": datetime.now(UTC).strftime("%Y-%m-%d"),
        "note": existing.get(
            "note",
            "Ratchet floor for coverage_gate.py (AGENTS 5.7). Raise with --update-baseline.",
        ),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return True, f"baseline set to line={payload['line_pct']}% branch={payload['branch_pct']}%"


# ---------------------------------------------------------------------------
# pytest runner
# ---------------------------------------------------------------------------


def run_pytest_with_coverage(root: Path, config: dict) -> int:
    """Run the full suite under coverage, emitting the Cobertura XML the gate reads.

    Returns pytest's exit code. Test failures (non-zero) are surfaced, not hidden:
    a red suite is its own signal and the caller reports it.
    """
    xml_rel = str(config["coverage_xml"])
    (root / xml_rel).parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "pytest"]
    for src in config["source"]:
        cmd.append(f"--cov={src}")
    if config.get("branch", True):
        cmd.append("--cov-branch")
    cmd.append(f"--cov-report=xml:{xml_rel}")
    proc = subprocess.run(cmd, cwd=root)
    return proc.returncode


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate(root: Path, config: dict, report: CoverageReport) -> GateResult:
    result = GateResult(line_pct=report.line_pct, branch_pct=report.branch_pct)

    # 1. Diff coverage -- the primary gate.
    min_diff = float(config["min_diff_coverage_pct"])
    added = git_added_lines(root, str(config["diff_base"]))
    if added is None:
        result.note(
            "WARN",
            f"cannot resolve diff base '{config['diff_base']}' (fresh repo or shallow "
            "checkout); diff coverage not evaluated this run",
        )
    else:
        covered, total, uncovered = compute_diff_coverage(added, report)
        result.diff_covered, result.diff_total = covered, total
        if total == 0:
            # Zero can mean two things this arm could not previously distinguish: the
            # commit legitimately changed no measured source, or every changed file is
            # UNTRACKED -- git diff cannot see untracked files, so a pre-commit gate run
            # congratulates you on coverage it never looked at, with output character-
            # for-character identical to the legitimate case (AGENTS 4.1 axis 7).
            untracked = untracked_files_under_source(root, config)
            if untracked:
                shown = ", ".join(untracked[:5])
                more = "" if len(untracked) <= 5 else f" (+{len(untracked) - 5} more)"
                result.note(
                    "WARN",
                    f"diff coverage measured NOTHING: {len(untracked)} changed file(s) under "
                    f"measured source are untracked, invisible to git diff: {shown}{more}. "
                    "Commit them and re-run, or this PASS measured nothing.",
                )
            else:
                result.note("INFO", "no new/changed executable lines in measured source")
        else:
            result.diff_pct = covered / total * 100.0
            if result.diff_pct + 1e-9 < min_diff:
                result.failed = True
                shown = ", ".join(uncovered[:10])
                more = "" if len(uncovered) <= 10 else f" (+{len(uncovered) - 10} more)"
                result.note(
                    "FAIL",
                    f"diff coverage {result.diff_pct:.1f}% < {min_diff:.0f}% floor; "
                    f"uncovered new lines: {shown}{more}",
                )
            else:
                result.note("INFO", f"diff coverage {result.diff_pct:.1f}% >= {min_diff:.0f}% floor")

    # 2. Ratchet -- total coverage may not regress below the tracked baseline.
    baseline = load_baseline(root, config)
    base_line = baseline.get("line_pct")
    result.baseline_line_pct = base_line if isinstance(base_line, (int, float)) else None
    base_branch = baseline.get("branch_pct")
    result.baseline_branch_pct = base_branch if isinstance(base_branch, (int, float)) else None
    tolerance = float(config["ratchet_tolerance_pct"])
    if result.baseline_line_pct is None:
        result.note("INFO", "no baseline floor set yet; ratchet skipped (seed with --update-baseline)")
    elif report.line_pct + tolerance + 1e-9 < result.baseline_line_pct:
        result.failed = True
        result.note(
            "FAIL",
            f"line coverage {report.line_pct:.2f}% dropped below baseline "
            f"{result.baseline_line_pct:.2f}% (tolerance {tolerance}%); coverage regressed",
        )
    else:
        result.note(
            "INFO",
            f"line coverage {report.line_pct:.2f}% vs baseline {result.baseline_line_pct:.2f}% (ok)",
        )

    # The BRANCH arm of the ratchet. Measured, printed and written to the baseline file
    # since the ratchet was adopted -- and compared to nothing, so the ratchet had one
    # arm. This is the arm that justifies branch coverage existing at all: line coverage
    # cannot see a change that keeps every line executed while removing a branch's
    # second arm, which is precisely the case AGENTS 4.1 axis 3 exists for.
    if result.baseline_branch_pct is None:
        result.note("INFO", "no branch baseline floor set yet; branch ratchet skipped")
    elif report.branch_pct + tolerance + 1e-9 < result.baseline_branch_pct:
        result.failed = True
        result.note(
            "FAIL",
            f"branch coverage {report.branch_pct:.2f}% dropped below baseline "
            f"{result.baseline_branch_pct:.2f}% (tolerance {tolerance}%); a branch lost "
            "an arm even if line coverage held",
        )
    else:
        result.note(
            "INFO",
            f"branch coverage {report.branch_pct:.2f}% vs baseline "
            f"{result.baseline_branch_pct:.2f}% (ok)",
        )
    return result


# ---------------------------------------------------------------------------
# Reporting and entry point
# ---------------------------------------------------------------------------


def print_report(result: GateResult, mode: str) -> None:
    print("Coverage gate (AGENTS 5.7)")
    print(f"Repo root: {REPO_ROOT}")
    print(f"Mode: {mode}")
    print()
    print(f"  line coverage   : {_fmt(result.line_pct)}")
    print(f"  branch coverage : {_fmt(result.branch_pct)}")
    if result.diff_total:
        print(f"  diff coverage   : {result.diff_covered}/{result.diff_total} = {_fmt(result.diff_pct)}")
    else:
        print("  diff coverage   : n/a (no measured new lines)")
    print(f"  baseline (line) : {_fmt(result.baseline_line_pct)}")
    # An arm that blocks but is invisible in the report is an arm nobody will
    # understand when it fires.
    print(f"  baseline (branch): {_fmt(result.baseline_branch_pct)}")
    print()
    for severity, text in result.messages:
        print(f"  {severity}: {text}")
    print()


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}%"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")

    parser = argparse.ArgumentParser(prog="coverage_gate", description=__doc__)
    parser.add_argument("--run", action="store_true", help="run the full pytest suite with coverage first")
    parser.add_argument("--update-baseline", action="store_true", dest="update_baseline")
    parser.add_argument("--force", action="store_true", help="allow --update-baseline to lower the floor")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    config = load_coverage_config(REPO_ROOT)
    mode = str(config["mode"]).lower()
    gating = mode == "gating"

    if args.run:
        code = run_pytest_with_coverage(REPO_ROOT, config)
        if code != 0:
            print(f"WARNING: pytest exited {code} (test failures or errors); coverage numbers may be partial")

    primary = str(config["coverage_xml"])
    extra = [str(p) for p in (config.get("extra_coverage_xml") or [])]
    report, missing, malformed = read_reports(REPO_ROOT, [primary, *extra])

    # The primary (backend/pytest) report is mandatory: its absence is the loud
    # failure. Extra reports (frontend) missing is a WARN, never a silent green.
    if primary in missing or primary in malformed:
        why = "not found" if primary in missing else "malformed XML"
        msg = f"primary coverage report {why} at {primary}; run with --run, or run pytest --cov ... first"
        if args.as_json:
            print(json.dumps({"error": msg, "mode": mode}, indent=2))
        else:
            print(f"Coverage gate (AGENTS 5.7)\nMode: {mode}\n\n  {'FAIL' if gating else 'WARN'}: {msg}\n")
        # Fail loudly in gating mode; advisory reports and passes (AGENTS 5.5.1).
        return 1 if gating else 0

    if args.update_baseline:
        ok, message = write_baseline(REPO_ROOT, config, report, force=args.force)
        print(f"{'OK' if ok else 'REFUSED'}: {message}")
        return 0 if ok else 1

    result = evaluate(REPO_ROOT, config, report)
    for rel in missing:
        result.note("WARN", f"extra coverage report not found at {rel}; that source was not measured this run")
    for rel in malformed:
        result.note("WARN", f"extra coverage report at {rel} is malformed XML; skipped")

    if args.as_json:
        print(
            json.dumps(
                {
                    "mode": mode,
                    "line_pct": result.line_pct,
                    "branch_pct": result.branch_pct,
                    "diff_covered": result.diff_covered,
                    "diff_total": result.diff_total,
                    "diff_pct": result.diff_pct,
                    "baseline_line_pct": result.baseline_line_pct,
                    "baseline_branch_pct": result.baseline_branch_pct,
                    "failed": result.failed,
                    "gating": gating,
                    "messages": [{"severity": s, "text": t} for s, t in result.messages],
                },
                indent=2,
            )
        )
    else:
        print_report(result, mode)
        verdict = "FAIL" if (result.failed and gating) else "PASS"
        if result.failed and not gating:
            verdict = "PASS (advisory: would FAIL if mode were 'gating')"
        print(f"Result: {verdict}")

    return 1 if (result.failed and gating) else 0


if __name__ == "__main__":
    sys.exit(main())
