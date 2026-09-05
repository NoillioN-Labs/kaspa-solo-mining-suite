import argparse
import glob
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - degraded mode when pyyaml missing
    yaml = None  # type: ignore[assignment]


def get_project_root() -> Path:
    """Return the absolute path of the project root."""
    return Path(__file__).resolve().parent.parent.parent

def candidate_brain_dirs() -> list[Path]:
    """Return possible IDE 'brain' directories, most-likely first.

    The IDE stores transcripts under the user profile. Windows-native is the
    primary environment; append additional vendor locations here if a new IDE
    or install layout needs to be supported.
    """
    return [Path.home() / ".gemini" / "antigravity-ide" / "brain"]

def transcript_references_project(transcript_path: Path, project_name: str) -> bool:
    """Return True iff the transcript's content mentions the project folder name.

    The IDE brain directory holds transcripts for ALL workspaces, so picking by
    modification time alone can select another project's (or another client's)
    conversation. Requiring a path-fragment match on the repo folder name links
    the transcript to THIS project before it is archived into the repo.
    """
    needle = project_name.lower()
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if needle in line.lower():
                    return True
    except OSError as exc:
        print(f"[WARN] Could not read transcript {transcript_path}: {exc}")
    return False

#: The header line every chat backup writes (see generate_chat_backup). Matching on
#: this, ANCHORED, is what makes archived-ID detection an identity test rather than a
#: substring guess. Kept as one constant so the writer and the reader cannot drift.
_CONV_ID_HEADER_RE = re.compile(r"^\*\*Conversation ID:\*\*\s*(\S+)\s*$", re.MULTILINE)

#: `chat_backup_YYMMDD_HHMM.md`, optionally carrying a `_b`/`_c`... disambiguating
#: suffix from resolve_backup_collision. The stamp is written INTO the filename by
#: this script, which makes it a CONTENT-DERIVED time.
#:
#: Deliberately preferred over the file's mtime: git checkouts and cloud-sync clients
#: both rewrite mtimes for reasons that have nothing to do with when the archive was
#: taken. Either would make every backup look newer than every transcript and so
#: silently disable continuation detection below -- a failure that leaves no trace,
#: because the guard would simply go on reporting "already archived".
_BACKUP_STAMP_RE = re.compile(r"^chat_backup_(\d{6}_\d{4})(?:_[a-z])?\.md$")


def _backup_stamp(path: Path) -> datetime | None:
    """The archive time encoded in a backup's filename, or None if unparseable."""
    match = _BACKUP_STAMP_RE.match(path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%y%m%d_%H%M")
    except ValueError:
        return None


def archived_conversation_times(project_root: Path) -> dict[str, datetime]:
    """Map conversation ID -> the LATEST time it was archived.

    IDs come only from the `**Conversation ID:**` header; times come from the backup
    filename stamp. A backup whose name carries no parseable stamp still registers its
    conversation, at `datetime.min` -- present, but never newer than a live transcript,
    so it can never SUPPRESS a continuation. Fail toward re-archiving; that costs disk,
    not history.
    """
    archive_dir = project_root / "docs" / "chat_logs" / "archive"
    if not archive_dir.is_dir():
        return {}
    times: dict[str, datetime] = {}
    for backup in sorted(archive_dir.glob("*.md")):
        try:
            text = backup.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"[WARN] Could not read {backup}: {exc}")
            continue
        stamp = _backup_stamp(backup) or datetime.min
        for conv_id in _CONV_ID_HEADER_RE.findall(text):
            if conv_id not in times or stamp > times[conv_id]:
                times[conv_id] = stamp
    return times


def archived_conversation_ids(project_root: Path) -> set[str]:
    """The conversation IDs previously archived, read from backup HEADERS only."""
    return set(archived_conversation_times(project_root))


def transcript_continued_since_archive(
    transcript_path: Path, conv_id: str, project_root: Path
) -> bool:
    """True when this conversation was archived AND has been written to since.

    "Already archived" is not "fully archived". A session that keeps working after
    running the archiver has a transcript newer than its own backup, and skipping it
    silently truncates the record. The two cases separate on one fact:

    * **stale re-match** (the 260711 defect the skip exists for) -- an old conversation
      the IDE brain keeps re-offering, NOT written since it was archived. Stay skipped.
    * **continued session** -- transcript modified AFTER its own archive stamp. Re-archive.

    Returns False when the conversation was never archived; the caller's ordinary
    "not archived" path already handles that.
    """
    archived_at = archived_conversation_times(project_root).get(conv_id)
    if archived_at is None:
        return False
    try:
        modified = datetime.fromtimestamp(transcript_path.stat().st_mtime)
    except OSError:
        return False  # cannot compare: stay conservative
    return modified > archived_at


def transcript_already_archived(
    conv_id: str, project_root: Path, transcript_path: Path | None = None
) -> bool:
    """Return True iff this conversation is archived AND has not grown since.

    The IDE brain directory keeps old conversations indefinitely, so the newest
    project-matching transcript can be one an earlier session already archived.
    Re-compiling it would file a stale conversation under a fresh timestamp
    (observed 260711: the 260706 PPT-troubleshooting conversation matched again).
    Skipping already-archived IDs makes transcript selection idempotent.

    DEFECT FIXED 260731 -- THIS IS WHY IT IS HEADER-SCOPED. This used to be
    `conv_id in backup.read_text()`, a substring scan of every archived backup's
    ENTIRE BODY. Chat backups contain the full conversation, and conversations
    routinely quote transcript paths and conversation IDs, so a session that merely
    *discussed* its own transcript matched its predecessor's backup, was declared
    already-archived, and selection fell through to an unrelated conversation -- which
    would then be filed under this session's timestamp and reported as success.
    Compacted sessions make this near-certain: the compaction note names the transcript.

    Legacy backups predating the header contribute NO ids, deliberately. Their
    conversation IDs were never recorded, so scanning their bodies cannot IDENTIFY a
    conversation -- it can only manufacture false positives.
    """
    if not conv_id or conv_id == "unknown":
        return False
    if conv_id not in archived_conversation_ids(project_root):
        return False
    if transcript_path is not None and transcript_continued_since_archive(
        transcript_path, conv_id, project_root
    ):
        print(
            f"[INFO] Conversation {conv_id} has grown since it was last archived; "
            "re-archiving so the tail is not stranded."
        )
        return False
    return True

