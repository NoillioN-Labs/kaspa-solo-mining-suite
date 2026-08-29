"""Unit tests for scripts/utilities/coverage_gate.py (AGENTS 5.7).

The gate is the deterministic arm of AGENTS 4.1 axis 3. These tests pin the three
behaviours that make it trustworthy rather than theatrical:

  * diff coverage is computed against the ACTUAL executable lines in the report,
    not the raw diff (blank/comment lines must not count),
  * advisory mode NEVER blocks while gating mode fails loudly -- including when the
    coverage report is missing (a silent green there would be a latent incident), and
  * the diff is decoded with an EXPLICIT codec, so a real diff carrying bytes the
    Windows locale codec has no mapping for parses instead of crashing the gate.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "utilities"))

import coverage_gate  # noqa: E402

COBERTURA = """<?xml version="1.0" ?>
<coverage line-rate="0.66" branch-rate="0.5" branches-covered="1" branches-valid="2">
  <packages><package name="backend"><classes>
    <class filename="backend/core/logger.py">
      <lines>
        <line number="10" hits="1"/>
        <line number="11" hits="0"/>
        <line number="12" hits="3"/>
      </lines>
    </class>
  </classes></package></packages>
</coverage>
"""

# A second stack's report (e.g. frontend vitest cobertura) covering different files.
COBERTURA_FRONTEND = """<?xml version="1.0" ?>
<coverage branches-covered="3" branches-valid="4">
  <packages><package name="frontend"><classes>
    <class filename="frontend/src/App.tsx">
      <lines>
        <line number="1" hits="1"/>
        <line number="2" hits="1"/>
        <line number="3" hits="0"/>
      </lines>
    </class>
  </classes></package></packages>
