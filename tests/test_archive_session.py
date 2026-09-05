"""Unit tests for scripts/utilities/archive_session.py.

Covers the transcript-to-project matching filter (wrong-transcript
confidentiality guard) and the sweep staging pathspec logic (staging the OLD
path of a moved tracked file so its deletion is not left unstaged).
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "utilities"))

import archive_session  # noqa: E402

# ---------------------------------------------------------------------------
# Transcript matching filter
# ---------------------------------------------------------------------------

def _make_transcript(brain_dir: Path, conv_id: str, text: str, mtime_offset: int) -> Path:
    """Create brain/<conv_id>/.system_generated/logs/transcript.jsonl with the given text."""
    logs_dir = brain_dir / conv_id / ".system_generated" / "logs"
    logs_dir.mkdir(parents=True)
    transcript = logs_dir / "transcript.jsonl"
    transcript.write_text(text, encoding="utf-8")
    stamp = time.time() + mtime_offset
    os.utime(transcript, (stamp, stamp))
    return transcript


def test_transcript_references_project(tmp_path: Path) -> None:
    matching = tmp_path / "match.jsonl"
    matching.write_text(
        '{"content": "Editing D:\\\\Apps\\\\my-project\\\\scripts\\\\run.py"}\n',
        encoding="utf-8",
    )
    non_matching = tmp_path / "nomatch.jsonl"
    non_matching.write_text('{"content": "Working on other-client-repo"}\n', encoding="utf-8")

    assert archive_session.transcript_references_project(matching, "my-project") is True
    assert archive_session.transcript_references_project(non_matching, "my-project") is False
    # Case-insensitive match
    assert archive_session.transcript_references_project(matching, "My-Project") is True


def test_find_active_transcript_prefers_matching_over_newest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The newest transcript belongs to another project; the older one that
    references this project must win."""
    brain = tmp_path / "brain"
    older_matching = _make_transcript(
        brain, "conv-this-project", '{"content": "path/to/my-project/file.py"}\n', mtime_offset=-100
    )
    _make_transcript(
        brain, "conv-other-client", '{"content": "path/to/other-client/file.py"}\n', mtime_offset=0
    )
    monkeypatch.setattr(archive_session, "candidate_brain_dirs", lambda: [brain])

    found = archive_session.find_active_transcript("my-project")
    assert found == older_matching


def test_find_active_transcript_skips_when_unmatched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    brain = tmp_path / "brain"
    _make_transcript(brain, "conv-other", '{"content": "unrelated repo"}\n', mtime_offset=0)
    monkeypatch.setattr(archive_session, "candidate_brain_dirs", lambda: [brain])

    assert archive_session.find_active_transcript("my-project") is None
    out = capsys.readouterr().out
    assert "[WARN]" in out
    assert "my-project" in out


def test_find_active_transcript_allow_unmatched_returns_newest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    brain = tmp_path / "brain"
    _make_transcript(brain, "conv-older", '{"content": "unrelated A"}\n', mtime_offset=-100)
    newest = _make_transcript(brain, "conv-newer", '{"content": "unrelated B"}\n', mtime_offset=0)
    monkeypatch.setattr(archive_session, "candidate_brain_dirs", lambda: [brain])

    found = archive_session.find_active_transcript("my-project", allow_unmatched=True)
    assert found == newest


# ---------------------------------------------------------------------------
# Sweep staging pathspec logic (deletion at the OLD path must be staged)
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")


def test_run_git_add_stages_deletion_of_moved_tracked_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    docs = repo / "docs"
    archive = docs / "archive"
    archive.mkdir(parents=True)
    old_path = docs / "notes_260101_1200.md"
    old_path.write_text("swept content\n", encoding="utf-8")
    _git(repo, "add", "--", "docs/notes_260101_1200.md")
    _git(repo, "commit", "-m", "add tracked note")

    # Simulate the sweep: move the tracked file into archive/
    new_path = archive / "notes_260101_1200.md"
    old_path.rename(new_path)

    ok = archive_session.run_git_add(repo, [new_path, old_path])
    assert ok is True

    status = _git(repo, "status", "--porcelain")
    lines = [line for line in status.splitlines() if line.strip()]
    # Everything must be staged: no line may report unstaged worktree changes
    # (second status column) - in particular no unstaged deletion " D".
    assert lines, "expected staged changes in git status"
    for line in lines:
        assert line[1] == " ", f"unstaged change left behind: {line!r}"
    # The move is recorded either as a rename or as add + delete.
    joined = "\n".join(lines)
    assert "notes_260101_1200.md" in joined
    assert not any(line.startswith(" D") for line in lines)


