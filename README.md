# Kaspa Solo Mining Suite

Master template for harness-engineered AI development projects. It pairs the **BMAD Method** (Product Brief → PRD → Architecture → Epics & Stories → Retrospective, run as agent skills) with a **single-loop coding agent** (plan mode for design, normal execution for build) and **deterministic governance** — the rules that matter are enforced by scripts and CI, not by prose.

All agent-facing rules live in one file: [AGENTS.md](AGENTS.md) (the Project Constitution). Start there.

## Getting Started

1. Run `bootstrap_project.ps1` (right-click → Run with PowerShell, or from a console).
2. Enter the full path for the new project when prompted. The bootstrapper copies the template, cleanses placeholders, creates the venv (`uv sync`), wires the skill junctions, initializes git, and creates a private GitHub repo.
3. Activate the environment: `.venv\Scripts\Activate.ps1`
4. Begin the BMAD lifecycle: invoke the product-brief skill and work forward. Story files in `_bmad-output/implementation-artifacts/` drive implementation.

## Repository Structure

See the Repository Map in [AGENTS.md §3](AGENTS.md) — the constitution's table is the single source of truth for what lives where.

## Governance Mechanisms

| Tool | Run | Purpose |
|---|---|---|
| `scripts/utilities/governance_lint.py` | before ending a session; enforced in CI | Verifies ADR register, upgrade-pack currency, sprint-status freshness, dead links, placeholder leakage |
| `scripts/utilities/sync_sprint_status.py` | after story work | Regenerates `sprint-status.yaml` from story files (`sync`); detects drift (`check`) |
| `scripts/utilities/apply_upgrade.py` | when applying/creating upgrade packs | Atomic ledger-and-delete closing action; `disseminate` pushes new packs to fleet projects; `prune` deletes packs once every fleet ledger records them (both template-only) |
| `scripts/utilities/archive_session.py` | at session end | Compiles the project-matched chat transcript, rotates logs, sweeps historical files into `archive/` folders |

CI (`.github/workflows/agent-lint-check.yml`) runs `ruff check` and the governance lint on every push.

## Skills

- **Global skills** (shared by all projects) live in the `neon-skills` git repository; agent tools discover them through junctions created by the bootstrapper.
- **Project skills** live in `.agent/skills/` and override global skills of the same name.
- New skills are created via the crystallization check at retrospectives — see [AGENTS.md §7](AGENTS.md).

## Requirements

- Windows 11, PowerShell 5.1+
- Python 3.11+ managed by [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock` are committed; `uv sync` reproduces the environment)
- Git + [GitHub CLI](https://cli.github.com/) authenticated to the `phil-neon` account