</coverage>
"""


def _write_report(tmp_path: Path) -> Path:
    xml = tmp_path / "coverage.xml"
    xml.write_text(COBERTURA, encoding="utf-8")
    return xml


def test_parse_cobertura_derives_line_from_files_and_branch_from_counts(tmp_path: Path) -> None:
    report = coverage_gate.parse_cobertura(_write_report(tmp_path))
    assert report.line_pct == pytest.approx(200 / 3)  # 2 covered / 3 executable
    assert report.branch_pct == pytest.approx(50.0)  # 1 of 2 branches
    fc = report.files["backend/core/logger.py"]
    assert fc.executable == {10, 11, 12}
    assert fc.covered == {10, 12}


def test_read_reports_merges_multiple_sources(tmp_path: Path) -> None:
    """Backend + frontend Cobertura reports aggregate into one CoverageReport."""
    (tmp_path / "coverage.xml").write_text(COBERTURA, encoding="utf-8")
    (tmp_path / "frontend.xml").write_text(COBERTURA_FRONTEND, encoding="utf-8")
    merged, missing, malformed = coverage_gate.read_reports(tmp_path, ["coverage.xml", "frontend.xml"])
    assert (missing, malformed) == ([], [])
    # line: (2 + 2) covered / (3 + 3) executable = 4/6; branch: (1 + 3) / (2 + 4) = 4/6
    assert merged.line_pct == pytest.approx(4 / 6 * 100)
    assert merged.branch_pct == pytest.approx(4 / 6 * 100)
    assert set(merged.files) == {"backend/core/logger.py", "frontend/src/App.tsx"}


def test_read_reports_records_missing_without_false_zero(tmp_path: Path) -> None:
    (tmp_path / "coverage.xml").write_text(COBERTURA, encoding="utf-8")
    merged, missing, malformed = coverage_gate.read_reports(tmp_path, ["coverage.xml", "frontend.xml"])
    assert missing == ["frontend.xml"]  # recorded, not merged as 0%
    assert "backend/core/logger.py" in merged.files


def test_diff_coverage_counts_only_executable_lines(tmp_path: Path) -> None:
    report = coverage_gate.parse_cobertura(_write_report(tmp_path))
    # Added lines 10 (covered), 11 (uncovered), 99 (blank/non-executable -> ignored).
    added = {"backend/core/logger.py": {10, 11, 99}}
    covered, total, uncovered = coverage_gate.compute_diff_coverage(added, report)
    assert (covered, total) == (1, 2)  # line 99 excluded: not in the executable set
    assert uncovered == ["backend/core/logger.py:11"]


def test_missing_report_fails_loudly_only_when_gating(tmp_path: Path, monkeypatch) -> None:
    """A missing coverage report is a WARN+exit0 in advisory, ERROR+exit1 when gating."""
    monkeypatch.setattr(coverage_gate, "REPO_ROOT", tmp_path)

    monkeypatch.setattr(coverage_gate, "load_coverage_config",
                        lambda root: {**coverage_gate.DEFAULT_CONFIG, "mode": "advisory",
                                      "coverage_xml": "missing.xml"})
    assert coverage_gate.main([]) == 0  # advisory never blocks

    monkeypatch.setattr(coverage_gate, "load_coverage_config",
                        lambda root: {**coverage_gate.DEFAULT_CONFIG, "mode": "gating",
                                      "coverage_xml": "missing.xml"})
    assert coverage_gate.main([]) == 1  # gating fails loudly on a missing report


def test_uncovered_diff_lines_do_not_block_in_advisory(tmp_path: Path, monkeypatch) -> None:
    """New uncovered lines are a would-fail, but advisory mode still exits 0."""
    _write_report(tmp_path)
    monkeypatch.setattr(coverage_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(coverage_gate, "load_coverage_config",
                        lambda root: {**coverage_gate.DEFAULT_CONFIG, "mode": "advisory",
                                      "coverage_xml": "coverage.xml", "min_diff_coverage_pct": 90.0})
    # Force a diff with an uncovered executable line.
    monkeypatch.setattr(coverage_gate, "git_added_lines",
                        lambda root, base: {"backend/core/logger.py": {11}})
    config = coverage_gate.load_coverage_config(tmp_path)
    result = coverage_gate.evaluate(tmp_path, config, coverage_gate.parse_cobertura(tmp_path / "coverage.xml"))
    assert result.failed is True  # it WOULD fail
    assert coverage_gate.main([]) == 0  # ...but advisory mode does not block


def test_gating_blocks_on_uncovered_diff(tmp_path: Path, monkeypatch) -> None:
    _write_report(tmp_path)
    monkeypatch.setattr(coverage_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(coverage_gate, "load_coverage_config",
                        lambda root: {**coverage_gate.DEFAULT_CONFIG, "mode": "gating",
                                      "coverage_xml": "coverage.xml", "min_diff_coverage_pct": 90.0})
    monkeypatch.setattr(coverage_gate, "git_added_lines",
                        lambda root, base: {"backend/core/logger.py": {11}})
    assert coverage_gate.main([]) == 1


def test_unresolvable_diff_base_is_not_a_false_zero(tmp_path: Path, monkeypatch) -> None:
    """When the base ref can't be resolved, diff coverage is skipped, not scored 0%."""
    _write_report(tmp_path)
    monkeypatch.setattr(coverage_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(coverage_gate, "git_added_lines", lambda root, base: None)
    config = {**coverage_gate.DEFAULT_CONFIG, "coverage_xml": "coverage.xml"}
    result = coverage_gate.evaluate(tmp_path, config, coverage_gate.parse_cobertura(tmp_path / "coverage.xml"))
    assert result.diff_pct is None
    assert result.failed is False
    assert any(sev == "WARN" for sev, _ in result.messages)


# ---------------------------------------------------------------------------
# Diff decoding -- a REAL repo, because the defect is in HOW git is invoked
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> None:
    """Run git in *repo*, failing loudly. Bytes on purpose: the harness never decodes."""
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)