def test_run_git_add_skips_missing_untracked_paths(tmp_path: Path) -> None:
    """A never-tracked, no-longer-existing path (e.g. a skipped chat backup)
    must not break staging of the other paths."""
    repo = tmp_path / "repo"
    _init_repo(repo)

    real_file = repo / "kept.md"
    real_file.write_text("hello\n", encoding="utf-8")
    ghost = repo / "docs" / "chat_backup_never_created.md"

    ok = archive_session.run_git_add(repo, [real_file, ghost])
    assert ok is True

    status = _git(repo, "status", "--porcelain")
    assert "A  kept.md" in status
    assert "chat_backup_never_created" not in status


# ---------------------------------------------------------------------------
# Session-log placement (agent-written log is authoritative; stub is fallback)
# ---------------------------------------------------------------------------

def _outcomes() -> "archive_session.RunOutcomes":
    return archive_session.RunOutcomes()


def test_place_session_log_prefers_handwritten(tmp_path: Path) -> None:
    """An agent-written docs/sessions/session_<stamp>.md is moved to archive
    verbatim; no maintenance stub is generated over it."""
    root = tmp_path
    sessions = root / "docs" / "sessions"
    sessions.mkdir(parents=True)
    handwritten = sessions / "session_260101_1200.md"
    handwritten.write_text("# Real session record\n", encoding="utf-8")
    dest = sessions / "archive" / "session_260101_1200.md"

    archive_session.place_session_log(root, dest, "260101_1200", _outcomes())

    assert not handwritten.exists()
    assert dest.read_text(encoding="utf-8") == "# Real session record\n"


def test_place_session_log_handwritten_wins_over_existing_stub(tmp_path: Path) -> None:
    """If a stub already landed in archive (e.g. a prior run), the handwritten
    log replaces it rather than colliding on the sweep."""
    root = tmp_path
    sessions = root / "docs" / "sessions"
    archive_dir = sessions / "archive"
    archive_dir.mkdir(parents=True)
    (sessions / "session_260101_1200.md").write_text("# Real\n", encoding="utf-8")
    dest = archive_dir / "session_260101_1200.md"
    dest.write_text("# Stub\n", encoding="utf-8")

    archive_session.place_session_log(root, dest, "260101_1200", _outcomes())

    assert dest.read_text(encoding="utf-8") == "# Real\n"
    assert not (sessions / "session_260101_1200.md").exists()


def test_place_session_log_skips_when_archive_copy_exists(tmp_path: Path) -> None:
    """No handwritten log + an existing archive log for the stamp: leave it alone."""
    root = tmp_path
    archive_dir = root / "docs" / "sessions" / "archive"
    archive_dir.mkdir(parents=True)
    dest = archive_dir / "session_260101_1200.md"
    dest.write_text("# Existing\n", encoding="utf-8")

    archive_session.place_session_log(root, dest, "260101_1200", _outcomes())

    assert dest.read_text(encoding="utf-8") == "# Existing\n"


def test_place_session_log_falls_back_to_stub(tmp_path: Path) -> None:
    """Bare archiver run (no session log anywhere) still produces a log."""
    root = tmp_path
    dest = root / "docs" / "sessions" / "archive" / "session_260101_1200.md"

    archive_session.place_session_log(root, dest, "260101_1200", _outcomes())

    assert dest.is_file()
    assert "Session Maintenance" in dest.read_text(encoding="utf-8")


def test_find_agent_session_log_ignores_stamp(tmp_path: Path) -> None:
    """The agent's log is found by shape, not by the archive run's stamp."""
    sessions = tmp_path / "docs" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "session_260712_1144.md").write_text("# Real session\n", encoding="utf-8")

    found = archive_session.find_agent_session_log(tmp_path)

    assert found is not None
    assert found.name == "session_260712_1144.md"


