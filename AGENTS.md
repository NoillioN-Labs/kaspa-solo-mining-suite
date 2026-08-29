# Project Constitution (AGENTS.md)

The single authoritative rulebook for every agent and developer working in this repository. If any other document contradicts this file, this file wins. Keep it under ~4,000 tokens: a rule may only be added here if it names (a) the value it adds, (b) how it is enforced (mechanism, skill, or core rule), and (c) what is removed to make room.

## 1. Operating Model

- **Single-loop execution.** One coding agent handles both design and implementation: plan first (plan mode / a planning pass reviewed by the user), then execute. There is no separate planning tool, no handoff manifest, and no hand-back report.
- **BMAD lifecycle for ceremony.** Product ideation follows the BMAD Method via skills: Product Brief → PRD → Architecture (+ DESIGN.md for UI) → Epics & Stories → implementation → Retrospective. Planning personas write strategy artifacts to `_bmad-output/`; they do not write application code.
- **Retrospective contract.** A bare "run a retrospective" means: cover everything since the last retro, autonomously and skipping no steps; implement the reversible in-project findings directly; batch every §9 boundary-crossing action into one approval at the end. The full contract lives in the `bmad-retrospective` skill.
- **Story files are the unit of work.** Implementation of planned work starts from `_bmad-output/implementation-artifacts/X-Y-title.story.md` (dash separators, no decimals). Do not improvise requirements that contradict the story; if requirements are ambiguous, ask the user rather than guessing.
- **One story per conversation** (prefer) — context bleed between stories breeds contradictory assumptions. Product projects keep **exactly one standing maintenance epic** (any number; `epic-0` suggested) so chores, defects and upgrades cannot bypass story governance: it never closes, is excluded from velocity, its stories carry acceptance criteria like any other, 3+ related chores promote to a real epic, and it never substitutes for an ADR. *This repo is exempt* — `task.md` is its unit.
- **Model routing.** Use the strongest available model for planning/architecture; mechanical execution may use cheaper tiers. Coding runs bill to the flat-rate subscription — never a pay-per-token API key.

## 2. The Adapter Rule (vendor neutrality)

All governance content, skills, scripts, and enforcement logic MUST be vendor-neutral: no tool-specific names, paths, or syntax in rules or logic. Vendor-specific files are limited to **thin, regenerable adapters** — a one-line loader file importing this constitution, directory junctions for skill discovery, and hook registrations that call the shared Python scripts. Adapters contain zero rules and are recreated by `bootstrap_project.ps1`; losing them must never lose information.

## 3. Repository Map

| Path | Purpose |
|---|---|
| `AGENTS.md` | This constitution (the only always-loaded rulebook) |
| `config.yaml` | All non-secret parameters: models, thresholds, paths, execution modes |
| `.env` | Secrets only; never committed; never printed |
| `task.md` | Current-milestone checklist only; each completed `[x]` triggers auto-save (§8); prune finished work — history lives in git |
| `_bmad/` | BMAD per-project config (installer-managed; overrides in `_bmad/custom/`) |
| `_bmad-output/planning-artifacts/` | product-brief, PRD, **ARCHITECTURE (the single living map — §5.8)**, DESIGN, API-SPEC |
| `_bmad-output/implementation-artifacts/` | `*.story.md`, epics, `sprint-status.yaml` (generated — never hand-edit) |
| `backend/` `frontend/` `tests/` | Application code and verification harness |
| `backend/ai_modules/` | Application LLM prompts/schemas (§5.4) |
| `scripts/utilities/` | Reusable tools incl. the governance scripts (§6) |
| `scripts/scratch/` | One-off scripts; timestamped; archived with `_DEPRECATED` when done |
| `docs/ADR/` | Architecture Decision Records + register |
| `docs/memory/` | The agent's memory cache (§7) — **in-repo and git-tracked**; the vendor's memory path is a junction into it (Adapter Rule) |
| `docs/upgrades/` | Template upgrade packs + `upgrades_ledger.md` (§6) |
| `docs/sessions/`, `docs/chat_logs/`, `docs/retrospectives/`, `docs/code review/` | Session bookkeeping; each has an `archive/` subfolder |
| `client_files/` | Client data — git-ignored, never indexed, no PII leaves this folder |
| `.data/`, `logs/` | Local data and telemetry — git-ignored (only `.gitkeep` tracked) |
| `.agent/skills/` | Project-local skills (canonical location; vendor paths junction here) |

