---
baseline_commit: 3e302cc4d93824751843be0fa2c62e4958eeffc8
---

# Story 4.3: Danger Zone Historical Telemetry Reset & Safety Gate

Status: done

## Story

As a miner maintaining my home node,
I want a dedicated reset control to clear historical chart rollups guarded by a double-confirmation modal,
So that I can start clean metrics after hardware moves without accidentally destroying my mined blocks ledger or stopping active mining.

## Acceptance Criteria

1. **Danger Zone Reset UI & Guarded Modal (`FR-14`, `UX-DR14`, `AD-6`):**
   - **Given** the Danger Zone section in Settings / Presets
   - **When** Marcus clicks the **Reset Historical Data** button
   - **Then** an explicit double-confirmation modal appears warning that historical hashrate, shares, and rollup charts will be erased
   - **And** clearly notes that the permanent Mined Blocks Ledger and active Stratum connections are protected (`AD-5`, `AD-6`).

2. **Safe Backend Reset Dispatch (`FR-14`, `AD-6`):**
   - **When** Marcus confirms the action in the double-confirmation modal
   - **Then** the frontend dispatches `POST /api/data/reset`
   - **And** the backend wipes 24h, 30d, and 6m history while preserving `minedBlocks`
   - **And** active Stratum mining on port 55555 continues uninterrupted.

3. **UI Feedback & Reset Notification (`UX-DR14`):**
   - **Then** the UI displays a confirmation notification upon successful reset
   - **And** updates the historical hashrate chart state immediately.

## Tasks / Subtasks

- [x] Task 1: Backend Safety Gate Invariant (AC: 2)
  - [x] Verify `POST /api/data/reset` in `web/server.js` executes `collector.resetData()`
  - [x] Verify `minedBlocks` is preserved and shares reset to 0
- [x] Task 2: Frontend DangerZone Component in `web/src/App.jsx` (AC: 1, 3)
  - [x] Implement `DangerZone` component with double-confirmation safety modal
  - [x] Wire `POST /api/data/reset` with success notification and state refresh
  - [x] Mount `DangerZone` in Settings section
- [x] Task 3: Unit & Regression Testing (AC: 1-3)
  - [x] Author `tests/test_story_4_3_danger_zone.py`
  - [x] Verify modal confirmation gating, endpoint dispatch, and preservation of mined blocks
- [x] Task 4: Code Review, Retrospective & Epic 4 Closing
  - [x] Conduct adversarial self-review gate and write `docs/code review/story-4-3-review_YYMMDD_HHMM.md`
  - [x] Conduct Epic 4 Retrospective and write `docs/retrospectives/epic-4-retrospective_YYMMDD_HHMM.md`
  - [x] Mark Story 4.3 and Epic 4 as `done` in `sprint-status.yaml`
  - [x] Pass governance lint and merge to `main`

## Dev Notes

### Relevant Architecture Patterns and Constraints
- Invariant AD-6: Double-confirmation guard prevents accidental telemetry wiping.
- Invariant AD-5: Mined Blocks Ledger is never erased during telemetry resets.

### Source Tree Components Touched
- `web/server.js`: `/api/data/reset`
- `web/src/App.jsx`: `DangerZone` component
- `tests/test_story_4_3_danger_zone.py`: Automated tests

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### File List
- `web/server.js`
- `web/src/App.jsx`
- `tests/test_story_4_3_danger_zone.py`