def discover_sibling_projects(project_root: Path) -> list[str]:
    """Folder names of sibling fleet projects (contain AGENTS.md), for transcript attribution."""
    siblings: list[str] = []
    try:
        for entry in project_root.parent.iterdir():
            if entry.name == project_root.name or entry.name.startswith((".", "_")):
                continue
            if entry.is_dir() and (entry / "AGENTS.md").exists():
                siblings.append(entry.name)
    except OSError as exc:
        print(f"[WARN] Could not scan sibling projects: {exc}")
    return siblings

def transcript_belongs_elsewhere(transcript_path: Path, project_name: str, sibling_names: list[str]) -> str | None:
    """Return the sibling project this transcript most likely belongs to, or None.

    A conversation held in another fleet project can mention this project in
    passing (observed 260711: a Horse-racing-tips conversation mentioning the
    template), so a bare substring match over-claims. Attribute the transcript
    to the project it mentions most; a sibling that out-mentions this project
    wins the claim and the transcript is skipped here.
    """
    try:
        text = transcript_path.read_text(encoding="utf-8", errors="replace").lower()
    except OSError as exc:
        print(f"[WARN] Could not read transcript {transcript_path}: {exc}")
        return None
    own_count = text.count(project_name.lower())
    for sibling in sibling_names:
        if text.count(sibling.lower()) > own_count:
            return sibling
    return None

def find_active_transcript(project_name: str, allow_unmatched: bool = False) -> Path | None:
    """Locate the most recently modified transcript.jsonl that references this project.

    Candidates are ordered newest-first by modification time and filtered to
    those whose content mentions `project_name`. When none match, returns None
    (callers should skip transcript compilation, NOT abort the run) unless
    `allow_unmatched` is True, in which case the newest transcript is accepted
    with a warning as an explicit opt-in for edge cases.
    """
    brain_dirs = [d for d in candidate_brain_dirs() if d.exists()]
    if not brain_dirs:
        searched = ", ".join(str(d) for d in candidate_brain_dirs())
        print(f"[WARN] IDE AppData brain directory not found. Searched: {searched}")
        return None

    transcript_paths: list[str] = []
    for ide_brain_dir in brain_dirs:
        pattern = str(ide_brain_dir / "*" / ".system_generated" / "logs" / "transcript.jsonl")
        transcript_paths.extend(glob.glob(pattern))

    if not transcript_paths:
        searched = ", ".join(str(d) for d in brain_dirs)
        print(f"[WARN] No transcript.jsonl files found under: {searched}")
        return None

    # Newest first, then three gates: the content must mention this project,
    # the conversation must not already be archived, and no sibling project may
    # out-mention this one (a passing reference is not ownership).
    project_root = get_project_root()
    sibling_names = discover_sibling_projects(project_root)
    newest_first = sorted(transcript_paths, key=os.path.getmtime, reverse=True)
    for candidate in newest_first:
        candidate_path = Path(candidate)
        if not transcript_references_project(candidate_path, project_name):
            continue
        conv_id = candidate_path.parent.parent.parent.name
        if transcript_already_archived(conv_id, project_root, candidate_path):
            print(f"[INFO] Skipping already-archived conversation {conv_id} (present in docs/chat_logs/archive/).")
            continue
        rival = transcript_belongs_elsewhere(candidate_path, project_name, sibling_names)
        if rival is not None:
            print(f"[INFO] Skipping conversation {conv_id}: it mentions '{rival}' more than this project.")
            continue
        return candidate_path

    if allow_unmatched:
        newest = Path(newest_first[0])
        print(
            f"[WARN] No transcript references '{project_name}'. --allow-unmatched "
            f"is set; using newest transcript anyway: {newest}"
        )
        return newest

    print(
        f"[WARN] None of the {len(newest_first)} transcript(s) under "
        f"{', '.join(str(d) for d in brain_dirs)} reference this project "
        f"('{project_name}'). Skipping transcript compilation to avoid archiving "
        "another project's conversation. Use --transcript <path> to point at the "
        "correct file, or --allow-unmatched to accept the newest transcript."
    )
    return None

def claude_project_dirs() -> list[Path]:
    """Return the Claude Code per-project transcript directories, if present.

    Claude Code stores one directory per workspace under the user profile, named
    by encoding the absolute project path (every non-alphanumeric/underscore char
    becomes '-'). Each holds `<sessionId>.jsonl` transcripts for THIS project only,
    so there is no cross-project attribution problem the way the shared IDE brain
    directory has.
    """
    base = Path.home() / ".claude" / "projects"
    return [d for d in base.iterdir() if d.is_dir()] if base.is_dir() else []


def _claude_transcript_cwd(transcript_path: Path) -> str | None:
    """Read the first event carrying a `cwd` and return it (the session's project root)."""
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    cwd = json.loads(line).get("cwd")
                except json.JSONDecodeError:
                    continue
                if cwd:
                    return cwd
    except OSError as exc:
        print(f"[WARN] Could not read Claude transcript {transcript_path}: {exc}")
    return None