def _init_repo(repo: Path) -> Path:
    """A real repo with an identity, so `commit` works where no global one is set.

    gpgsign is forced OFF rather than merely left unset: a developer with global commit
    signing inherits it here and every `git commit` below dies with `gpg: signing failed`,
    exit 128 -- a failure about this machine's config, not about the code under test.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def test_git_added_lines_parses_a_diff_the_locale_codec_cannot_decode(tmp_path: Path) -> None:
    """A diff carrying bytes undefined in cp1252 must still parse (AGENTS 5.5.1).

    text=True decodes subprocess output with the LOCALE codec -- cp1252 on Windows, where
    0x81/0x8D/0x8F/0x90/0x9D are undefined. U+1F37E encodes to f0 9f 8d be, so byte three
    is 0x8D and the diff cannot be decoded at all.

    Where the decode fails is the part worth knowing, and it was measured by mutation
    rather than reasoned about: capture_output reads the pipes on READER THREADS, so the
    UnicodeDecodeError is raised in a thread and never reaches the caller. No `except`
    around the call can catch it; `proc.stdout` just arrives as None and the parser dies
    on it. See test_a_thread_swallowed_decode_becomes_cannot_compute for that half.

    The fixture must be an emoji. An em-dash (e2 80 94) is fully decodable in cp1252, so a
    test built on one passes against the UNFIXED code and proves nothing. A mocked
    subprocess proves nothing either: the defect is in the invocation, not the parsing.
    """
    repo = _init_repo(tmp_path / "repo")
    source = repo / "backend" / "doc.py"
    source.parent.mkdir(parents=True)
    source.write_text("BASE = 0\n", encoding="utf-8")
    _git(repo, "add", "--", "backend/doc.py")
    _git(repo, "commit", "-m", "base")

    # Two lines inserted at the top; the first carries 0x8D in its UTF-8 encoding.
    source.write_text('EMOJI = "\U0001F37E"\nVALUE = 1\nBASE = 0\n', encoding="utf-8")
    _git(repo, "commit", "-a", "-m", "insert two lines, one undecodable in cp1252")

    added = coverage_gate.git_added_lines(repo, "HEAD~1")
    assert added is not None, "a readable diff must not be reported as 'cannot compute'"
    assert added["backend/doc.py"] == {1, 2}


def test_file_content_cannot_fabricate_a_hunk_header(tmp_path: Path) -> None:
    """Decoding as UTF-8 makes U+0085 a `splitlines()` boundary. `split("\\n")` is what git means.

    This is the regression the encoding fix above would otherwise have INTRODUCED. Read as
    cp1252 those bytes were ordinary characters, so the locale decode was accidentally safe
    here; read as UTF-8, `str.splitlines()` breaks on U+0085, U+2028 and U+2029, none of which
    git uses to terminate a line. A content line carrying one, followed by text shaped like a
    hunk header, is then parsed AS a hunk header.

    The damage is not a crash, which is why it needs a test: the fabricated lines are added to
    the diff set, and any of them that the coverage report calls executable-and-covered dilute
    the percentage. One genuinely uncovered new line among 900 invented covered ones reads as a
    comfortable PASS -- a silent false green, the failure mode AGENTS 5.5.1 exists to forbid.
    """
    repo = _init_repo(tmp_path / "repo")
    source = repo / "backend" / "m.py"
    source.parent.mkdir(parents=True)
    source.write_text("BASE = 0\n", encoding="utf-8")
    _git(repo, "add", "--", "backend/m.py")
    _git(repo, "commit", "-m", "base")

    # ONE added line. U+0085 (NEL) mid-line, then something shaped exactly like a hunk header.
    source.write_text("REAL = 1\u0085@@ -1,0 +900,3 @@\nBASE = 0\n", encoding="utf-8")
    _git(repo, "commit", "-a", "-m", "one added line that looks like two")

    added = coverage_gate.git_added_lines(repo, "HEAD~1")

    assert added == {"backend/m.py": {1}}, (
        "content after a U+0085 must stay content -- a fabricated hunk header silently "
        f"inflates the added-line set and dilutes diff coverage to a false PASS: {added}"
    )


def test_added_lines_in_a_non_ascii_filename_are_not_silently_dropped(tmp_path: Path) -> None:
    """git C-escapes non-ASCII paths unless core.quotepath=false, and an escaped path never
    matches the Cobertura filename -- so the file's added lines vanish from diff coverage
    without any error. An emoji in a FILENAME, not just in a diff body."""
    repo = _init_repo(tmp_path / "repo")
    source = repo / "backend" / "caf\u00e9.py"
    source.parent.mkdir(parents=True)
    source.write_text("BASE = 0\n", encoding="utf-8")
    _git(repo, "add", "--", "backend/caf\u00e9.py")
    _git(repo, "commit", "-m", "base")

    source.write_text("VALUE = 1\nBASE = 0\n", encoding="utf-8")
    _git(repo, "commit", "-a", "-m", "add a line")

    added = coverage_gate.git_added_lines(repo, "HEAD~1")

    assert added is not None
    assert "backend/caf\u00e9.py" in added, (
        f"a C-escaped path can never match a Cobertura filename, so its lines are dropped: {added}"
    )


def test_an_undecodable_byte_is_replaced_rather_than_crashing(tmp_path: Path, monkeypatch) -> None:
    """The half of the decode that `errors="replace"` exists for, which no fixture reaches.

    A real git diff of UTF-8 files is valid UTF-8, so the emoji test above exercises
    `encoding=` and never `errors=`. What `errors="replace"` actually guards is output that is
    not valid UTF-8 at all -- a file committed in some other encoding. Without it that is a
    hard `UnicodeDecodeError`, i.e. the same class of crash the whole change removes, just
    arriving from the other direction.
    """
    def _invalid_utf8(*args, **kwargs):
        if "rev-parse" in args[0]:  # base ref resolves; only the diff is under test
            return type("P", (), {"stdout": ""})()
        # 0xFF is not valid UTF-8 in any position. Decode it exactly as the module asks
        # subprocess to, so the assertion is about the module's OWN encoding arguments.
        payload = b'+++ b/backend/m.py\n@@ -1,0 +1,1 @@\n+X = "\xff"\n'
        return type("P", (), {
            "stdout": payload.decode(kwargs["encoding"], errors=kwargs["errors"])
        })()

    monkeypatch.setattr(coverage_gate.subprocess, "run", _invalid_utf8)

    assert coverage_gate.git_added_lines(tmp_path, "HEAD~1") == {"backend/m.py": {1}}


def test_a_thread_swallowed_decode_becomes_cannot_compute(monkeypatch, tmp_path: Path) -> None:
    """stdout=None is a REACHABLE state, and it must not crash the gate.

    Mocking is right here and wrong in the test above, for opposite reasons. There the
    defect was in how git is invoked, so only a real subprocess could reproduce it. Here
    the subject is what this function does with a result it cannot influence: on Windows a
    decode that fails on a reader thread is swallowed whole, leaving stdout None with no
    exception anywhere the caller can see. Recreating that for real needs a mid-flight
    thread failure; recreating the RESULT is exact and costs nothing.

    Without the guard this raises AttributeError deep in the parser -- an error naming
    neither git nor encoding, which is exactly how long the origin project's debugging took.
    """
    class _Swallowed:
        stdout = None

    monkeypatch.setattr(coverage_gate.subprocess, "run", lambda *a, **k: _Swallowed())

    assert coverage_gate.git_added_lines(tmp_path, "HEAD~1") is None


# ---------------------------------------------------------------------------
# Source-root resolution -- pack: coverage_gate_source_root_paths_260816_1700
#
# The diff arm is the gate's PRIMARY check ("every new/changed executable line must
# be covered") and it had never matched a single file. Cobertura writes
# `class/@filename` relative to whichever source root matched the file, not relative
# to the repo -- so `--cov=backend` emits `ingest.py` while `git diff` emits
# `backend/ingest.py`. Every lookup missed, every added line was skipped by a branch
# whose comment explained it away as "docs, config, tests", and the gate reported
# `diff coverage: n/a (no measured new lines)` and PASSED.
#
# Measured in this repo before the fix: covered=0 total=0. After: total=2.
# ---------------------------------------------------------------------------


def _write_two_root_report(tmp_path: Path) -> Path:
    """A report shaped the way coverage.py actually writes one.

    Two <source> roots and BARE filenames. A hand-written fixture using repo-relative
    filenames passes against the defect and proves nothing, which is why the files
    below are really created on disk -- the resolution is an on-disk check.
    """
    (tmp_path / "backend").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "utilities").mkdir(parents=True, exist_ok=True)
    (tmp_path / "backend" / "ingest.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "scripts" / "utilities" / "tool.py").write_text("x\n", encoding="utf-8")

    xml = f"""<?xml version="1.0" ?>
