# NEON Dev Stack & Skills Harness: Complete Setup & Operating Guide

This guide documents the full architecture, one-time machine installation, global skill connectivity, and step-by-step procedures to instantiate and run projects using the **NEON Dev Stack** with **Google Antigravity** on Windows.

---

## 1. Directory Topology

For seamless skill sharing and automated bootstrapping across all projects, repositories are organized in your workspace directory (e.g. `c:\Users\natha\OneDrive\Documents\Side Hussle\`):

```text
Side Hussle/
├── _NEON-dev-stack/          # The Pristine Master Template (Golden Image)
├── neon-skills/              # Canonical Global Skills Repository (50+ BMAD/Dev skills)
├── _NEON_skills              # Directory Junction -> neon-skills (for backwards/cross-tool compatibility)
│
├── Kaspa Stratum Bridge/     # Your active project (bootstrapped from _NEON-dev-stack)
├── Project_Two/              # Future projects...
└── Project_Three/            # Future projects...
```

---

## 2. One-Time Machine Prerequisites

### A. Python & `uv` (Fast Package Manager)
- `uv` is installed at `C:\Users\natha\.local\bin\uv.exe`.
- `uv` automatically manages isolated Python versions (`Python 3.11`).
- Installed via PowerShell:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  uv python install 3.11
  ```

### B. Git for Windows & POSIX `sh.exe`
- Git is installed. To ensure all pre-commit / pre-push hooks and tests execute cleanly under Windows, ensure `C:\Program Files\Git\bin` is in your User PATH:
  ```powershell
  $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
  [Environment]::SetEnvironmentVariable('Path', "C:\Program Files\Git\bin;C:\Users\natha\.local\bin;$userPath", 'User')
  ```

### C. GitHub CLI (`gh`)
- Installed at `C:\Program Files\GitHub CLI\gh.exe`.
- Authenticate once in your terminal:
  ```powershell
  gh auth login
  ```

---

## 3. Global Antigravity & Claude Skill Wiring

Google Antigravity loads global skills from `~/.gemini/config/skills/`. By creating a single filesystem directory junction, every skill updated in `neon-skills` is immediately available in Antigravity without duplicating files.

### Junction Setup Commands:
```powershell
# 1. Wire Antigravity / Gemini Global Skills
New-Item -ItemType Junction -Path "C:\Users\natha\.gemini\config\skills" -Target "C:\Users\natha\OneDrive\Documents\Side Hussle\neon-skills\skills" -Force

# 2. Wire Claude Compatibility
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills" -Target "C:\Users\natha\OneDrive\Documents\Side Hussle\neon-skills\skills" -Force

# 3. Wire Sibling Junction
New-Item -ItemType Junction -Path "C:\Users\natha\OneDrive\Documents\Side Hussle\_NEON_skills" -Target "C:\Users\natha\OneDrive\Documents\Side Hussle\neon-skills" -Force
```

---

## 4. How to Create a New Project (Instant Setup)

Whenever you want to start a new project:

### Option A: Automated Single-Line Command
From your terminal or agent:
```powershell
powershell -ExecutionPolicy ByPass -File "C:\Users\natha\OneDrive\Documents\Side Hussle\_NEON-dev-stack\bootstrap_project.ps1" -DestinationPath "C:\Users\natha\OneDrive\Documents\Side Hussle\MyNewProject" -NonInteractive -EnvMode E
```

### Option B: Interactive Mode
1. Open PowerShell and run:
   ```powershell
   cd "C:\Users\natha\OneDrive\Documents\Side Hussle\_NEON-dev-stack"
   .\bootstrap_project.ps1
   ```
2. Enter the full path for the new project when prompted.
3. Choose `.env` mode (`E` for empty skeleton, `K` for master keys).

### What the Bootstrapper Does Automatically:
1. **Robocopy Pristine Clone**: Copies template files while excluding cache/temporary files and master-only tools.
2. **Cleanses Identity**: Replaces template names and slugs with your new project name across all configs and docs.
3. **Resets State**: Creates a clean ADR register, resets `task.md`, generates fresh `sprint-status.yaml`, and filters inherited memory.
4. **Provisions Python & Packages**: Runs `uv venv --python 3.11`, `uv sync`, and `uv run playwright install chromium`.
5. **Wires Local Junctions**: Connects `.agent/skills` and local memory caches.
6. **Initializes Git**: Creates initial commit with `.env` leak protection and optionally creates a private GitHub repo.
7. **Verifies Integrity**: Runs `governance_lint.py` and `pytest`.

---

## 5. Daily Development & The BMAD Lifecycle

Once in a project directory, activate the virtual environment:
```powershell
.venv\Scripts\Activate.ps1
```

### Standard BMAD Product Flow:
1. **Product Brief**: Invoke `bmad-product-brief` to frame objectives, problem statements, and scope.
2. **PRD**: Invoke `bmad-prd` to draft detailed functional and technical requirements.
3. **Architecture**: Invoke `bmad-architecture` to generate `_bmad-output/planning-artifacts/ARCHITECTURE.md`.
4. **Epics & Stories**: Invoke `bmad-create-epics-and-stories` and `bmad-create-story` to generate discrete story files in `_bmad-output/implementation-artifacts/`.
5. **Story Implementation**: Work on a `story/<id>-<slug>` branch. Follow the plan and tests.
6. **Story Close**: Run `uv run python scripts/utilities/governance_lint.py`, review findings, and commit.
7. **Retrospective**: At the end of an epic or milestone, invoke `bmad-retrospective` and `crystallize` to promote reusable skills.

---

## 6. Deterministic Governance Command Cheat-Sheet

| Command | Purpose | When to Run |
|---|---|---|
| `uv run python scripts/utilities/governance_lint.py` | Full governance linter (ADR, links, memory, configs) | Before every commit / session end |
| `uv run pytest` | Full automated test suite | After changes / before merging |
| `uv run python scripts/utilities/sync_sprint_status.py sync` | Updates `sprint-status.yaml` from story files | After creating or updating stories |
| `uv run python scripts/utilities/archive_session.py` | Compiles session transcripts and rotates logs | At the end of a session |
| `uv run python scripts/utilities/coverage_gate.py --run` | Measures branch/diff test coverage ratchet | To check test coverage |

---

## 7. Windows Specific Tips & Gotchas

1. **PowerShell Execution Policy**: If PowerShell blocks running `.ps1` scripts, use `-ExecutionPolicy ByPass`.
2. **File Encoding**: All `.ps1` / `.bat` / `.cmd` scripts are saved as UTF-8 without BOM or pure ASCII to prevent PowerShell ANSI string delimiter parsing bugs.
3. **Paths with Spaces**: Always wrap directory paths with spaces in quotes when passing arguments to CLI scripts.