#: Claude Code exports the running session's conversation id into the environment of
#: every command it spawns. When present this is AUTHORITATIVE -- it is the one signal
#: that stays correct with several chat windows open on the same project, where
#: "newest mtime" is a coin toss between them.
_SESSION_ID_ENV = "CLAUDE_CODE_SESSION_ID"


def session_transcript_from_env(project_root: Path) -> Path | None:
    """The transcript of the session that invoked this script, if it can be known.

    Selecting by modification time is a heuristic, and with two or more Claude Code
    windows open on the same project it is simply wrong: every one of them has a live
    transcript whose `cwd` matches, so the archiver files whichever window typed most
    recently rather than the one that asked. This is the difference between DETECTING
    that problem and not having it.

    Returns None when the variable is unset (a plain terminal, or another tool), when
    the file is missing, or when the transcript's `cwd` is a different project -- all
    of which fall back to the mtime scan rather than trusting a stale variable.
    """
    conv_id = os.environ.get(_SESSION_ID_ENV, "").strip()
    if not conv_id:
        return None
    target = str(project_root).lower().rstrip("\\/")
    for pdir in claude_project_dirs():
        candidate = pdir / f"{conv_id}.jsonl"
        if not candidate.is_file():
            continue
        cwd = _claude_transcript_cwd(candidate)
        if cwd is None or cwd.lower().rstrip("\\/") != target:
            print(
                f"[WARN] {_SESSION_ID_ENV}={conv_id} resolves to a transcript whose "
                "cwd is not this project; ignoring it and scanning instead."
            )
            return None
        return candidate
    return None


def _warn_if_multiple_live_transcripts(candidates: list[str], chosen: Path) -> None:
    """Warn when several transcripts for this project were written to recently.

    Only reached on the mtime-scan fallback; with the session id available the choice
    is exact and this never fires. Makes the ambiguity visible rather than silent.
    """
    try:
        chosen_m = chosen.stat().st_mtime
    except OSError:
        return
    rivals = []
    for path in candidates:
        p = Path(path)
        if p == chosen:
            continue
        try:
            if abs(p.stat().st_mtime - chosen_m) <= 3600:  # within an hour
                rivals.append(p.stem)
        except OSError:
            continue
    if rivals:
        print(
            f"[WARN] {len(rivals) + 1} transcripts for this project were written to "
            f"within the last hour: {chosen.stem} (chosen), {', '.join(rivals)}. "
            f"{_SESSION_ID_ENV} was not set, so the choice is by modification time "
            "and may be the wrong window. Confirm the [SELECTED] line, or pass "
            "--transcript explicitly."
        )


def _announce_selection(path: Path, source: str, conv_id: str) -> None:
    """Print the [SELECTED] line: WHAT was chosen, and WHEN it was last written.

    The near-miss behind this script's identity fixes was caught only because a
    human read a dry-run. The **last-modified time is the single best tell**: it
    should read as *now*. A days-old stamp means the wrong conversation was
    selected, and no other field makes that as obvious.
    """
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        modified = "unknown"
    print(f"[SELECTED] source={source} conversation={conv_id}")
    print(f"[SELECTED] last modified={modified}  <- should read as NOW")
    print(f"[SELECTED] path={path}")


def find_claude_transcript(project_root: Path) -> Path | None:
    """Locate this session's Claude Code transcript.

    Selection order:
      1. `CLAUDE_CODE_SESSION_ID` -- exact, and correct with any number of windows open;
      2. `cwd` match + newest mtime (plain terminal, or another tool), warning when
         more than one project transcript was written within the hour.

    Matching on the embedded `cwd` (case-insensitive) rather than reconstructing the
    encoded directory name is robust to drive-letter casing and path quirks.
    Conversations already present in the chat archive are skipped (idempotent).
    """
    exact = session_transcript_from_env(project_root)
    if exact is not None and not transcript_already_archived(
        exact.stem, project_root, exact
    ):
        return exact

    candidates: list[str] = []
    for pdir in claude_project_dirs():
        candidates.extend(glob.glob(str(pdir / "*.jsonl")))
    if not candidates:
        return None
    target = str(project_root).lower()
    matching: list[str] = []
    for path in candidates:
        cwd = _claude_transcript_cwd(Path(path))
        if cwd is not None and cwd.lower().rstrip("\\/") == target.rstrip("\\/"):
            matching.append(path)
    for path in sorted(matching, key=os.path.getmtime, reverse=True):
        p = Path(path)
        if transcript_already_archived(p.stem, project_root, p):
            print(f"[INFO] Skipping already-archived Claude conversation {p.stem}.")
            continue
        _warn_if_multiple_live_transcripts(matching, p)
        return p
    return None