<coverage branches-covered="1" branches-valid="2" line-rate="0.5">
  <sources>
    <source>{tmp_path / "backend"}</source>
    <source>{tmp_path / "scripts" / "utilities"}</source>
  </sources>
  <packages><package name="."><classes>
    <class filename="ingest.py"><lines>
      <line number="1" hits="1"/><line number="2" hits="0"/>
    </lines></class>
    <class filename="tool.py"><lines>
      <line number="1" hits="1"/>
    </lines></class>
  </classes></package></packages>
</coverage>
"""
    path = tmp_path / "coverage.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def test_diff_coverage_is_not_a_silent_no_op_against_a_real_report(tmp_path: Path) -> None:
    """`git diff` yields backend/ingest.py; the report keys it as ingest.py."""
    report = coverage_gate.parse_cobertura(_write_two_root_report(tmp_path), repo_root=tmp_path)
    covered, total, uncovered = coverage_gate.compute_diff_coverage(
        {"backend/ingest.py": {1, 2}}, report
    )
    assert (covered, total) == (1, 2), "the added lines must be MEASURED, not skipped"
    assert uncovered == ["backend/ingest.py:2"]


def test_both_source_roots_resolve_and_stay_distinguishable(tmp_path: Path) -> None:
    """Two roots flatten into the same package; only the on-disk probe separates them."""
    report = coverage_gate.parse_cobertura(_write_two_root_report(tmp_path), repo_root=tmp_path)
    assert "backend/ingest.py" in report.files
    assert "scripts/utilities/tool.py" in report.files


def test_a_report_with_no_sources_element_is_left_untouched(tmp_path: Path) -> None:
    """Frontend vitest Cobertura has no <sources>; its keys are already repo-relative."""
    xml = """<?xml version="1.0" ?>