def test_place_session_log_no_duplicate_stub_when_stamps_differ(tmp_path: Path) -> None:
    """The real-world case: the agent writes session_<T1>.md mid-session, the archiver
    runs later under stamp T2 and the sweep has already moved the log into archive/.

    The old exact-stamp check looked in the (now-emptied) sessions root, missed the real
    log, and wrote a stub beside it -- two logs for one session. Every prior test used a
    single stamp for both, so none of them caught it.
    """
    root = tmp_path
    sessions = root / "docs" / "sessions"
    archive_dir = sessions / "archive"
    archive_dir.mkdir(parents=True)

    agent_log = sessions / "session_260712_1144.md"
    agent_log.write_text("# Real session record\n", encoding="utf-8")

    # Spotted before the sweep, then relocated by it (as the real sweep does).
    spotted = archive_session.find_agent_session_log(root)
    agent_log.rename(archive_dir / agent_log.name)

    dest = archive_dir / "session_260712_1416.md"  # the archive run's own stamp
    placed = archive_session.place_session_log(root, dest, "260712_1416", _outcomes(), spotted)

    assert not dest.exists(), "a duplicate maintenance stub was written beside the real log"
    assert placed is not None
    assert placed.name == "session_260712_1144.md"
    assert placed.read_text(encoding="utf-8") == "# Real session record\n"


# ---------------------------------------------------------------------------
# Chat-backup collision + live-session tail (found by Expert tippers, 2026-07-28)
#
# Both defects are SILENT and they masked each other: the fall-through made the
# archiver look healthy because it found *a* transcript and wrote *a* backup,
# while dropping half the intended conversation and clobbering another.
#
# Prior art: archiver_session_log_collision_260712_1215 fixed this collision class
# for the SESSION LOG (place_session_log guards on dest_path.exists()). The CHAT
# BACKUP path was never covered.
# ---------------------------------------------------------------------------


def _claude_transcript(path: Path, conv_id: str, texts: list[str]) -> Path:
    """Minimal Claude Code JSONL transcript with a given conversation id."""
    import json

    lines = []
    for t in texts:
        lines.append(json.dumps({
            "sessionId": conv_id,
            "cwd": "D:/whatever",
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": t}]},
        }))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_same_minute_backups_do_not_destroy_each_other(tmp_path: Path) -> None:
    """DATA LOSS: two runs in the same minute built the same filename and the
    second silently overwrote the first -- both printing '[OK] Chat backup created'.

    Observed live: an Antigravity conversation archived at 19:48 was destroyed
    seconds later by a Claude conversation archived at the same 19:48 stamp.
    """
    archive = tmp_path / "docs" / "chat_logs" / "archive"
    archive.mkdir(parents=True)
    stamp = "260728_1948"

    first = _claude_transcript(tmp_path / "a.jsonl", "conv-AAA", ["first conversation"])
    second = _claude_transcript(tmp_path / "b.jsonl", "conv-BBB", ["second conversation"])
    dest = archive / f"chat_backup_{stamp}.md"

    archive_session.generate_chat_backup(first, dest, stamp, "conv-AAA", "claude")
    archive_session.generate_chat_backup(second, dest, stamp, "conv-BBB", "claude")

    surviving = sorted(archive.glob("chat_backup_*.md"))
    blob = "\n".join(p.read_text(encoding="utf-8") for p in surviving)
    assert "conv-AAA" in blob, (
        f"the first conversation was destroyed; only {[p.name for p in surviving]} survive"
    )
    assert "conv-BBB" in blob, "the second conversation was not archived"


def test_active_conversation_is_not_skipped_by_the_already_archived_guard(tmp_path: Path) -> None:
    """Archiving mid-session must not strand the rest of that session.

    The guard exists to stop a stale IDE conversation being re-filed under a fresh
    stamp. But it assumed archiving happens at the END: archive at 19:26, keep
    talking, archive again at 19:48, and the second run skipped the live
    conversation and archived an unrelated one instead.
    """
    archive = tmp_path / "docs" / "chat_logs" / "archive"
    archive.mkdir(parents=True)
    transcript = _claude_transcript(tmp_path / "live.jsonl", "conv-LIVE", ["first half"])
    backup = archive / "chat_backup_260728_1926.md"
    backup.write_text(
        "# Chat Backup\n\n**Conversation ID:** conv-LIVE\n\nfirst half\n", encoding="utf-8"
    )

    archived_at = datetime(2026, 7, 28, 19, 26).timestamp()

    # Archived and untouched since -> genuinely finished. Must still be skipped, or
    # the 260711 bug returns (a stale conversation re-filed under a fresh stamp).
    os.utime(transcript, (archived_at - 60, archived_at - 60))
    assert archive_session.transcript_already_archived("conv-LIVE", tmp_path, transcript) is True

    # The session continues: the transcript grows after that backup was written.
    os.utime(transcript, (archived_at + 60, archived_at + 60))
    assert archive_session.transcript_already_archived("conv-LIVE", tmp_path, transcript) is False, (
        "a transcript that grew since its backup holds content that backup does not; "
        "skipping it strands the tail of the session"
    )

    # No transcript to compare against -> stay conservative and treat as archived.
    assert archive_session.transcript_already_archived("conv-LIVE", tmp_path) is True