## 4. Workflow

1. **Plan** — understand requirements, verify constraints, present the plan for review before substantive changes. **The simplest thing that works is the default (YAGNI):** the plan names the shortest solution that satisfies the story, and every new dependency, abstraction or layer is justified *in the plan or an ADR, before it is built*. Complexity is a cost, never a default. This constrains the *solution*, never the discipline — it is not licence to skip tests, verification or ADRs. (`/simplify` remediates complexity after the fact; it is not a substitute for not building it.)
2. **Implement** — on a `story/<id>-<slug>` branch (scope in §8); follow the story/plan; write code that matches the surrounding style.
3. **Document** — inline where the code can't speak for itself; ADR for architectural decisions; update the architecture map (§5.8) if structure moved.
4. **Test** — run the suite; drive the affected behavior end-to-end, not just typecheck.
5. **Self-review gate (§4.1)** — mandatory before any claim of "done".
6. **Close** — `governance_lint.py` + ruff; crystallize check (§7); doc/memory updates ride in the *same* commit, never as an afterthought. **A story closes with its code review run, findings dispositioned, and the review artifact at `docs/code review/story-<id>-review_YYMMDD_HHMM.md`; an epic closes with its retrospective run and findings implemented.** Enforced by `governance_lint` (`story-lifecycle`).

### 4.1 Self-review gate — nothing is "done" until this passes

Run an adversarial pass over your **own** work before declaring it done. External review should find nits, not criticals.

1. **Trust boundaries** — malformed/hostile input, missing files, partial state.
2. **Completeness vs ground truth** — the whole entity set, or only the examples you happened to see? **Never truncate the output of a completeness check:** `head`/`tail`/`-First` on a "did I find everything?" query turns a real check into a false negative, and in PowerShell `Select-Object -First` also kills the native command (`StopUpstreamCommandsException`), leaving a bogus `$LASTEXITCODE`.
3. **Verification honesty** — *no assumed-as-verified labels.* A suite you didn't run isn't green; an exit code is not a log (pipelines swallow exceptions — read the log for ERROR/WARNING); a passing test that never exercised the path proves nothing — when in doubt, run the **mutation-battery skill** against it. Before closing, **read the CI result for the ref you are closing and check which jobs actually ran**: a green run whose relevant job never executed is a green run about nothing.
4. **Regression risk** — run the FULL suite; every bug fixed gets a regression test.
5. **Output integrity** — the artifact actually produced is the artifact you claim.
6. **Failure modes** — when it breaks, does it fail *loudly* (§5.5.1)?
7. **Could this PASS be caused *by* the defect?** Name an indicator the failure mode cannot produce. A count of zero is SKIP/UNKNOWN, never PASS — report the subject-set size beside every empty result.
8. **A rollback is an acceptance criterion.** Show the exact undo command, that your identity may run it *after* the forward change, and that post-undo equals pre-change — or record "no rollback" honestly. The remedy gets the defect's evidence standard.

**Decision promotion (anti-amnesia rule).** The moment the user answers a question, states a preference, or makes a decision, record it *before proceeding* — an ADR if it is durable, memory only as a pointer (§7). Never make the user answer the same question twice.

**Template change gate.** Any change to this constitution or the master template needs a stated trigger (incident *or* idea) recorded in the upgrades ledger, plus the three-question test in the preamble.

## 5. Engineering Rules

### 5.1 Configuration & Secrets
- **Zero hardcoding.** Model names, endpoints, paths, thresholds live in `config.yaml`; secrets live in `.env`. Behavior changes via config/CLI flags, never by editing source to flip a toggle.
- **Execution modes** (`process_all`, `sample`, `dry_run`) defined in config; `dry_run` is the default. Before batch/paid runs: run a local count first, report exact impact, get explicit approval. Prefer delta-only execution (process only missing/failed records).

### 5.2 Naming & Timestamps
- Verbose descriptive names everywhere (`api_user_authentication_service.py`, not `auth.py`).
- Every *generated* file (logs, reports, backups, plans, exports) ends with `_YYMMDD_HHMM`. Source code and core config files are exempt.

