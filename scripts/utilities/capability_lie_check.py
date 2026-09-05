"""
scripts/utilities/capability_lie_check.py
==========================================

A mechanical assist for the **prompt capability lie**: an LLM prompt's
absence-claiming prose ("GENUINELY ABSENT", "IMPOSSIBLE", "NOT SUPPORTED") drifting
stale after the system gains a capability the prompt once correctly called out as
missing. The prompt then actively instructs the model NOT to use something that now
works, and nothing fails -- output just quietly gets worse.

The originating project hit this across four separate epics before an adversarial
reviewer caught it by reading prose against code **by hand**. That is the tell for a
mechanisable check: a human doing string comparison repeatedly, reliably, and late.

WHY THIS IS ADVISORY AND NOT IN governance_lint's CHECKS TUPLE. Matching prose to a
capability registry is a fuzzy keyword-overlap heuristic, not an exact citation check
(unlike `adr-refs`, which matches a regex). A WARNING that fires on fuzzy false
positives on every push trains people to ignore it -- exactly the anti-pattern the
C:-path check already demonstrated once, at 53 warnings of which 50 were noise. **Run
this deliberately** (a retro, a prompt review) and read every finding by hand. It
always exits 0 and never edits anything.

CONFIGURATION (config.yaml `capability_registry`), because a template cannot know
where your project tracks what it can and cannot do::

    capability_registry:
      path: ""                       # JSON list of capability entries. Empty = check skipped.
      resolved_states: [BUILT, COMPOSABLE]   # states meaning "no longer absent"
      state_field: "gap_class"       # entry key holding the state
      id_field: "gap_id"             # entry key holding the identifier
      text_fields: [title, target]   # entry keys whose words are compared to the claim
      prompt_globs:                  # defaults to the AGENTS 5.4 layout
        - "backend/ai_modules/*/*__prompt__*.md"

The prompt glob default is the AGENTS 5.4 convention -- one `__prompt__` file per
agent under `backend/ai_modules/<NN>_<agent_name>/` -- so any project following the
constitution gets a working default with no configuration at all.

Usage
-----
    python scripts/utilities/capability_lie_check.py
    python scripts/utilities/capability_lie_check.py --prompt path/to/some_prompt.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_DEFAULT_PROMPT_GLOBS: tuple[str, ...] = ("backend/ai_modules/*/*__prompt__*.md",)
_DEFAULT_RESOLVED_STATES = ("BUILT", "COMPOSABLE")
_DEFAULT_STATE_FIELD = "gap_class"
_DEFAULT_ID_FIELD = "gap_id"
_DEFAULT_TEXT_FIELDS = ("title", "target")

#: Headings that mark a section as making an absence claim.
_SECTION_HEADING_RE = re.compile(r"GENUINELY ABSENT|IMPOSSIBLE|NOT SUPPORTED", re.IGNORECASE)
_BULLET_CLAIM_RE = re.compile(r"^\s*[*-]\s+\*\*(?P<label>[^*]+)\*\*", re.MULTILINE)
_STOPWORDS = frozenset({
    "a", "an", "the", "of", "on", "in", "to", "and", "or", "not", "is", "are", "for",
    "with", "this", "that", "it", "its", "as", "at", "by", "from", "into", "verified",
})
#: Two shared significant words is the floor before a match is worth a human's time.
#: Tune this and _STOPWORDS against real false-positive experience -- it is a starting
#: point, not a tuned mechanism.
_MIN_SHARED_WORDS = 2


def load_settings(config_path: Path | None = None) -> dict[str, Any]:
    """Read the `capability_registry` block, falling back to AGENTS 5.4 defaults."""
    path = config_path or PROJECT_ROOT / "config.yaml"
    block: dict[str, Any] = {}
    if yaml is not None:
        try:
            with open(path, encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle) or {}
            raw = loaded.get("capability_registry")
            if isinstance(raw, dict):
                block = raw
        except (OSError, yaml.YAMLError):
            pass

    globs = block.get("prompt_globs")
    return {
        "path": str(block.get("path") or "").strip(),
        "resolved_states": frozenset(block.get("resolved_states") or _DEFAULT_RESOLVED_STATES),
        "state_field": str(block.get("state_field") or _DEFAULT_STATE_FIELD),
        "id_field": str(block.get("id_field") or _DEFAULT_ID_FIELD),
        "text_fields": tuple(block.get("text_fields") or _DEFAULT_TEXT_FIELDS),
        "prompt_globs": tuple(globs) if globs else _DEFAULT_PROMPT_GLOBS,
    }


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9_-]{2,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def load_resolved_entries(registry_path: Path, settings: dict[str, Any]) -> list[dict]:
    """Registry entries that are no longer actually absent."""
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[WARN] could not read {registry_path}: {exc}")
        return []
    if not isinstance(data, list):
        print(f"[WARN] {registry_path} is not a JSON list; nothing to compare against.")
        return []
    state_field = settings["state_field"]
    resolved = settings["resolved_states"]
    return [e for e in data if isinstance(e, dict) and e.get(state_field) in resolved]


def extract_absence_claims(prompt_text: str) -> list[str]:
    """Bold-leading bullet labels inside any absence-claiming section.

    Scoped to the section by reading from the heading until the next closing
    pseudo-XML tag (the AGENTS 5.4 prompt convention uses <STEP>/<RULES>-style tags as
    delimiters) or end of file.
    """
    claims: list[str] = []
    for heading_match in _SECTION_HEADING_RE.finditer(prompt_text):
        section_start = heading_match.end()
        end_match = re.search(r"</\w+>", prompt_text[section_start:])
        section_end = section_start + end_match.start() if end_match else len(prompt_text)
        section_text = prompt_text[section_start:section_end]
        claims.extend(m.group("label").strip() for m in _BULLET_CLAIM_RE.finditer(section_text))
    return claims


def find_stale_claims(
    prompt_text: str, resolved_entries: list[dict], settings: dict[str, Any]
) -> list[tuple[str, dict, set[str]]]:
    """(claim, best-matching resolved entry, shared words) for each suspect claim.

    Deduplicated by (claim, entry id): an absence-claiming section can legitimately
    appear more than once (a per-variant prompt repeating the same capability prose),
    and without this the same real finding prints once per repetition -- volume that
    would make a true finding look like noise.
    """
    id_field = settings["id_field"]
    text_fields = settings["text_fields"]
    findings: list[tuple[str, dict, set[str]]] = []
    seen: set[tuple[str, str]] = set()

    for claim in extract_absence_claims(prompt_text):
        claim_tokens = _tokenize(claim)
        best: tuple[dict, set[str]] | None = None
        for entry in resolved_entries:
            blob = " ".join(str(entry.get(f, "")) for f in (*text_fields, id_field))
            shared = claim_tokens & _tokenize(blob)
            if len(shared) >= _MIN_SHARED_WORDS and (best is None or len(shared) > len(best[1])):
                best = (entry, shared)
        if best is None:
            continue
        key = (claim, str(best[0].get(id_field, "")))
        if key in seen:
            continue
        seen.add(key)
        findings.append((claim, best[0], best[1]))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--prompt", type=str, action="append", default=None,
        help="Explicit prompt file(s) to scan, instead of the configured globs.",
    )
    parser.add_argument(
        "--registry", type=str, default=None,
        help="Override capability_registry.path for this run.",
    )
    args = parser.parse_args(argv)

    settings = load_settings()
    registry_str = args.registry or settings["path"]
    if not registry_str:
        # A check that did not run is not a check that passed (AGENTS 6): say so.
        print(
            "[SKIP] capability_registry.path is not set in config.yaml, so there is no "
            "record of what this project can already do to compare prompt claims against."
        )
        return 0

    registry_path = Path(registry_str)
    if not registry_path.is_absolute():
        registry_path = PROJECT_ROOT / registry_path
    if not registry_path.is_file():
        print(f"[SKIP] capability registry not found at {registry_path}.")
        return 0

    prompt_paths = (
        [Path(p) for p in args.prompt]
        if args.prompt
        else [p for pattern in settings["prompt_globs"] for p in PROJECT_ROOT.glob(pattern)]
    )

    resolved = load_resolved_entries(registry_path, settings)
    print(f"Resolved registry entries (no longer absent): {len(resolved)}")
    print(f"Prompt files scanned: {len(prompt_paths)}\n")

    total_findings = 0
    for prompt_path in sorted(prompt_paths):
        try:
            text = prompt_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"[WARN] could not read {prompt_path}: {exc}")
            continue
        findings = find_stale_claims(text, resolved, settings)
        if not findings:
            continue
        try:
            label = prompt_path.relative_to(PROJECT_ROOT)
        except ValueError:
            label = prompt_path
        print(f"[{label}]")
        for claim, entry, shared in findings:
            total_findings += 1
            print(
                f"  WARNING: claims {claim!r} is absent, but registry entry "
                f"{entry.get(settings['id_field'])} ({entry.get(settings['state_field'])}) "
                f"shares: {sorted(shared)} -- verify this claim is still true"
            )
        print()

    if total_findings == 0:
        print("[OK] No claims matched a resolved registry entry.")
    else:
        print(
            f"{total_findings} finding(s) -- advisory only, review each by hand "
            "(fuzzy keyword match, not a citation check)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