def test_a_body_mention_does_not_suppress_a_live_conversation(tmp_path: Path) -> None:
    """Identity must be matched on the DECLARED header, never "does this string
    appear somewhere in the document".

    The guard used to run `conv_id in backup.read_text()` over every archived
    backup's entire body. Chat backups contain whole conversations, and
    conversations routinely quote transcript paths and conversation IDs -- so a
    session that merely DISCUSSED its own transcript matched a predecessor's
    backup, was declared already-archived, and selection fell through to an
    unrelated conversation, which would then be filed under this session's
    timestamp and reported as success. Compaction makes this near-certain: the
    compaction note names the transcript.
    """
    archive = tmp_path / "docs" / "chat_logs" / "archive"
    archive.mkdir(parents=True)
    (archive / "chat_backup_260730_1521.md").write_text(
        "# Chat Backup\n\n"
        "**Conversation ID:** conv-OLD\n\n"
        "We reviewed the transcript for conv-LIVE and agreed it looked fine.\n",
        encoding="utf-8",
    )

    assert archive_session.transcript_already_archived("conv-LIVE", tmp_path) is False, (
        "conv-LIVE is only MENTIONED in another conversation's backup; treating that "
        "as 'already archived' strands the real session and archives the wrong one"
    )
    # The conversation the backup actually declares is still correctly skipped.
    assert archive_session.transcript_already_archived("conv-OLD", tmp_path) is True


def test_continuation_uses_the_filename_stamp_not_the_backup_mtime(tmp_path: Path) -> None:
    """Continuation detection must key on the content-derived filename stamp.

    File mtimes are rewritten by git checkouts and by cloud-sync clients for
    reasons unrelated to when the archive was taken. Keying on the backup's mtime
    makes every archive look newer than every transcript after a checkout, which
    silently disables this detection -- and leaves no trace, because the guard
    just goes on reporting "already archived".
    """
    archive = tmp_path / "docs" / "chat_logs" / "archive"
    archive.mkdir(parents=True)
    transcript = _claude_transcript(tmp_path / "live.jsonl", "conv-LIVE", ["first half"])
    backup = archive / "chat_backup_260728_1926.md"
    backup.write_text(
        "# Chat Backup\n\n**Conversation ID:** conv-LIVE\n\nfirst half\n", encoding="utf-8"
    )

    archived_at = datetime(2026, 7, 28, 19, 26).timestamp()
    # The session continued 5 minutes after that archive was taken...
    os.utime(transcript, (archived_at + 300, archived_at + 300))
    # ...but a later git checkout restamped the backup FILE to now, so by mtime the
    # backup looks far newer than the transcript.
    now = time.time()
    os.utime(backup, (now, now))
    assert backup.stat().st_mtime > transcript.stat().st_mtime, "test setup: mtime is inverted"

    assert archive_session.transcript_already_archived("conv-LIVE", tmp_path, transcript) is False, (
        "continuation was missed because the backup's mtime was trusted over its "
        "filename stamp; a git checkout would silently disable this detection"
    )


def test_backup_stamp_parses_disambiguated_collision_names(tmp_path: Path) -> None:
    """The stamp reader must accept the `_b`/`_c` names the collision guard writes.

    These two mechanisms arrived from different projects and meet here. If the
    stamp regex rejected the disambiguating suffix, those backups would register at
    datetime.min and their conversations would be re-archived on every run.
    """
    assert archive_session._backup_stamp(tmp_path / "chat_backup_260731_1400.md") == datetime(
        2026, 7, 31, 14, 0
    )
    assert archive_session._backup_stamp(tmp_path / "chat_backup_260731_1400_b.md") == datetime(
        2026, 7, 31, 14, 0
    )
    assert archive_session._backup_stamp(tmp_path / "session_260731_1400.md") is None