### 5.3 Logging
- Use `backend/core/logger.py` (`initialize_logging`): structured JSON-lines via structlog, plus an optional hardware-metrics stream (`start_hardware_log`). On init it sweeps stale `logs/*.log` into `logs/archive/` — never leave stale logs in the active folder.

### 5.4 Application LLM Prompts
- Prompts and schemas are external files under `backend/ai_modules/<NN>_<agent_name>/` — one `__prompt__` and one `__schema__` file per agent, COBOL-numbered dirs (10_, 20_ …).
- **Archive-on-write, not archive-on-supersession.** The moment you create or change a live prompt/schema, write an exact copy to that agent's `archive/` under the same name plus `_YYMMDD_HHMM`. A compliance step that happens *after* the interesting work is finished gets skipped, and skipping it leaves no trace. Enforced by `governance_lint.py` (`prompt-archive`).
- **New agents: live filenames carry NO timestamp** (stable import paths). Existing timestamped live files are **grandfathered and must not be renamed** — loaders match on those names, so a rename is a breaking change for no functional gain. Advisory only, by design.

### 5.5 Script Lifecycle
- Reusable → `scripts/utilities/`; deprecation = DeprecationWarning + move to `archive/` + `_DEPRECATED` suffix.
- One-off → `scripts/scratch/` with timestamp; archive with `_DEPRECATED` in the same turn the task completes.
- PowerShell wrappers MUST assert `$LASTEXITCODE` after every native call; silent continuation is prohibited.

### 5.5.1 Native-Windows Execution
**A fallback that silently returns success is a latent incident.** Platform-conditional code either implements the equivalent or fails loudly — it never no-ops into a green test. Enforced by `governance_lint.py` (`script-ascii`, `windows-traps`); CI blocks on it.
- `.ps1`/`.bat`/`.cmd` files are **pure ASCII**, comments included — PowerShell 5.1 reads BOM-less files as ANSI, and a stray em-dash becomes a string delimiter that silently swallows code.
- `Start-Process -ArgumentList` does not quote: wrap interpolated paths (`('"{0}"' -f $path)`) or spaced paths split across argv.
- Call JS entrypoints as `node <bin>.js`; npm `.cmd` shims mis-parse the `&` in the project path.
- One pytest config source per repo (`pytest.ini` silently beats `pyproject.toml`); `zoneinfo` requires a pinned `tzdata` (Windows ships no OS tz database); use `tasklist`/`psutil`, never deprecated `wmic`.
- Not statically checkable, still binding: stamp the *inner* `os.getpid()` when identity matters (the venv `python.exe` is a launcher); treat `Path.exists()` as fallible near legacy symlinks (it *raises* `WinError 1920`, it does not return `False`).

### 5.6 Database (when applicable)
- Append-only; never drop/truncate. Log & Archive pattern: AFTER INSERT/UPDATE triggers clone prior row state to archive tables.

### 5.7 Testing & Dependencies
- pytest + Playwright; failure traces/screenshots auto-saved to `.data/test_artifacts/` (see `tests/conftest.py`). Tests that bill money carry the `paid` marker (deselected by default; run with `-m paid`).
- **Coverage is branch-enabled and ratcheted, not chased to a number.** `coverage_gate.py` (§6) reports line/branch/diff coverage; new code must be covered and total coverage may not regress below the tracked baseline (`docs/coverage_baseline.json`). Advisory until a project sets `testing.coverage.mode: gating`. A % target is a vanity metric — the gate exists to make §4.1's "the path was never exercised" mechanical.
- **Session-scope any fixture that copies bulk data and is only READ**; fixtures whose tests **mutate** the copy stay function-scoped and say why in the docstring (sharing a mutable copy trades disk for cross-test bleed). Find them with `grep -rn "copytree" tests/`. **Suite wall-clock is a bill** — the measured incident lives in the ADR register.
- **Web-UI projects: Playwright E2E + vitest are mandatory, not optional.** A detected frontend without a Playwright config, at least one E2E spec, vitest, and its coverage wired into the ratchet (`extra_coverage_xml`) is a lint ERROR (`frontend-testing`); the `scaffold-frontend-testing` skill stamps the toolchain.
- Generated/scratch paths come from `backend/core/paths.py` (`project_temp_dir`, `new_temp_dir`), never a bare `tempfile` call: the machine-level `TEMP` redirect only reaches processes that inherit it (§5.5.1). Enforced by `governance_lint` (`windows-traps`).
- `uv` manages the environment; `pyproject.toml` (pinned) and `uv.lock` are committed; `uv sync` reproduces the env — **check for a dev extra: a bare `uv sync` can exit 0 leaving `pytest` missing**. No global installs. Before adopting a package or model, check for a better current alternative.
- UI work reads `_bmad-output/planning-artifacts/DESIGN.md` as the styling source of truth.