<coverage branches-covered="0" branches-valid="0">
  <packages><package name="."><classes>
    <class filename="src/app.ts"><lines><line number="1" hits="1"/></lines></class>
  </classes></package></packages>
</coverage>
"""
    path = tmp_path / "frontend.xml"
    path.write_text(xml, encoding="utf-8")
    report = coverage_gate.parse_cobertura(path, repo_root=tmp_path)
    assert "src/app.ts" in report.files, "an untouched key must not gain a prefix"


def test_a_foreign_source_root_degrades_rather_than_guessing(tmp_path: Path) -> None:
    """A report written on another machine must not be force-fitted to this repo."""
    xml = """<?xml version="1.0" ?>
<coverage branches-covered="0" branches-valid="0">
  <sources><source>/somewhere/else/entirely/nope</source></sources>
  <packages><package name="."><classes>
    <class filename="mystery.py"><lines><line number="1" hits="1"/></lines></class>
  </classes></package></packages>
</coverage>
"""
    path = tmp_path / "foreign.xml"
    path.write_text(xml, encoding="utf-8")
    report = coverage_gate.parse_cobertura(path, repo_root=tmp_path)
    assert "mystery.py" in report.files, "unplaceable roots must degrade to the old behaviour"


def test_an_ambiguous_filename_under_two_roots_is_left_alone(tmp_path: Path) -> None:
    """Attributing coverage to the WRONG file is worse than leaving it unmatched."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    xml = f"""<?xml version="1.0" ?>