def test_collision_guard_does_not_overwrite_on_a_body_mention(tmp_path: Path) -> None:
    """The collision guard decides "same conversation" on the header too.

    It exists to stop one conversation clobbering another at the same stamp. Deciding
    "this is just a refresh" from a body substring re-opens that exact data loss from
    the other side: a backup that merely MENTIONS this id in prose would be treated as
    a refresh of it and overwritten in place.
    """
    archive = tmp_path / "docs" / "chat_logs" / "archive"
    archive.mkdir(parents=True)
    dest = archive / "chat_backup_260731_1400.md"
    dest.write_text(
        "# Chat Backup\n\n"
        "**Conversation ID:** conv-OLD\n\n"
        "Notes captured while debugging conv-NEW.\n",
        encoding="utf-8",
    )

    resolved = archive_session.resolve_backup_collision(dest, "conv-NEW")
    assert resolved != dest, (
        "conv-NEW is a DIFFERENT conversation that is merely named in conv-OLD's body; "
        "returning the same path overwrites conv-OLD's backup"
    )
    assert resolved.name == "chat_backup_260731_1400_b.md"
    # A genuine refresh of the declared conversation still overwrites in place.
    assert archive_session.resolve_backup_collision(dest, "conv-OLD") == dest


def test_claude_backup_returns_the_path_it_actually_wrote(tmp_path: Path) -> None:
    """generate_chat_backup is annotated `-> Path` and the caller assigns its result
    to the path it later stages. The Claude branch fell out of the function with a
    bare `return`, so on every Claude session the caller staged None -- while the
    backup itself was written correctly, which is what kept it quiet.
    """
    archive = tmp_path / "docs" / "chat_logs" / "archive"
    archive.mkdir(parents=True)
    dest = archive / "chat_backup_260731_1400.md"

    first = _claude_transcript(tmp_path / "a.jsonl", "conv-AAA", ["first"])
    written = archive_session.generate_chat_backup(first, dest, "260731_1400", "conv-AAA", "claude")
    assert written == dest
    assert written.exists()

    # On a collision it must return the DISAMBIGUATED path, not the one requested.
    second = _claude_transcript(tmp_path / "b.jsonl", "conv-BBB", ["second"])
    redirected = archive_session.generate_chat_backup(
        second, dest, "260731_1400", "conv-BBB", "claude"
    )
    assert redirected != dest, "the second conversation must not claim the first one's path"
    assert redirected.exists(), "staging would point at a file that was never written"


# ---------------------------------------------------------------------------
# Multi-window transcript selection (archive_session_integrity pack S6)
# ---------------------------------------------------------------------------

def _claude_project_transcript(pdir: Path, conv_id: str, cwd: str, mtime: float) -> Path:
    """A Claude Code transcript in a project dir, with an explicit cwd and mtime."""
    import json

    path = pdir / f"{conv_id}.jsonl"
    path.write_text(
        json.dumps({
            "sessionId": conv_id,
            "cwd": cwd,
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]},
        }) + "\n",
        encoding="utf-8",
    )
    os.utime(path, (mtime, mtime))
    return path


def test_session_id_beats_newest_mtime_with_two_windows_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With two windows open, EVERY transcript matches cwd and every one is live.

    "Newest mtime" then selects whichever window typed most recently, not the one
    that ran the archiver. CLAUDE_CODE_SESSION_ID is the only signal that stays
    correct, so it must win even though the other transcript is newer.
    """
    project = tmp_path / "proj"
    (project / "docs" / "chat_logs" / "archive").mkdir(parents=True)
    pdir = tmp_path / "claude"
    pdir.mkdir()
    monkeypatch.setattr(archive_session, "claude_project_dirs", lambda: [pdir])

    now = time.time()
    _claude_project_transcript(pdir, "conv-OTHER", str(project), now)       # newest
    mine = _claude_project_transcript(pdir, "conv-MINE", str(project), now - 600)

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "conv-MINE")
    assert archive_session.find_claude_transcript(project) == mine, (
        "the calling session's own transcript must win over a more recently "
        "typed-in window"
    )


def test_falls_back_to_mtime_scan_and_warns_when_session_id_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No session id -> mtime scan, but the ambiguity must be VISIBLE, not silent."""
    project = tmp_path / "proj"
    (project / "docs" / "chat_logs" / "archive").mkdir(parents=True)
    pdir = tmp_path / "claude"
    pdir.mkdir()
    monkeypatch.setattr(archive_session, "claude_project_dirs", lambda: [pdir])

    now = time.time()
    newest = _claude_project_transcript(pdir, "conv-A", str(project), now)
    _claude_project_transcript(pdir, "conv-B", str(project), now - 60)

    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    assert archive_session.find_claude_transcript(project) == newest
    warning = capsys.readouterr().out
    assert "2 transcripts for this project" in warning, (
        "two live transcripts within the hour is exactly the case mtime cannot "
        "resolve; choosing silently hides it"
    )