def locate_transcript(project_root: Path, args: argparse.Namespace) -> tuple[Path | None, str, str | None]:
    """Resolve the transcript to compile and its source format.

    Order: explicit --transcript override, then Claude Code (the current tool),
    then the Antigravity IDE brain (retained for occasional IDE sessions). Returns
    (path, source, skip_reason) where source is 'claude' | 'antigravity' | 'none'.
    """
    if args.transcript:
        override = Path(args.transcript).expanduser()
        if override.is_file():
            source = "claude" if override.suffix == ".jsonl" and override.name != "transcript.jsonl" else "antigravity"
            return override, source, None
        return None, "none", f"--transcript path not found: {override}"

    claude = find_claude_transcript(project_root)
    if claude is not None:
        return claude, "claude", None

    try:
        antigravity = find_active_transcript(project_root.name, allow_unmatched=args.allow_unmatched)
    except Exception as exc:  # noqa: BLE001 - discovery must never abort the run
        print(f"[WARN] Error locating Antigravity transcript: {exc}")
        antigravity = None
    if antigravity is not None:
        # Loud, because this is BOTH legitimate (an occasional IDE session) and the
        # exact shape of the near-miss: no Claude transcript was found, so selection
        # fell through to another tool's conversation and would have filed it under
        # this session's timestamp. Legitimate and catastrophic look identical here.
        print(
            "[WARN] No Claude Code transcript matched this project; falling back to "
            "the IDE brain. If you are IN a Claude Code session right now, this is "
            "WRONG -- check the [SELECTED] line below before proceeding."
        )
        return antigravity, "antigravity", None
    return None, "none", "no Claude or Antigravity transcript matched this project"


def _compile_claude(transcript_path: Path) -> tuple[str, int]:
    """Compile a Claude Code JSONL transcript to Markdown body; return (body, dropped)."""
    body = ""
    dropped = 0
    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                dropped += 1
                continue
            if ev.get("type") not in ("user", "assistant") or ev.get("isSidechain"):
                continue
            content = (ev.get("message") or {}).get("content")
            texts: list[str] = []
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for block in content:
                    # Real conversation is the 'text' blocks; tool_use / tool_result /
                    # thinking blocks are machinery and are intentionally omitted.
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
            text = "\n".join(t for t in texts if t and t.strip())
            if not text.strip():
                continue
            role = (ev.get("message") or {}).get("role")
            # Drop slash-command wrappers and injected caveats — not user prose.
            if role == "user" and (
                text.lstrip().startswith(("<local-command", "<command-name", "Caveat:"))
                or "<command-name>" in text
            ):
                continue
            heading = "User" if role == "user" else "Assistant"
            body += f"### {heading}\n\n{text}\n\n"
    return body, dropped


def resolve_backup_collision(dest_path: Path, conv_id: str) -> Path:
    """Return a path that will not destroy an existing backup of a DIFFERENT conversation.

    The backup filename carries a minute-resolution stamp, so two runs inside the same
    minute build the same name. Writing unconditionally meant the second silently
    overwrote the first while both printed `[OK] Chat backup created` -- observed live
    on 2026-07-28, when an Antigravity conversation archived at 19:48 was destroyed
    seconds later by a Claude conversation at the same stamp.

    `place_session_log` already guards this collision class for the session log
    (archiver_session_log_collision_260712_1215); the chat backup was never covered.

    Re-archiving the SAME conversation to the same stamp still overwrites, which is
    correct -- that is a refresh, not a collision.

    "Same conversation" is decided on the backup's `**Conversation ID:**` HEADER, never
    on a body substring. A body scan re-opens the very data loss this function exists to
    prevent, from the other side: a backup that merely MENTIONS this conversation's id in
    prose would be misread as a refresh of it and overwritten in place.
    """
    if not dest_path.exists():
        return dest_path
    try:
        existing = dest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        existing = ""
    if conv_id and conv_id != "unknown" and conv_id in _CONV_ID_HEADER_RE.findall(existing):
        return dest_path  # same conversation: a refresh, not a clobber
    for suffix in "bcdefghijklmnopqrstuvwxyz":
        candidate = dest_path.with_name(f"{dest_path.stem}_{suffix}{dest_path.suffix}")
        if not candidate.exists():
            print(
                f"[WARN] {dest_path.name} already holds a different conversation; "
                f"writing {candidate.name} instead (nothing overwritten)."
            )
            return candidate
    raise RuntimeError(
        f"Refusing to overwrite {dest_path.name}: it holds a different conversation and "
        "26 disambiguated names are already taken. Pass --timestamp to choose a new stamp."
    )