### 5.8 Architecture Map (living)
- `_bmad-output/planning-artifacts/ARCHITECTURE.md` is the **single living map** — components, data flows, module boundaries and their invariants. It is the map you read to orient before touching unfamiliar code, and BMAD's design-time input. **Exactly one per project; never create a second** (two maps that disagree are worse than none).
- It is **maintained, not archived**: any story that adds or moves structure updates it as part of closing (§4 step 3). Restamp `last_reviewed: YYYY-MM-DD` only when you have actually re-read it against the code.
- Enforced by `governance_lint.py` (`architecture-map`): flags a missing map, a second architecture doc, and a `last_reviewed` older than `knowledge.architecture_max_age_days` (config). Whether the map is *true* needs judgment — that is §4.1's job, not the linter's.

## 6. Deterministic Governance (mechanism over prose)

These scripts — not agent memory — enforce the bookkeeping. CI (`.github/workflows/agent-lint-check.yml`) runs ruff + governance lint on every push.

| Script (`scripts/utilities/`) | Duty |
|---|---|
| `governance_lint.py` | Verifies ADR register, upgrade-pack currency, sprint-status freshness, dead links, template-placeholder leakage, config path integrity, loose stale files. Run before ending any session; CI enforces. |
| `sync_sprint_status.py` | Regenerates `sprint-status.yaml` from the story files (`sync`); `check` fails on drift. |
| `apply_upgrade.py` | Upgrade-pack lifecycle: `record` (ledger row + close-out), `disseminate` and `prune` (**master only — fleet copies refuse**; disseminate additionally requires `--approved-by-user`, §9). Content-compared, ledger-matched on the Upgrade File cell. Pack present = pending work; ledger row = applied. |
| `archive_session.py` | Session close: compiles the project-matched chat transcript, rotates root logs, sweeps timestamped files into `archive/` folders, stages results. Audit logs reflect actual outcomes. |
| `memory_lint.py` | **The third verb** (§7): index drift, dead wikilinks, append-rot, stale refs, and **durable knowledge stranded in scratch**. Advisory, **never CI** — half the calls need judgment (the `memory-lint` skill). Run at every retrospective. |
| `coverage_gate.py` | Branch-and-line coverage as a **ratchet** — the deterministic arm of §4.1 axis 3. Reports line/branch/diff coverage; enforces diff coverage (new lines covered) + no regression below `docs/coverage_baseline.json`, **never a fixed %** (that is a vanity metric). `--run` measures the full suite; `--update-baseline` raises the floor. Advisory until `testing.coverage.mode: gating`; fails loudly when gating (§5.5.1). |