def test_stale_session_id_pointing_elsewhere_is_ignored_not_trusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A session id resolving to ANOTHER project's transcript must not be believed.

    Trusting it would archive a different project's conversation into this repo --
    the confidentiality failure the cwd filter exists to prevent.
    """
    project = tmp_path / "proj"
    (project / "docs" / "chat_logs" / "archive").mkdir(parents=True)
    other = tmp_path / "someone-elses-project"
    pdir = tmp_path / "claude"
    pdir.mkdir()
    monkeypatch.setattr(archive_session, "claude_project_dirs", lambda: [pdir])

    now = time.time()
    _claude_project_transcript(pdir, "conv-FOREIGN", str(other), now)
    mine = _claude_project_transcript(pdir, "conv-MINE", str(project), now - 600)

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "conv-FOREIGN")
    assert archive_session.find_claude_transcript(project) == mine
    assert "cwd is not this project" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The sweep keeps the next session's working set (owner comment C2, 2026-08-29)
# ---------------------------------------------------------------------------


def _sweep_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs" / "archive").mkdir(parents=True)
    return root


def test_the_newest_workplan_survives_the_sweep_and_older_ones_do_not(tmp_path: Path) -> None:
    """Archiving happens at the exact moment the next session's plan was just
    written; sweeping it away un-plans the session it exists for."""
    root = _sweep_repo(tmp_path)
    old_plan = root / "docs" / "workplan_next_session_260801_1000.md"
    new_plan = root / "docs" / "workplan_next_session_260829_0400.md"
    old_plan.write_text("old\n", encoding="utf-8")
    new_plan.write_text("new\n", encoding="utf-8")
    import os as _os
    _os.utime(old_plan, (1, 1))  # unambiguously older

    staged: list[Path] = []
    moved, failed = archive_session.archive_all_folders_with_archives(
        root, "260829_9999", staged, dry_run=False
    )
    assert failed == 0
    assert new_plan.exists(), "the NEWEST workplan must stay in place"
    assert not old_plan.exists(), "older workplans archive as normal"
    assert (root / "docs" / "archive" / old_plan.name).exists()


def test_keep_globs_protect_ad_hoc_companion_files(tmp_path: Path) -> None:
    root = _sweep_repo(tmp_path)
    companion = root / "docs" / "handoff_notes_260801_1200.md"
    companion.write_text("keep me\n", encoding="utf-8")

    staged: list[Path] = []
    archive_session.archive_all_folders_with_archives(
        root, "260829_9999", staged, dry_run=False, keep_globs=["docs/handoff_notes_*.md"]
    )
    assert companion.exists(), "--keep globs must survive the sweep"


def test_the_pack_library_is_never_swept_even_with_an_archive_subfolder(tmp_path: Path) -> None:
    """docs/upgrades/ has its OWN lifecycle (record/prune, AGENTS 6) - the sweep must
    not touch it. It was safe only while it lacked an archive/ subfolder; the day one
    appeared, a dry run showed the sweep about to move all 27 packs out of the library,
    which every tool would read as 'nothing pending' mid-fleet-application."""
    root = tmp_path / "repo"
    lib = root / "docs" / "upgrades"
    (lib / "archive").mkdir(parents=True)
    pack = lib / "upgrade_instructions_pending_260801_1200.md"
    pack.write_text("# pending work\n", encoding="utf-8")

    staged: list[Path] = []
    archive_session.archive_all_folders_with_archives(root, "260829_9999", staged, dry_run=False)
    assert pack.exists(), "a pending pack must NEVER be swept out of the library"
    assert not (lib / "archive" / pack.name).exists()