def generate_chat_backup(
    transcript_path: Path, dest_path: Path, stamp: str, conv_id: str, source: str = "antigravity"
) -> Path:
    """Compile a transcript to a Markdown chat backup. Returns the path actually written.

    Dispatches on `source`: 'claude' parses Claude Code JSONL (text blocks only),
    'antigravity' parses the IDE brain schema (USER_EXPLICIT + MODEL planner turns).

    Never destroys a backup of a different conversation -- see resolve_backup_collision.
    """
    dest_path = resolve_backup_collision(dest_path, conv_id)
    if source == "claude":
        body, dropped = _compile_claude(transcript_path)
        header = (
            f"# Chat Backup - {stamp}\n\n"
            f"**Timestamp:** {stamp}\n"
            f"**Conversation ID:** {conv_id}\n"
            f"**Source:** Claude Code session transcript\n\n"
        )
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as out:
            out.write(header + body)
        if dropped:
            print(f"[WARN] Dropped {dropped} malformed JSON line(s) during chat backup.")
        print(f"[OK] Chat backup created: {dest_path.name}")
        return dest_path

    markdown_content = f"# Chat Backup - {stamp}\n\n"
    markdown_content += f"**Timestamp:** {stamp}\n"
    markdown_content += f"**Conversation ID:** {conv_id}\n\n"

    dropped_lines = 0
    with open(transcript_path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            try:
                step = json.loads(line)
                source = step.get("source")
                type_ = step.get("type")
                content = step.get("content", "")

                # M-16: Handle structured content gracefully
                if isinstance(content, (list, dict)):
                    content = json.dumps(content, indent=2)

                if type_ == "USER_INPUT" and source == "USER_EXPLICIT":
                    markdown_content += f"### User\n\n{content}\n\n"
                elif type_ == "PLANNER_RESPONSE" and source == "MODEL":
                    markdown_content += f"### Assistant\n\n{content}\n\n"
            except Exception:
                dropped_lines += 1

    if dropped_lines > 0:
        print(f"[WARN] Dropped {dropped_lines} malformed or unparseable JSON lines during chat backup.")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as out:
        out.write(markdown_content)
    print(f"[OK] Chat backup created: {dest_path.name}")
    return dest_path

def archive_root_logs(project_root: Path, stamp: str, dry_run: bool = False) -> list[str]:
    """Scan the project root for hermes_stderr.log and hermes_stdout.log and move them to logs/archive/.

    Returns the archive file names actually moved (empty on dry runs or when no
    root logs are present) so the session/action logs can record real outcomes.
    """
    archive_dir = project_root / "logs" / "archive"
    if not dry_run:
        archive_dir.mkdir(parents=True, exist_ok=True)

    moved: list[str] = []
    for name in ["hermes_stderr.log", "hermes_stdout.log"]:
        log_file = project_root / name
        if log_file.exists():
            stem = log_file.stem
            dest_name = f"{stem}_{stamp}.log"
            dest = archive_dir / dest_name
            if dry_run:
                print(f"[DRY-RUN] Would move {name} to logs/archive/{dest_name}")
                continue
            try:
                shutil.move(str(log_file), str(dest))
                moved.append(dest_name)
                print(f"[OK] Moved {name} to logs/archive/{dest_name}")
            except Exception as e:
                print(f"[WARN] Could not move {name}: {e}")
    return moved

@dataclass
class RunOutcomes:
    """Actual results of an archiving run.

    Collected AFTER the work has been performed so that the session and action
    logs describe what really happened (including skips and failures) instead
    of pre-written claims of success.
    """
    chat_backup_result: str = "Not attempted"
    chat_backup_created: bool = False
    root_logs_moved: list[str] = field(default_factory=list)
    swept_moved: int = 0
    swept_failed: int = 0
    pruned_deleted: int = 0
    pruned_candidates: int = 0
    staging_result: str = "Not attempted"


def find_agent_session_log(project_root: Path) -> Path | None:
    """Return the agent-written docs/sessions/session_*.md for this session, if any.

    MUST be called BEFORE the sweep: the sweep relocates session_*.md into
    docs/sessions/archive/, so a check made afterwards always looks at an emptied
    directory. Matching on the archive run's own stamp is likewise wrong -- the agent
    writes its log mid-session, minutes or hours before the archiver runs, so the two
    stamps virtually never agree.
    """
    sessions_dir = project_root / "docs" / "sessions"
    candidates = [p for p in sessions_dir.glob("session_*.md") if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def place_session_log(
    project_root: Path,
    dest_path: Path,
    stamp: str,
    outcomes: RunOutcomes,
    agent_log: Path | None = None,
) -> Path | None:
    """Ensure exactly one session log exists for this session, preferring the agent's.

    An agent-written session log is the authoritative record; the generated maintenance
    stub exists only so a bare archiver run still leaves a log behind. Returns the path
    of the log that stands for this session, or None if there is nothing to stage.

    `agent_log` is the pre-sweep sighting from find_agent_session_log(); by the time we
    run, the sweep has already moved it into docs/sessions/archive/.
    """
    handwritten = project_root / "docs" / "sessions" / f"session_{stamp}.md"
    if handwritten.is_file():
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists():
            dest_path.unlink()
        handwritten.rename(dest_path)
        print(f"[OK] Agent-written session log archived: {dest_path.name} (stub skipped)")
        return dest_path
    if agent_log is not None:
        swept = dest_path.parent / agent_log.name
        landed = swept if swept.is_file() else agent_log
        print(f"[OK] Agent-written session log is authoritative: {landed.name} (stub skipped)")
        return landed if landed.is_file() else None
    if dest_path.is_file():
        print(f"[OK] Session log already present: {dest_path.name} (stub skipped)")
        return dest_path
    create_session_log(dest_path, stamp, outcomes)
    return dest_path


def create_session_log(dest_path: Path, stamp: str, outcomes: RunOutcomes) -> None:
    """Write the session log describing the outcomes of the run just performed."""
    root_logs_result = (
        "Moved: " + ", ".join(outcomes.root_logs_moved)
        if outcomes.root_logs_moved
        else "No root log files present"
    )
    sweep_result = f"{outcomes.swept_moved} file(s) archived, {outcomes.swept_failed} failure(s)"
    ran_clean = (
        not outcomes.chat_backup_result.startswith("Failed")
        and outcomes.swept_failed == 0
        and outcomes.staging_result == "Completed"
    )
    status = "Completed" if ran_clean else "Completed with warnings"

    artifact_lines: list[str] = []
    if outcomes.chat_backup_created:
        artifact_lines.append(f"* `docs/chat_logs/archive/chat_backup_{stamp}.md`")
    for name in outcomes.root_logs_moved:
        artifact_lines.append(f"* `logs/archive/{name}`")
    artifact_lines.append(f"* `docs/sessions/archive/session_{stamp}.md` (this file)")
    artifact_lines.append(f"* `docs/sessions/archive/actions_{stamp}.log`")
    artifacts_block = "\n".join(artifact_lines)

    content = f"""# Session Log: Session Maintenance

**Timestamp:** {stamp}
**Project:** {get_project_root().name}
**Topic:** Archive session logs, chats, and root telemetry logs
**Status:** {status}
**Executor:** `scripts/utilities/archive_session.py` (agent-executed)

---

## 1. Goal

Archive the active session chat history, rotate/sweep any root telemetry files (`hermes_stderr.log` / `hermes_stdout.log`), and ensure clean project bookkeeping and synchronization.

## 2. Execution Phases

| Phase | Description | Result |
|-------|-------------|--------|
| 1 | Compile the active conversation `transcript.jsonl` to `docs/chat_logs/archive/chat_backup_{stamp}.md`. | {outcomes.chat_backup_result} |
| 2 | Move root log files `hermes_stderr.log` and `hermes_stdout.log` into `logs/archive/` with timestamp suffixes. | {root_logs_result} |
| 3 | Sweep timestamped files into their `archive/` subfolders. | {sweep_result} |
| 4 | Stage results via `git add`. | {outcomes.staging_result} |

## 3. Key Discoveries & Implementation Invariants

* **Standardized Archive Flow**: Archiving runs via the standardized `scripts/utilities/archive_session.py` script.
* **Tidy Workspace**: Clearing out raw `.log` files at the project root prevents accidental commits of transient agent execution streams.

## 4. Outputs / Artifacts

{artifacts_block}
"""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Session log created: {dest_path.name}")

def create_action_log(dest_path: Path, stamp: str, outcomes: RunOutcomes) -> None:
    """Write the action log describing the outcomes of the run just performed."""
    root_logs_result = (
        "Moved " + ", ".join(outcomes.root_logs_moved) + " into `logs/archive/`"
        if outcomes.root_logs_moved
        else "No root log files present"
    )
    content = f"""# Archive Action Log - {stamp}

**Task:** Archive Chats and Logs (Standardized Utility Run)
**Runtime:** `scripts/utilities/archive_session.py` (Windows-native)
**Session window:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## Actions Performed

1. **Executed Archive Script**:
   - Ran `python scripts/utilities/archive_session.py` to automate session archival.
2. **Chat Backup**: {outcomes.chat_backup_result}
3. **Root Log Rotation**: {root_logs_result}
4. **Archive Sweep**: {outcomes.swept_moved} file(s) moved, {outcomes.swept_failed} failure(s)
5. **Git Staging**: {outcomes.staging_result}
"""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Action log created: {dest_path.name}")

def run_git_add(project_root: Path, file_paths: list[Path]) -> bool:
    """Run git add on the specified paths relative to project root, skipping gitignored files.

    Paths that no longer exist on disk (e.g. the OLD location of a swept file)
    are staged only when git tracks them, in which case `git add <old_path>`
    stages the deletion so a subsequent commit is clean. Returns True when
    staging succeeded (or there was nothing to stage), False on failure.
    """
    valid_paths: list[str] = []
    for p in file_paths:
        p_str = str(p)
        if not Path(p_str).exists():
            # Deleted/moved-away path: stageable only if git tracks it, in which
            # case adding the pathspec stages the deletion (see M-20).
            res = subprocess.run(
                ["git", "ls-files", "--error-unmatch", "--", p_str],
                cwd=str(project_root),
                check=False,
                capture_output=True,
            )
            if res.returncode == 0:
                valid_paths.append(p_str)
            continue
        try:
            # git check-ignore returns 0 if the path is ignored, 1 if not ignored.
            res = subprocess.run(
                ["git", "check-ignore", "-q", p_str],
                cwd=str(project_root),
                check=False
            )
            # M-19: 0 is ignored, 1 is not ignored, 128 is a fatal error
            if res.returncode == 1:
                valid_paths.append(p_str)
            elif res.returncode != 0 and res.returncode != 1:
                print(f"[WARN] git check-ignore failed with code {res.returncode} for {p_str}")
        except Exception:
            valid_paths.append(p_str)

    if not valid_paths:
        print("[OK] No stageable files (all ignored, missing, or untracked).")
        return True

    try:
        cmd = ["git", "add", "--"] + valid_paths
        subprocess.run(cmd, cwd=str(project_root), check=True, capture_output=True)
        print("[OK] Files staged successfully via git add.")
        return True
    except Exception as e:
        print(f"[WARN] Git add failed: {e}")
        return False

def archive_all_folders_with_archives(
    project_root: Path,
    current_stamp: str,
    files_to_stage: list[Path],
    dry_run: bool = False,
    keep_globs: list[str] | None = None,
) -> tuple[int, int]:
    """
    Find all subdirectories named 'archive' in the project.
    For each parent directory containing 'archive':
      - List all files in the parent directory.
      - If a file's name contains a timestamp in the format _YYMMDD_HHMM (or -YYMMDD_HHMM),
        and that timestamp is not the current session's timestamp,
        move the file to the 'archive' subdirectory.
    Returns (moved_count, failed_count); on dry runs moved_count counts planned moves.
    """
    print("\n[INFO] Scanning for 'archive' directories to tidy up...")
    timestamp_pattern = re.compile(r'[-_](?P<yymmdd>\d{6})_(?P<hhmm>\d{4})')

    # The NEWEST next-session workplan stays where the next session will look for
    # it (owner comment C2, 2026-08-29): archiving happens at the exact moment the
    # next session's plan has just been written, and sweeping it away un-plans the
    # session it exists for. Older workplans archive as normal. --keep adds ad-hoc
    # companions (root-relative globs) for the same reason.
    workplans = sorted(
        (project_root / "docs").glob("workplan_*.md"),
        key=lambda p: p.stat().st_mtime,
    )
    keep_paths: set[Path] = set(workplans[-1:])
    for pattern in keep_globs or []:
        keep_paths.update(q for q in project_root.glob(pattern) if q.is_file())
    for kept in sorted(keep_paths):
        print(f"  [KEPT] {kept.relative_to(project_root)} - next session's working set")

    # Only ever sweep known documentation/log/script roots. Walking the whole
    # project would let the sweep MOVE client/data files that happen to match a
    # timestamp pattern (e.g. `report_260101_1200.csv`) into an `archive/`
    # subfolder - a data-integrity hazard against client_files/ and .data/ (C-5).
    allowed_roots = ['docs', 'scripts', 'logs']

    # Defence-in-depth: never descend into these even if reached transitively.
    exclude_dirs = {
        '.git', '.venv', '.venv-linux', '__pycache__', '.pytest_cache',
        'client_files', '.data', 'node_modules', 'frontend', 'backend',
        # The pack library has its OWN lifecycle: presence in docs/upgrades/ means
        # pending work, and only `record`/`prune` may end it (AGENTS 6). The library
        # was safe from this sweep only while it happened to lack an archive/
        # subfolder; the day one appeared (2026-08-29, for two absorbed proposals) a
        # dry run showed the sweep about to move ALL 27 timestamped packs out of the
        # library - which would read to every tool as "nothing pending" while the
        # fleet was mid-application. Excluded by name, not by luck.
        'upgrades',
    }

    walk_targets = [
        project_root / r for r in allowed_roots if (project_root / r).is_dir()
    ]

    moved_count = 0
    failed_count = 0
    for target in walk_targets:
        for root, dirs, files in os.walk(str(target)):
            # Filter out excluded directories in-place to prevent walking them
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            if 'archive' not in dirs:
                continue
            parent_dir = Path(root)
            archive_dir = parent_dir / 'archive'
            print(f"  Checking parent folder: {parent_dir.relative_to(project_root)}")

            # List files in the parent folder
            for item in parent_dir.iterdir():
                if item.is_file() and not item.name.startswith('.'):
                    if item in keep_paths:
                        continue  # announced above; the next session needs it in place
                    match = timestamp_pattern.search(item.name)
                    if match:
                        file_stamp = f"{match.group('yymmdd')}_{match.group('hhmm')}"
                        # If the timestamp is different from the current session's timestamp
                        if file_stamp != current_stamp:
                            old_path = item
                            dest = archive_dir / item.name
                            if dry_run:
                                print(f"    [DRY-RUN] Would move {item.name} -> archive/{item.name}")
                                moved_count += 1
                                continue
                            try:
                                shutil.move(str(old_path), str(dest))
                                print(f"    [Moved] {item.name} -> archive/{item.name}")
                                moved_count += 1
                                # M-20: run_git_add stages explicit pathspecs (not
                                # `git add -A`), so the deletion at the OLD path
                                # must be staged explicitly as well - `git add`
                                # stages a tracked file's removal when given its
                                # (now missing) pathspec.
                                files_to_stage.append(dest)
                                files_to_stage.append(old_path)
                            except Exception as e:
                                failed_count += 1
                                print(f"    [WARN] Failed to move {item.name}: {e}")
    return moved_count, failed_count

def main() -> None:
    parser = argparse.ArgumentParser(description="Standardized archiving utility for chats and logs.")
    parser.add_argument("--timestamp", type=str, help="Override default timestamp (YYMMDD_HHMM)")
    parser.add_argument("--dry-run", action="store_true", help="Preview moves without acting")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument(
        "--keep", action="append", default=[], metavar="GLOB",
        help="Root-relative glob(s) the sweep must leave in place (the newest "
             "docs/workplan_*.md is always kept automatically)",
    )
    parser.add_argument(
        "--transcript",
        type=str,
        help="Explicit path to the transcript.jsonl to compile (bypasses auto-detection)",
    )
    parser.add_argument(
        "--allow-unmatched",
        action="store_true",
        help="Accept the newest transcript even if its content does not reference this project",
    )
    args = parser.parse_args()

    # 1. Establish timestamp
    if args.timestamp:
        # Validate the override: an arbitrary string would flow into filenames and
        # the sweep's "current stamp" comparison, causing every timestamped file
        # to be treated as not-current and archived (M-18).
        if not re.fullmatch(r"\d{6}_\d{4}", args.timestamp):
            print(
                f"[ERROR] Invalid --timestamp '{args.timestamp}'. "
                "Expected format YYMMDD_HHMM (e.g. 260626_2000)."
            )
            return
        stamp = args.timestamp
    else:
        stamp = datetime.now().strftime("%y%m%d_%H%M")

    project_root = get_project_root()

    # 2. Locate active transcript. This step is independent: an unmatched or
    #    missing transcript only skips chat-backup compilation; root-log
    #    rotation, the archive sweep, and git staging below always run.
    #    Claude Code is tried first (the current tool), Antigravity as fallback.
    transcript_path, transcript_source, transcript_skip_reason = locate_transcript(project_root, args)

    conv_id = "unknown"
    if transcript_path is not None:
        conv_id = (
            transcript_path.stem
            if transcript_source == "claude"
            else (transcript_path.parent.parent.parent.name or "unknown")
        )
        _announce_selection(transcript_path, transcript_source, conv_id)

    # Interactive confirmation gate. The near-miss this guards was survivable only
    # because a human read a dry-run, so the prompt must RESTATE WHAT IT CONFIRMS:
    # a confirmation that does not name the conversation is a rubber stamp, and this
    # is the only gate a human actually sees (agents pass --yes).
    if not args.dry_run and not args.yes:
        print("\n[WARNING] This operation will archive logs and chats, and sweep timestamped files into archive folders.")
        if transcript_path is None:
            print(f"          No transcript will be compiled ({transcript_skip_reason}).")
        else:
            print(f"          It will archive conversation: {conv_id}")
            print(f"          from: {transcript_path}")
            print("          If that is NOT the conversation you are in, answer N and re-run")
            print("          with --transcript <path>, or check the [SELECTED] line above.")
        response = input("Proceed? (y/N): ")
        if not response.strip().lower().startswith("y"):
            print("Aborting.")
            return

    # 3. Path definitions
    chat_backup_path = project_root / "docs" / "chat_logs" / "archive" / f"chat_backup_{stamp}.md"
    session_log_path = project_root / "docs" / "sessions" / "archive" / f"session_{stamp}.md"
    action_log_path = project_root / "docs" / "sessions" / "archive" / f"actions_{stamp}.log"

    outcomes = RunOutcomes()

    # 4. Transcript compilation (independent step)
    if transcript_path is None:
        outcomes.chat_backup_result = f"Skipped ({transcript_skip_reason})"
    elif args.dry_run:
        print(f"[DRY-RUN] Would compile chat backup to docs/chat_logs/archive/chat_backup_{stamp}.md")
        outcomes.chat_backup_result = "Dry run"
    else:
        try:
            chat_backup_path = generate_chat_backup(
                transcript_path, chat_backup_path, stamp, conv_id, transcript_source
            )
            outcomes.chat_backup_created = True
            outcomes.chat_backup_result = "Completed"
        except Exception as e:
            outcomes.chat_backup_result = f"Failed ({e})"
            print(f"[WARN] Chat backup failed: {e}")

    # 5. Root log rotation (always runs)
    outcomes.root_logs_moved = archive_root_logs(project_root, stamp, dry_run=args.dry_run)

    # 6. Git staging candidates for the work products
    files_to_stage: list[Path] = [project_root / ".gitignore"]
    if outcomes.chat_backup_created:
        files_to_stage.append(chat_backup_path)

    # NOTE (H-11): archived root logs under logs/archive/ are intentionally NOT
    # staged. `.gitignore` ignores `logs/` wholesale, so `git check-ignore` would
    # drop them anyway - staging them was dead code that produced misleading
    # output. archive_root_logs() still moves them out of the project root to keep
    # the workspace tidy; they simply remain untracked by design.

    # The agent's own session log must be spotted BEFORE the sweep relocates it into
    # docs/sessions/archive/ -- otherwise place_session_log() inspects a directory the
    # sweep just emptied, never finds it, and writes a duplicate stub alongside it.
    agent_log = find_agent_session_log(project_root)

    # Sweep and archive other directories with archive folders (always runs)
    outcomes.swept_moved, outcomes.swept_failed = archive_all_folders_with_archives(
        project_root, stamp, files_to_stage, dry_run=args.dry_run, keep_globs=args.keep
    )

    # Prune logs/archive/ entries older than logging.archive_retention_days
    # (config.yaml) — archive_all_folders_with_archives only ever MOVES files
    # in, nothing ever deleted them. docs/*/archive/ (git-tracked
    # deliverables) are never touched — scope is logs/archive/ only. Runs
    # AFTER the sweep so this session's own rotated logs are eligible for
    # the SAME pass once they age out, not one run behind.
    from prune_log_archive import _load_retention_days, prune  # noqa: E402

    retention_days = _load_retention_days(project_root / "config.yaml")
    prune_result = prune(
        project_root / "logs" / "archive", retention_days, execute=not args.dry_run
    )
    outcomes.pruned_candidates = prune_result["candidates"]
    outcomes.pruned_deleted = prune_result["deleted"]
    if prune_result["candidates"]:
        verb = "Deleted" if not args.dry_run else "[DRY-RUN] Would delete"
        print(f"{verb} {prune_result['candidates']} log(s) older than {retention_days}d from logs/archive/")

    # Test temp-root sweep, delegated to the shared utility exactly as the log prune
    # above is. The BACKSTOP, not the fix: an oversized temp root almost always means a
    # function-scoped fixture copying bulk data per-test (AGENTS 5.7), and this is what
    # tells you that has regressed. It deletes OLDEST-FIRST only until back under the
    # ceiling -- emptying the root would destroy the scratch of the run that triggered
    # the sweep, since that is the newest thing in there.
    from prune_temp_root import _load_settings  # noqa: E402
    from prune_temp_root import prune as prune_temp

    temp_root, temp_max_gb = _load_settings(project_root / "config.yaml")
    temp_result = prune_temp(temp_root, temp_max_gb, execute=not args.dry_run)
    if temp_result["deleted"]:
        verb = "Deleted" if not args.dry_run else "[DRY-RUN] Would delete"
        print(
            f"{verb} {temp_result['deleted']} oldest entr(y/ies) from {temp_root} "
            f"to bring it under {temp_max_gb} GB"
        )

    if args.dry_run:
        print("[DRY-RUN] Would run git add for staged files.")
        outcomes.staging_result = "Dry run"
    else:
        outcomes.staging_result = "Completed" if run_git_add(project_root, files_to_stage) else "Failed"

    # 7. Session/action logs are written LAST so they record the actual
    #    outcomes of the run (including skips and failures), then staged.
    if args.dry_run:
        print(f"[DRY-RUN] Would create session_log and action_log for {stamp} reflecting run outcomes")
    else:
        placed_log = place_session_log(project_root, session_log_path, stamp, outcomes, agent_log)
        create_action_log(action_log_path, stamp, outcomes)
        staged = [p for p in (placed_log, action_log_path) if p is not None]
        run_git_add(project_root, staged)

    print("\nNext steps:")
    print(f'  git commit -m "docs: auto-save - archive chats and logs for session {stamp}"')
    print('  git push')

if __name__ == "__main__":
    main()
