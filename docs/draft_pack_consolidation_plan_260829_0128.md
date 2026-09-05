# Draft-pack consolidation review — 2026-08-29 01:28

**Scope:** every proposed DRAFT upgrade pack in the fleet, reviewed read-only, de-duped and
consolidated into work packages with the decisions each needs. **Updated 08-29 after the
collection sweep:** 19 items (17 packs + 2 skill proposals); every outstanding fleet draft is
now physically in this inbox, including one origin-side revision taken over our stale copy. **Nothing has been applied,
edited in any fleet project, or disseminated.**

**Method:** 16 drafts read in full by a six-reader verification pass; items 17-19 and the #3
revision read directly during the 08-29 collection sweep; every pack's claims
checked against the master's code at HEAD (not taken on trust), with file:line evidence. Fleet
ledgers swept for prior applications (none reference any draft). Verification detail lives in
the workflow transcript; verdicts are summarised here.

---

## 1. Inventory — 19 items, and where they stand against master HEAD

| # | Pack (short name) | Origin | At master HEAD | Asks for |
|---|---|---|---|---|
| 1 | coverage_gate_silent_zero_diff (260820) | Expert tippers | **not absorbed** — `coverage_gate.py:521` still conflates "no new lines" with "gate saw nothing" | master code — *collected into the inbox 08-29* |
| 2 | a_malformed_guard_needs_a_malformed_fixture (260823) | PowerPoint creator | **partially absorbed** — mutation-battery skill carries one of the two claimed instances | global skill (+ optional AGENTS 4.1 clause) |
| 3 | green_local_is_not_green_ci (260823, **revised by the origin 260828 — revision collected 08-29**) | PowerPoint creator | **not absorbed** | AGENTS 4.1 sentence + optional new `ci_status_check.py` |
| 4 | mutation_battery_launcher_deadlock (260820) | Vision AI | **not absorbed** | global skill (mutation-battery trap) |
| 5 | mutate_the_ui_not_just_the_pure_module (260823) | Nineteen | **already absorbed** — shipped to neon-skills `b28cb1c` an hour after authoring; pack never restatused | ratify + close only |
| 6 | control_characters_in_patched_source (260828) | Nineteen | **not absorbed** — and the pack's own supplied fixture carries the defect class it guards (double-escaped `\\n`) | new guard test, after correcting the fixture |
| 7 | ledger_row_must_match_the_upgrade_file_cell (260820) | Vision AI | **not absorbed** — `ledger_contains` is substring-anywhere; a Notes mention reads as "applied" | master code (apply_upgrade.py) |
| 8 | record_dedups_on_filename (260818) | PowerPoint creator | **not absorbed** — **CONFLICTS with #7**: same function, opposite remedy | master code (apply_upgrade.py) |
| 9 | retrospective_follow_through (260820) | Vision AI | **not absorbed** — bmad-retrospective Step 4 only globs `epic-N-retro-*` in implementation-artifacts | global skill (bmad-retrospective) |
| 10 | skill_overlay_never_resolves (260820) | Vision AI | **not absorbed** — BMAD resolver silently ignores overlays for registry-resident skills | `_bmad/scripts/resolve_customization.py` (installer-managed) |
| 11 | skills_registry_path_correction (260820) | Vision AI | **not absorbed** — crystallize skill still names the dead OneDrive registry path | global skill (crystallize) + PATTERNS.md |
| 12 | adr_audit_extension_gap (260818) | PowerPoint creator | **not absorbed** — amends the §4 audit script inside our own **still-pending** adr_number pack | pack amendment before dissemination |
| 13 | reviewed_pages_are_not_exempt_from_the_cap (260820) | Vision AI | **not absorbed** — 4 memory_lint defects confirmed at HEAD; headline one **reverses a deliberate, test-pinned exemption** | master code (memory_lint.py) — owner call |
| 14 | prompt_archive_check_defects (260820) | Vision AI | **partially absorbed** — empty-set SKIP and grandfathering already at HEAD; **confirmed live false-ERROR remains** (stem strips only one stamp, so a correctly archived grandfathered file reads as unarchived) | master code (governance_lint.py) |
| 15 | pass_caused_by_the_defect (260817) | Vision AI | **not absorbed** — the KEYSTONE; five other packs cite or apply its doctrine | AGENTS 4.1 + 9, governance_lint helper, apply-upgrade-packs skill |
| 16 | an_epic_is_not_done_because_its_written_stories_are (260828) | Nineteen | **not absorbed** — master verifiably has BOTH defects (derive-from-files AND epic-status latching at `sync_sprint_status.py:238`) | master code (sync_sprint_status.py) + master's own epics.md repair |
| 17 | branch_discipline_is_workflow_not_bookkeeping (260829) | Nineteen | **not absorbed** — *collected into the inbox 08-29 (from Nineteen's archive/)* | AGENTS 4 step 2 + §8 (small, surgical) |
| 18 | proposed_mutation_battery_skill_amendment (260828) | PowerPoint creator | **not absorbed** — *collected 08-29 from PPT's `drafts/`* — three genuinely new rules, self-de-duped against the skill before proposing: a `CONTROL-BROKE` verdict that aborts the battery (a leaked port/process makes every later verdict INERT for the wrong reason); "an INERT-expected entry is a second control, never a mutation wearing a criterion"; and proving a data-VALIDATING guard by mutating the *data*, where guard-removal being inert is the proof, not a shortfall | global skill (mutation-battery) |
| 19 | proposed_skill_windows_file_contention (260828) | PowerPoint creator | **not absorbed** — *collected 08-29 from PPT's `drafts/`* — a NEW global skill: Windows file/process contention (error-number taxonomy, "a fix can MOVE a race", narrowest-serialising-scope ladder, tests that distinguish a working lock from a lucky schedule, process-tree reaping). Crystallization check run honestly in the proposal: 5 incidents, each >30 min; the existing `resilient-subprocess-orchestration` skill stops at "serialize with threading" | new global skill |

Also verified: the three packs the master applied on 08-17 (source-root, branch-arm, prompts)
are correctly reflected at HEAD, and the packs above quote post-08-17 code — these are new
findings, not stale duplicates of what we already fixed.

## 2. De-dupe and conflict findings

**One direct conflict (needs a choice).** #7 and #8 rewrite the same `cmd_record` dedup:
#8 deletes it outright; #7 re-scopes it to cell-equality against the ledger's Upgrade File
column. **Recommendation: adopt #7 (cell-equality) and close #8 as superseded-by-consolidation**
— it fixes #8's incident (a corrected pack's re-application skipped and destroyed) while
keeping a guard against accidental double-runs, which matters more in the master where
`record` retains the pack. Both packs need master-lens adaptation their fleet-lens text lacks.

**One already delivered.** #5's content shipped to the neon-skills registry an hour after the
pack was written; the pack was never restatused. Close with a ratification ledger row.

**One keystone.** #15 (pass-caused-by-the-defect) is cited or applied by #1, #2, #6, #13, #14
and #16. Deciding it first simplifies everything downstream: its empty-set helper subsumes the
per-check SKIP fixes several packs re-derive, and its axis-3 trim makes the mutation-battery
skill the sole owner of the procedure that three other packs extend.

**Three packs edit the same global skill** (mutation-battery: #2, #4, #5) with interacting trap
numbering — must be applied as one batch, not three sequential edits.

**Three packs touch AGENTS 4.1 axis 3** (#2 optional clause, #3 CI sentence, #15 trim+axes).
The constitution has a ~4,000-token budget and #15 already admits a measured overage in its
origin. **Batch all AGENTS edits into ONE amendment** (with #17's two lines), measure the token
count before/after once, and record one trigger row — not four separate edits.

**The origin revised #3 after delivering it, and the revision changes a decision.** PPT's 08-28
§4.1 addition documents a CI job that is conditional on trigger (`if: github.event_name !=
'push'`), so a push run reported **success while the relevant job never ran** — which undercuts
the pack's own headline advice. D2's sentence must therefore be "check which jobs actually ran
for the ref you are closing", not merely "read the CI result". The revision (a strict superset)
has been taken into the master's copy. *Transferable: a delivered pack is not a frozen pack —
compare content, not filenames, when sweeping (the same rule `disseminate` already applies).*

**Sweep correction, recorded honestly.** The first fleet sweep globbed only
`docs/upgrades/*.md` and missed PPT's `drafts/` subfolder entirely (items 18-19 and the #3
revision). Caught by re-sweeping recursively with content hashes. PPT's `drafts/` convention is
itself worth noting: their README states the subfolder is deliberately invisible to the
`upgrade-packs` pending check because drafts are not pending work — a convention the master may
want to adopt or standardise (folded into Decision 13's scope as a minor point).

### 2a. MECE verification of the five collected items (2026-08-29, against the registry's actual text)

Each of the five was checked pairwise against the 14 existing drafts AND against the live
skill/constitution text it targets — not against pack summaries.

| Item | Verdict | Evidence |
|---|---|---|
| #17 branch_discipline | **CLEAN** — its three replacement targets exist verbatim in AGENTS.md (lines 44, 151, 153); no textual overlap with #15's §9 clause or #3's §4.1 sentence. All three batch into WP-2 without collision | grep-verified |
| #3 revision (§4.1) | **COMPLEMENTARY** — same false-green *family* as #1 (silent_zero) but different instrument (CI jobs vs coverage gate) and different remedy; no duplication | read both |
| #18 rule 1 (`CONTROL-BROKE`) | **CLEAN, cross-link required** — the skill's CONTROL section covers only the inverse direction ("runner reports RED whatever it is given"); trap 13 covers a *different* harness failure (detached battery corrupting a second one). Rule 1 fills the gap between them and must cite both | skill lines 194-201, 371-382 |
| #18 rule 2 (INERT-expected = control) | **NEAR-DUPLICATION — the one MECE catch.** The skill already says "**Never pre-label a mutation 'expected inert' and record it as a pass**" (diagnostic section) — in the exact section #18 says to append to. Verbatim append creates two adjacent near-duplicate rules, and leaves a surface contradiction standing: that paragraph forbids INERT pre-labels while the CONTROL section *requires* them for controls. #18's rule actually RESOLVES the tension (INERT-expected ⇔ control; names-a-criterion ⇒ RED). **Application must be a merge-rewrite of the existing paragraph, not an append** — WP-7 amended accordingly | skill lines 249-253 |
| #18 rule 3 (mutate the data, not the guard) | **CLEAN** — anchors at the three-RED paragraph (skill line 101); the data-validating-guard exemption is genuinely absent; trap 14 (vectors) is a different rule | skill lines 101-102, 152-176 |
| #19 windows-file-contention | **CLEAN as a new skill; boundary sentence required** — `resilient-subprocess-orchestration` (18 lines, verified) keeps launching/orchestration; the new skill takes diagnosis/fix/testing of contention. Its §5 fixture point should cite mutation-battery trap 5 rather than restate it. Minor: #4's uv-lock deadlock is a contention that *blocks* rather than errors — worth one cross-reference line in #19's taxonomy | wc + read |
| #2 residual (re-confirmed) | skill carries instance 1 (`payload.ref` chooser, line 76 area) but NOT instance 2 (render-failure guard with null `preview_error`) — the residual ask is the second instance only | skill lines 71-78 |
| #4 trap numbering | no collision — the skill tops out at trap 14, so "trap 15" is free; #18 is section-anchored, not numbered. Batch order in WP-7: #4 first, then #18, then #2's instance | skill line 152 |

**Stale content inside otherwise-valid packs.** #14's §2 snippet patches a function that no
longer exists at HEAD; #1's snippet calls a `_run_git` helper the master doesn't have; #16's
control test would fail on a fresh clone (the exact defect class we repaired on 08-16) and
assumes a maintenance-epic concept the master lacks. Absorb by intent, never verbatim.

**Pack hygiene is now an operational problem.** `governance_lint` is **FAILING at HEAD with 31
errors** — inherited ADR-0018/0019/etc. citations inside the inbox drafts (our `adr-refs` check
scans `docs/upgrades/*.md`, exactly as designed). Also recurring: closing commands that don't
parse (`--status Applied`, `--status applied|partial` placeholders, cmd.exe `^` continuations,
missing `--yes` — the same two incidents our own test_apply_upgrade pins), two packs with no
closing section at all, and one pack with no Status line. The 14 inbox drafts are also
**untracked in git** — the "canonical library existed only on disk" defect from 08-15, again.

## 3. Consolidated work packages

Everything below is applied at the **master only**; dissemination is a separate, later approval.

- **WP-1 — Inbox hygiene (first; no decisions).** Strip inherited ADR ids and fix/add closing
  commands across all drafts as they are absorbed or amended; restatus #5 and #17; collect #17
  and the stranded Expert tippers #1 into the inbox; then git-track the library. Clears the 31
  lint errors. Each content amendment is recorded in the pack's own header, per convention.
- **WP-2 — The single AGENTS amendment.** #15's axes 7+8 and §9 approval-lapse clause, paid for
  by the axis-3 trim; #3's read-the-CI-result sentence; #2's optional one-clause pointer; #17's
  two branch-discipline lines. One edit, one token measurement, one trigger row. (Decisions 1-4.)
- **WP-3 — apply_upgrade ledger matching.** #7's cell-equality parser + rewired
  record/disseminate/prune + tests; #8 closed as superseded. (Decision 5.)
- **WP-4 — coverage_gate untracked-files arm.** #1, adapted to the master's structure; new test
  + mutation. (Decision 6: WARN vs FAIL-under-gating.)
- **WP-5 — sprint-status epic roster + latching.** #16 with master adaptations: fix latching
  (re-derive + drift flag), roster derivation, fresh-clone skip handling, and repair the
  master's own epics.md (missing Story 1.3 heading — verified). (Decision 7.)
- **WP-6 — governance-check repairs.** #14 stem fix (+ optional marker widening), #13
  memory_lint fixes (Decision 8 on the reviewed-pages exemption reversal), #6 control-character
  guard with corrected fixture, #12 amendment to the pending adr_number pack **before** it ever
  disseminates. (Decisions 8-9.)
- **WP-7 — global skills registry batch.** One coordinated edit set, in this order per §2a:
  mutation-battery — #4's trap 15 first, then #18's three rules (**rule 2 as a merge-rewrite of
  the existing "never pre-label expected inert" paragraph, never an append** — it resolves that
  paragraph's standing tension with the CONTROL section; rule 1 cross-references traps 6 and 13),
  then #2's missing second instance, #5 ratified; bmad-retrospective Step 4 (#9); crystallize
  path fix (#11); apply-upgrade-packs four rules (#15 §4); and — if D13 approves — the **new
  `windows-file-contention` skill (#19)** with an explicit boundary sentence versus
  `resilient-subprocess-orchestration`, its §5 fixture point citing mutation-battery trap 5
  rather than restating it, and one cross-reference line for #4's blocks-rather-than-errors
  contention case. **Note for the owner:** a registry edit
  lands in every project instantly, bypassing the pack/approval machinery — that reach is why
  it's batched and listed here rather than just done. (Decision 10.)
- **WP-8 — BMAD resolver overlay fix.** #10; pick fix A/B/C; installer-managed file, so the
  change diverges from the installer until pushed upstream. (Decision 11.)
- **WP-9 — outbound queue (LAST, ask-first).** The three packs approved-but-never-disseminated
  on 08-17 (source-root, branch-arm, prompts) plus whatever the above absorbs; Nineteen joined
  the fleet after the last dissemination and needs a gap-check against the library. (Decision 12.)

## 4. The owner's five topics, mapped — **all five now answered by the 08-29 feedback (see §7)**

1. **Archive session** — no draft touches `archive_session.py`. Needs your requirements: what
   should change? (Nearest related work: WP-3's ledger matching and #15's §9 clause.)
2. **Building work plans** — nothing exists today beyond one ad-hoc
   `docs/workplan_next_session_*.md`. No draft covers it. Candidate: a global skill defining the
   workplan artifact (shape, where it lives, how sessions consume it). Needs your requirements.
3. **Epics & stories doco** — WP-5 fixes the *mechanics* (epic status truth). If you also want
   the *documentation conventions* changed (epics.md format, story templates), that's new
   scope: say what you want different.
4. **UI testing** — the fleet already moved: mutation-battery UI traps (#5, shipped) and the
   scaffold-frontend-testing skill exist. Gap unknown — what's missing for you? (E.g., UI
   testing scaffolding in the template itself rather than on-demand?)
5. **Git branching for features** — #17 answers this directly (branching filed under Workflow,
   scope stated per repo type). Approving WP-2 delivers it.

## 5. Execution plan and sequencing (revised 2026-08-29 after owner acceptance + feedback)

### Phase A — apply everything at the MASTER, in this order

| Step | Work | Why this position |
|---|---|---|
| A1 | **apply_upgrade.py fixes**: #7 cell-equality ledger matching (supersedes #8) **+ C7 dissemination lockdown** (`disseminate`/`prune` hard-refuse outside the master: "Only the master disseminates — draft and push to master's docs/upgrades/ for review") | First, because every later step writes ledger rows through `record`, and its matching is what #7 fixes; C7 shares the same file and tests |
| A2 | **The single constitution edit** (one commit, token count measured before/after): #15 axes 7+8 + §9 approval-lapse; #3's "check which jobs ran for the ref" sentence; #17's two branch lines; C3's discipline bullet (review artifact per story, retro per epic); C5's frontend-testing sentence; **C8 diet** — rationale prose moved out to new master ADRs (§8 CI-cost narrative, §5.7 fixture anecdote, §7 memory rationale trims), targeting net-negative tokens despite the additions | Rules before mechanisms; one trigger row; the diet pays for the additions |
| A3 | **Hooks (C4/D15)**: new pre-commit guard (code paths blocked on the default branch, docs/bookkeeping exempt, override `NEON_ALLOW_MASTER_COMMIT=1`) + `install_git_hooks.py` extension; #17's pack amended to carry it | Enforcement for the rule A2 just wrote |
| A4 | **Master code fixes**, each with tests + mutations, full gates between: #1 coverage silent-zero; #16 epic roster + latching + epics.md repair + C6's drift arm (governance_lint runs `sync_sprint_status.py check`); #14 stem fix + marker widening; #13 memory_lint four fixes; #6 control-character guard (fixture corrected); #12 amendment to the pending adr_number pack; **C2 archiver keep-rules** (newest `workplan_next_session_*` stays + `--keep <glob>`); **C5 frontend-testing lint check** (web UI detected ⇒ Playwright config + ≥1 E2E spec + vitest + coverage wiring, ERROR); **C3/D14 lint arms** (story done ⇒ review artifact; epic done ⇒ retro row done) | The bulk; every item already verified against HEAD |
| A5 | **Registry batch (WP-7, order per §2a)** + WP-8 resolver fix B: mutation-battery (#4 trap 15 → #18 merge-rewrite → #2 second instance → #5 ratified), bmad-retrospective, crystallize, apply-upgrade-packs (four #15 rules **+ D16's apply-order line**), **NEW `session-stocktake` skill (C1)**, **NEW `windows-file-contention` skill (#19/D13)**, bmad-dev-story + bmad-create-story close-ritual edits (C3 artifact, C6 numbering) | Registry edits land fleet-wide instantly — do them once the master's rules exist |
| A6 | **Author/refresh every outbound pack** incl. the **000 apply-order manifest (D16)**; every pack closing command parse-tested; full suite + ruff + lint; ledger rows throughout | Ship-ready state |

### Phase B — disseminate to the fleet (SEPARATE approval at execution time, §9)

One scoped `--only` run shipping, in the order the 000 manifest enforces in each project:

1. `upgrade_instructions_000_apply_order_*` — read first, closed last
2. apply_upgrade fixes pack (A1) — so every subsequent `record` in that project writes true rows, and their own `disseminate` locks itself out (C7)
3. constitution pack (A2+A3, incl. hooks + installer)
4. code packs (A4) — any order among themselves
5. registry-skill verification step only (content already live via junctions; each project confirms its junction resolves — #10/#11's lesson)
6. per-project: gap-check (Nineteen never received the earlier waves; PPT's ledger-skip hand-delivery cases from 08-16 recur here — the 000 manifest instructs re-checking content, not filenames), verify per pack, record rows, close 000 with the sequence confirmation

Also riding in Phase B: the 08-17 trio (source-root, branch-arm, prompts) still undisseminated, and the amended adr_number pack (#12 applied first).

## 6. Decisions — **ALL ACCEPTED by the owner, 2026-08-29** (D1–D13 per recommendation; D14–D16 below resolved by direct question)

| # | Decision | Recommendation |
|---|---|---|
| D1 | AGENTS 4.1 axes 7+8 and the §9 approval-lapse clause (#15), paid for by the axis-3 trim — accept? Token overage is real and measured. | Accept; the doctrine already proved itself six times across the fleet |
| D2 | #3's CI sentence — **revised per the origin's 08-28 update**: the sentence must say "check which jobs actually ran for the ref you are closing" (a green run whose relevant job was conditional-on-trigger is a green run about nothing). Prose-only, or also build `ci_status_check.py`? | Prose now, with the jobs-ran wording; mechanism as follow-up |
| D3 | #2's optional AGENTS pointer, or skill-only? | Skill-only (the pack's own recommendation); skip the pointer |
| D4 | #17 branch-discipline lines — accept? | Accept as written; it answers your own question |
| D5 | Ledger-matching conflict: #7 cell-equality (keeps a re-scoped guard) vs #8 delete-the-dedup | #7; close #8 as superseded |
| D6 | Coverage untracked-files arm severity | WARN default; FAIL when `mode: gating` |
| D7 | Epic roster + latching fix, including repairing the master's epics.md | Accept with the fresh-clone adaptations |
| D8 | Reverse the deliberate `reviewed: true` cap exemption in memory_lint (permanent warnings on long curated pages) | Accept — an exemption one frontmatter line can grant is not a cap |
| D9 | Widen the prompt-archive marker to `__prompt`/`__schema` (origin-style names) as well as fixing the stem? | Yes to both; the widening is a harmless superset here |
| D10 | Approve the registry batch (WP-7) — instant fleet-wide reach | Approve as one batch; that reach is also worth a standing think |
| D11 | BMAD resolver fix choice: A (root-find from as-passed path) / B (require `_bmad/`) / C (explicit flag) | B — verified to work for this fleet today, smallest surface |
| D12 | Dissemination of the 08-17 trio + newly absorbed packs, incl. Nineteen catch-up | Defer until WP-1..8 land; then one scoped `--only` run for approval |
| D14 | **ACCEPTED:** every story closes with a persisted review artifact (`docs/code review/story-<id>-review_<stamp>.md`), lint-enforced; every epic 'done' requires its retrospective row done | — |
| D15 | **ACCEPTED:** pre-commit hook hard-blocks code commits on the default branch (docs/bookkeeping exempt per #17's scope clause), documented override `NEON_ALLOW_MASTER_COMMIT=1`, installed by `install_git_hooks.py` | — |
| D16 | **ACCEPTED:** dissemination ordering via a manifest pack `upgrade_instructions_000_apply_order_*` (sorts first, matches PACK_PATTERNS) + one line in the apply-upgrade-packs skill: if an apply-order pack is present, follow it | — |
| D13 | Create the `windows-file-contention` global skill (#19)? Its crystallization check passes honestly (5 incidents, each >30 min, fleet-wide applicability); overlaps `resilient-subprocess-orchestration` only at one sentence. Minor rider: standardise PPT's `drafts/` subfolder convention for proposal documents? | Create it, cross-linked from resilient-subprocess-orchestration; adopt the drafts/ convention |

**Open questions on your topics (no drafts cover these):** what changes do you want to archive
session (topic 1), work plans (topic 2), epics/stories documentation beyond WP-5 (topic 3), and
UI testing beyond what shipped (topic 4)?

## 7. Owner feedback 2026-08-29 → work items (all accepted into the plan)

| # | Comment | Disposition |
|---|---|---|
| C1 | End-of-session stocktake + next-plan boilerplate | **NEW global skill `session-stocktake`** (A5), not a BMAD persona — it spans PM/SM/retro and is invoked by "stocktake" / "prepare the next session". Produces: progress table from code-reviews/retros/backlog/sprint-status; blockers + interdependencies; sequencing rationale; the next-session workplan at the standard location (`docs/workplan_next_session_YYMMDD_HHMM.md`); the questions/permissions list; and the copy-paste kickoff text. Registry work — no pack needed |
| C2 | Archive session without moving the files the next session needs | **NEW pack** (A4): `archive_session.py` keeps the NEWEST `workplan_next_session_*` in place (older ones archive as normal) and gains `--keep <glob>` for associated files, printing what it kept and why. Pairs with C1: the skill writes to exactly the location the archiver protects |
| C3 | Code reviews after each story, retros after each epic, findings implemented | **D14 accepted**: constitution bullet (A2) + lint arms (A4: story done ⇒ `docs/code review/story-<id>-review_*` exists; epic done ⇒ retro row done) + dev-story close-ritual edit (A5). Merged with C6 into one "story lifecycle discipline" pack |
| C4 | Branching under-used; work landing on main | **D15 accepted**: pre-commit hard block on code paths on the default branch, docs/bookkeeping exempt (exactly #17's scope clause), override env var, installer-managed (A3). #17's pack amended to carry the mechanism, since its own text says an unenforced rule is what it is fixing |
| C5 | Web-UI projects must strictly enforce Playwright testing | **NEW pack** (A4): `frontend-testing` lint check — when a web UI is detected, require Playwright config, ≥1 E2E spec, vitest, and frontend coverage wired into the ratchet (`extra_coverage_xml`), at ERROR; AGENTS 5.7 sentence (A2); `scaffold-frontend-testing` cited as the remedy |
| C6 | Epic/story numbering drift; sprint-status not updated | #16 (accepted D7) fixes the epic half; **plus** governance_lint gains a blocking drift arm running `sync_sprint_status.py check` (A4), and bmad-create-story consults the registry for the next id at creation (A5). Merged with C3's pack |
| C7 | ONLY the master disseminates — fleet projects draft and push up, full stop | **Merged into A1's pack**: `disseminate` and `prune` hard-refuse outside the master with the message stating the rule; AGENTS 9's dissemination bullet gains the one-line absolute ("fleet projects never run it"); test + mutation. After Phase B every fleet project's own tooling refuses, so the question can never be asked again |
| C8 | AGENTS.md too large — pull concepts into ADRs | **Folded into A2's diet**: rules stay in AGENTS; rationale moves to master ADRs (candidates: §8's CI-cost narrative, §5.7's fixture anecdote, §7's memory-architecture rationale). Token count measured before/after and reported — the same discipline #15 demands. The constitution pack carries the moved rationale in its own text so receiving projects can copy it into their own ADRs if they wish |