- **`sprint-status.yaml` is generated output and the sole numbering registry.** Never hand-edit it. A story id that appears there is **spent forever**; an id that never appears is one a future story can silently re-use. Interior gaps are therefore a defect — either a story closed without a row, or the id is unreserved — and each must be fixed or explained. An **empty** registry is not a gap: it is the correct state for a project with no stories yet. Enforced by `sync_sprint_status.py check` and `tests/test_sprint_status_integrity.py`.
- **ADRs:** systemic decisions/workarounds → sequential `docs/ADR/NNNN-*.md` + register row (lint-enforced). Superseded ADRs are marked, never silently contradicted.
- **This constitution cites no ADR numbers, and neither may anything a clone inherits.** ADR ids are per-project: a clone starts an empty register and numbers its own from 0001, so a master number is meaningless there — and once the clone's register grows past it, the reference silently *resolves to an unrelated decision*. A dangling pointer is detectable; a resolving-but-wrong one is not. State the rule and cite the AGENTS section that owns it. Enforced by `governance_lint` (`adr-refs`).
- **Upgrade packs:** template learnings are disseminated as instruction packs. Receiving agents apply selectively (read the pack's warning header; surface conflicts to the user), then the agent itself executes `apply_upgrade.py record` to close.
- **Agents execute; users decide.** The user never runs commands. Every command in an instruction file, pack, or skill is the agent's to execute after the user approves the *decision*. Natural-language requests ("apply the upgrade packs") are handled by the global `apply-upgrade-packs` skill — never answered by handing the user a command to run.

## 7. Skills & Memory

- **Global skills** live in the `neon-skills` git repo (canonical, vendor-neutral, private remote). Vendor discovery paths (e.g. the user-level skills directory) are junctions into it — created by bootstrap, per the Adapter Rule. Update = commit + push; every project sees it immediately.
- **Project skills** live in `.agent/skills/` (committed). A project skill overrides a global skill of the same name. Truly project-specific workflows (domain pipelines) stay local.
- **Crystallization check** (retro + on demand): create a skill only when it earns its place — the procedure was needed ≥2 times, took >30 minutes to figure out, is not obvious from docs. Applies beyond this project → global repo; domain-specific → project. Complex multi-role workflows = one orchestrator skill + one subagent per role (own context, restricted tools, per-stage model).
- **Memory is a CACHE, not an archive.** It is the working set loaded at session start so the user never answers the same question twice. It holds *pointers*, not history. **No fact may live only in memory.** The four layers: **ADRs** = what we decided and why (binding, durable — promote aggressively); **session logs** = what happened this session (narrative); **chat archives** = what was literally said (forensic, never indexed, kept as-is); **memory** = what the agent must know before it reads anything (no authority).
- **Memory lives in `docs/memory/`, in-repo and git-tracked** — the vendor's memory directory is a *junction* into it (Adapter Rule §2), created by `bootstrap_project.ps1`. The cache is ours, not the vendor's: delete the junction and nothing is lost. `MEMORY.md` is the index (one line per page, never content) that the agent loads at session start.
- **Memory may hold only what cannot rot:** pointers, why/history, user preferences. Anything that *can* go out of date has an owner elsewhere — a **rule** → this constitution; an **invariant** → the architecture map (§5.8); a **procedure** → a skill; a **decision** → an ADR. Memory points at the owner. One home = one place to fix, so it cannot half-rot. **Never restate a rule in memory:** the copy drifts, and memory is read *first*, so the stale copy beats the truth.
- **Every page is `**Fact:**` / `**Why:**` / `**Authority:**`, under a hard 800-byte cap** (`knowledge.memory_max_page_bytes`). The cap *is* the mechanism — a restated rule does not fit. There is deliberately **no `governance` memory type**. `Authority` must **resolve** (an AGENTS section, an ADR that has a register row, a real file, a registry skill) or be `none (domain gotcha)` — but a decision is never a gotcha.
- **Lifecycle:** create pages only for user preferences, third-party gotchas, or unique syntheses — never task progress or restated rules. Procedures belong in skills, never memory. The commit that retires a feature also fixes every memory page citing it.
- **Revise in place.** Pages are rewritten as current truth, never appended with dated status blocks — one fact smeared across five updates is rot, not memory. `reviewed: true` marks a human-edited page: revise *around* it, never overwrite it wholesale. Enforced by `memory_lint.py` (objective checks); judgment by the `memory-lint` skill.

## 8. Session Bookkeeping & Auto-Save

- **Commit freely; push deliberately.** A push triggers CI, and CI minutes bill to the *account*, not the repo — an over-pushing project darkens every sibling (the twelve-day incident lives in the ADR register). Ten commits pushed once cost the same as one.
- On completing any `task.md` checklist item or plan milestone: update the session log (`docs/sessions/session_YYMMDD_HHMM.md`, one file per session — update, don't multiply), stage docs/config changes, and **commit** `docs: auto-save …`. **Do not push per milestone.**
- **Work on a `story/<id>-<slug>` branch — it is workflow (§4 step 2), not a cost tactic.** Scope: every product/app repo, always; the governance repo for code and constitution changes (docs, session bookkeeping and auto-saves may land on the default branch directly). CI watches only the default branch and named patterns, so story-branch pushes trigger nothing — push as often as you like for off-machine safety. Then merge **locally** and push the default branch **once** per work block, after the local full suite is green: exactly one CI run. Pushing to this repo's own `origin` stays pre-approved (verify with `git remote -v`; `phil-neon` is the GitHub *account*, never a remote alias) — the guard is about batching, not permission.
- ⚠ **An open PR is not a free branch** — `pull_request: synchronize` fires on every push to its head. Open one only as the review artifact for finished work (mechanics: ADR register).
- Enforced by `scripts/hooks/pre-push` **and `pre-commit`** — pre-commit blocks code/constitution commits on the default branch (docs and bookkeeping exempt; override `NEON_ALLOW_MASTER_COMMIT=1`), pre-push batches pushes (override `NEON_ALLOW_MASTER_PUSH=1`). Both installed by `install_git_hooks.py`; an uninstalled guard is silently absent.
- At session end (or on request: "archive our chats"): run `archive_session.py`, then commit and push.
- Only current-session files live in doc-folder roots; everything historical goes to `archive/` (the script enforces this).

## 9. Access Boundaries

"Ask first" = state the exact command/target and wait for explicit approval; silence is no. **Approval covers the action *as described*:** an execution-time measurement that falsifies a material premise of the description lapses the approval — stop and re-ask with the measured truth.

- **Filesystem:** full read/write inside this project root only. Sibling projects: read-only, except their `docs/upgrades/` folder (upgrade-pack dissemination — the only permitted cross-project write). Never write to system paths or user folders outside the project; never read credential stores, browser profiles, or key files (`~/.ssh`, `*.pem`, other projects' `.env`, …).
- **Ask first (destructive):** deleting >10 files or anything you didn't create this session; `git reset --hard`, force-push, history rewrites; any non-SELECT against production-tagged databases; bulk renames/sed across >20 files.
- **Ask first (external):** installing system/global packages; paid API calls beyond the current conversation; pushes to any remote other than this repo's own `origin`; publishing, deploys, emails, posts; new network domains.
- **Review artifacts stay local.** Design, review, and analysis artifacts are authored as self-contained files inside the project structure (design → `_bmad-output/planning-artifacts/`, review → `docs/code review/`, else the relevant `docs/` folder) and reviewed locally in a browser or editor. Never publish them to an external host or hosted-artifact service — external hosting publishes the content. Enforced per-vendor by disabling the artifact-publish tool in the adapter; use the escape hatch only for a deliberate, approved external share.
- **Ask first (dissemination):** **only the master template disseminates — a fleet project NEVER does, and never asks to.** It drafts packs and pushes them to the master's `docs/upgrades/` for review; its own tooling refuses the command (mechanism, not trust). At the master: **never run `apply_upgrade.py disseminate` without the user's explicit approval of *that specific* dissemination.** A pack pushed to the fleet is not a stray file — it is work every project will *act on*. Show the plan (which packs, which projects, why), get approval, only then pass `--approved-by-user`. The flag asserts the user approved; `--yes` merely silences a prompt and is **not** approval. Authoring and refreshing packs locally is fine; pushing them outward is the user's call.
- **Secrets:** never print/log/transmit values matching `*KEY*`, `*TOKEN*`, `*SECRET*`, `*PASSWORD*`; redact accidental exposures immediately.
- **Escape hatch:** "expand scope to X" grants a one-turn exception; "lockdown" freezes all writes/network/process-spawns until released.

## 10. Production Mode

When a project goes live, set `production: true` in `config.yaml` (applied via the production-graduation upgrade pack). This tightens behavior: dry-run defaults locked on, no auto-push to main (branch + review instead), no touching live services without explicit instruction, log rotation and health checks required, and stricter lint rules apply.

## 11. Template Provenance

This file is cloned from the master template by `bootstrap_project.ps1`, which substitutes project-specific paths and names (including URL-encoded forms) and is verified by `tests/test_environment.py` and `governance_lint.py`. Improvements flow back: fix the master first (Golden Image principle), then disseminate via upgrade packs.
