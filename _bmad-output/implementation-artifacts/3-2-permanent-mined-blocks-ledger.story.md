---
baseline_commit: 75b99d8899eb13b4e6ce93e4776eb7a6d7224af9
---

# Story 3.2: Permanent Mined Blocks Ledger & Reward Analytics

Status: done

## Story

As a solo miner tracking my historical blocks and revenue,
I want an immutable ledger recording every mined block with blue score, worker attribution, effort, reward breakdown, and Explorer links,
So that I have a permanent audit trail of my mining rewards that is never pruned by data retention cleanup.

## Acceptance Criteria

1. **Mined Blocks Ledger View & Columns (`FR-11`, `UX-DR11`):**
   - **Given** one or more solved blocks in `collector.state.minedBlocks`
   - **When** Marcus opens the **Mined Blocks** ledger section / tab
   - **Then** the table displays:
     1. Solve Timestamp (formatted local time) and Blue Score
     2. Winning Worker Name and Effort % at time of solution (color-coded badge)
     3. Reward Breakdown: Subsidy + Fees formatted in KAS and USD equivalent
     4. DAG Confirmation status badge ("Tip Confirmed" / "Accepted")
     5. Block Hash with direct hyperlink pointing to `https://explorer.kaspa.org/blocks/<hash>`

2. **Zero-Loss Permanent Storage Invariant (`AD-5`):**
   - **Then** all mined block records are stored in `telemetry_history.json` under `minedBlocks`
   - **And** are strictly preserved during periodic 24h / 30d / 6m telemetry purges or historical chart resets.

3. **Informative Empty State (`UX-DR15`):**
   - **When** no blocks have been mined yet (`minedBlocks.length === 0`)
   - **Then** displays: *"No blocks mined yet. Active mining on port 55555 will record solved blocks here permanently."*

## Tasks / Subtasks

- [x] Task 1: Backend `/api/rewards` & Permanent Storage Invariant (AC: 2)
  - [x] Verify `web/server.js` exposes `/api/rewards` returning `minedBlocks` array
  - [x] Verify `BackgroundCollectorService.resetData()` preserves `minedBlocks`
- [x] Task 2: Frontend `MinedBlocksLedger` Component in `web/src/App.jsx` (AC: 1, 3)
  - [x] Implement `MinedBlocksLedger` with desktop table and mobile card view
  - [x] Format Blue Score, Worker, Effort %, Reward decomposition (KAS & USD), and direct Explorer links
  - [x] Render informative empty state when 0 blocks mined
- [x] Task 3: Unit & Regression Testing (AC: 1-3)
  - [x] Author `tests/test_story_3_2_ledger.py`
  - [x] Verify table columns, explorer link format, reward decomposition, and permanence across resets
- [x] Task 4: Epic 3 Completion & Retrospective
  - [x] Conduct Epic 3 Retrospective and write `docs/retrospectives/epic-3-retrospective_YYMMDD_HHMM.md`
  - [x] Mark Epic 3 as `done` in `sprint-status.yaml`
  - [x] Pass governance lint and merge to `main`

## Dev Notes

### Relevant Architecture Patterns and Constraints
- Mined blocks ledger records are immutable and permanent (never pruned by AD-5 tiered retention).
- Explorer links open in new tab (`target="_blank" rel="noopener noreferrer"`).

### Source Tree Components Touched
- `web/server.js`: `/api/rewards`
- `web/src/App.jsx`: `MinedBlocksLedger` component
- `tests/test_story_3_2_ledger.py`: Automated tests

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### File List
- `web/server.js`
- `web/src/App.jsx`
- `tests/test_story_3_2_ledger.py`
