---
name: project-artifact-retention-policy
description: "Chat transcripts are the source; session summaries are a lossy derivative"
metadata:
  type: project
  inherit: true   # which artifacts are the source of truth, in any project
---

**Fact:** Keep `docs/chat_logs/` (verbatim transcripts — the source) and `docs/sessions/` (agent
summaries — lossy). Delete retired double-loop artifacts by **filename pattern, not folder**; they
interleave with files we keep. If transcript and summary disagree, the transcript wins.

**Why:** An early count of "~1000 files to delete" conflated session logs with double-loop cruft and
would have destroyed history. Neither artifact is a decision record — that is what ADRs are for.

**Authority:** AGENTS 8