<coverage branches-covered="0" branches-valid="0">
  <sources><source>{tmp_path / "a"}</source><source>{tmp_path / "b"}</source></sources>
  <packages><package name="."><classes>
    <class filename="ghost.py"><lines><line number="1" hits="1"/></lines></class>
  </classes></package></packages>
</coverage>
"""
    path = tmp_path / "ambiguous.xml"
    path.write_text(xml, encoding="utf-8")
    report = coverage_gate.parse_cobertura(path, repo_root=tmp_path)
    assert "ghost.py" in report.files, "neither root locates it, so neither may claim it"


def test_parse_without_a_repo_root_keeps_filenames_verbatim(tmp_path: Path) -> None:
    """The default call shape must not change behaviour for existing callers."""
    report = coverage_gate.parse_cobertura(_write_two_root_report(tmp_path))
    assert "ingest.py" in report.files


# ---------------------------------------------------------------------------
# The BRANCH arm of the ratchet -- pack: coverage_gate_unenforced_branch_arm_260816_1700
#
# `baseline_branch_pct` was loaded in evaluate() and never read again: measured,
# printed, written to the baseline file, and compared to nothing. The ratchet had one
# arm. This is the arm that justifies branch coverage existing at all -- line coverage
# cannot see a change that keeps every line executed while removing a branch's second
# arm, which is exactly the case AGENTS 4.1 axis 3 exists for.
# ---------------------------------------------------------------------------


def _baseline_config(tmp_path: Path, line_pct: float, branch_pct: float | None) -> dict:
    payload: dict = {"line_pct": line_pct}
    if branch_pct is not None:
        payload["branch_pct"] = branch_pct
    (tmp_path / "baseline.json").write_text(json.dumps(payload), encoding="utf-8")
    return {
        **coverage_gate.DEFAULT_CONFIG,
        "coverage_xml": "coverage.xml",
        "baseline_file": "baseline.json",
        "ratchet_tolerance_pct": 0.5,
    }


def test_the_branch_ratchet_arm_actually_blocks(tmp_path: Path, monkeypatch) -> None:
    """The report measures branch_pct = 50.0; a 90% floor must FAIL."""
    _write_report(tmp_path)
    monkeypatch.setattr(coverage_gate, "git_added_lines", lambda root, base: {})
    config = _baseline_config(tmp_path, line_pct=1.0, branch_pct=90.0)
    result = coverage_gate.evaluate(tmp_path, config, coverage_gate.parse_cobertura(tmp_path / "coverage.xml"))
    assert result.failed is True, "a branch regression must block, not merely be printed"
    assert any(
        sev == "FAIL" and "branch coverage" in text for sev, text in result.messages
    ), f"the failure must NAME the branch arm: {result.messages}"


def test_the_branch_arm_does_not_fire_at_the_floor(tmp_path: Path, monkeypatch) -> None:
    """Equal to the baseline is not a regression -- an arm that always fires is noise."""
    _write_report(tmp_path)
    monkeypatch.setattr(coverage_gate, "git_added_lines", lambda root, base: {})
    config = _baseline_config(tmp_path, line_pct=1.0, branch_pct=50.0)
    result = coverage_gate.evaluate(tmp_path, config, coverage_gate.parse_cobertura(tmp_path / "coverage.xml"))
    assert result.failed is False


def test_an_unseeded_branch_baseline_skips_rather_than_failing(tmp_path: Path, monkeypatch) -> None:
    """No floor yet is a legitimate state; it must say so, not fail and not pass silently."""
    _write_report(tmp_path)
    monkeypatch.setattr(coverage_gate, "git_added_lines", lambda root, base: {})
    config = _baseline_config(tmp_path, line_pct=1.0, branch_pct=None)
    result = coverage_gate.evaluate(tmp_path, config, coverage_gate.parse_cobertura(tmp_path / "coverage.xml"))
    assert result.failed is False
    assert any("branch ratchet skipped" in text for _, text in result.messages)


def test_the_branch_arm_catches_what_the_line_arm_cannot(tmp_path: Path, monkeypatch) -> None:
    """The whole justification for the arm, stated as a test.

    Line coverage sits comfortably above its floor while branch coverage has collapsed
    -- a branch lost an arm with every line still executed. Only the branch arm sees it.
    """
    _write_report(tmp_path)
    monkeypatch.setattr(coverage_gate, "git_added_lines", lambda root, base: {})
    config = _baseline_config(tmp_path, line_pct=10.0, branch_pct=95.0)
    result = coverage_gate.evaluate(tmp_path, config, coverage_gate.parse_cobertura(tmp_path / "coverage.xml"))
    # startswith, not `in`: the branch failure's own text ends "...even if line coverage
    # held", so a substring match reports the branch arm as the line arm and the test
    # passes for the wrong reason.
    line_failed = any(sev == "FAIL" and text.startswith("line coverage") for sev, text in result.messages)
    branch_failed = any(sev == "FAIL" and text.startswith("branch coverage") for sev, text in result.messages)
    assert not line_failed, "line coverage is above its floor -- the line arm sees nothing"
    assert branch_failed and result.failed is True


# ---------------------------------------------------------------------------
# The silent-zero arm -- pack: coverage_gate_silent_zero_diff_260820_1610
#
# git diff cannot see untracked files, so a pre-commit gate run reported
# "n/a (no measured new lines)" + PASS with output character-for-character
# identical to a commit that genuinely touched no measured source.
# ---------------------------------------------------------------------------


def _evaluate_with_zero_diff(tmp_path: Path, monkeypatch, untracked: list[str]):
    _write_report(tmp_path)
    monkeypatch.setattr(coverage_gate, "git_added_lines", lambda root, base: {})
    monkeypatch.setattr(
        coverage_gate, "untracked_files_under_source", lambda root, config: untracked
    )
    config = {**coverage_gate.DEFAULT_CONFIG, "coverage_xml": "coverage.xml"}
    return coverage_gate.evaluate(
        tmp_path, config, coverage_gate.parse_cobertura(tmp_path / "coverage.xml")
    )


def test_zero_diff_with_untracked_source_files_warns_and_names_them(
    tmp_path: Path, monkeypatch
) -> None:
    result = _evaluate_with_zero_diff(tmp_path, monkeypatch, ["backend/new_module.py"])
    warns = [t for s, t in result.messages if s == "WARN"]
    assert any("measured NOTHING" in t and "backend/new_module.py" in t for t in warns), (
        f"the gate must say it measured nothing and NAME the invisible file: {result.messages}"
    )


def test_zero_diff_with_no_untracked_files_stays_a_calm_info(
    tmp_path: Path, monkeypatch
) -> None:
    """The legitimate case (docs commit) must not cry wolf."""
    result = _evaluate_with_zero_diff(tmp_path, monkeypatch, [])
    assert any(
        s == "INFO" and "no new/changed executable lines" in t for s, t in result.messages
    )
    assert not any("measured NOTHING" in t for _s, t in result.messages)


def test_untracked_probe_is_scoped_to_source_roots(tmp_path: Path) -> None:
    """A stray scratch file OUTSIDE the measured roots must not appear."""
    import subprocess as sp

    sp.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "inside.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("x\n", encoding="utf-8")
    got = coverage_gate.untracked_files_under_source(tmp_path, {"source": ["backend"]})
    assert got == ["backend/inside.py"]


def test_untracked_probe_fails_toward_silence_not_invented_warnings(tmp_path: Path) -> None:
    """Not a git repo -> [] -- a warning from a broken probe trains people to ignore it."""
    assert coverage_gate.untracked_files_under_source(tmp_path, {"source": ["backend"]}) == []
