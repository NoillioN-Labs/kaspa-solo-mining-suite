---
baseline_commit: df71179130ab888178bf4629dfcf4db13c81ed29
---

# Story 1.2: Multi-Stage Initial Block Download (IBD) Telemetry & Visualizer

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a home miner watching my node synchronize,
I want the dashboard to explicitly distinguish pruning proof validation from DAA header catchup with real-time ETA,
So that I know exactly which sync stage my node is in without thinking it is frozen.

## Acceptance Criteria

1. **Stage 1 - Pruning Point Proof Validation (`FR-5`, `UX-DR5`):**
   - **Given** a syncing Rusty Kaspad node
   - **When** the node is downloading and verifying the initial pruning point proof (`headerCount` progressing toward ~92,160 headers and `isSynced: false`, `isUtxoIndexed: false`)
   - **Then** the UI sync banner and Kaspa Node card display: *"Validating DAG Pruning Proofs (~92k headers)... Network consensus verification in progress."* with an animated progress pulse.

2. **Stage 2 - DAA Header Catchup with ETA (`FR-5`, `UX-DR5`):**
   - **When** the pruning proof completes and the node catches up headers to the network tip
   - **Then** the UI transitions to **Stage 2 (Header Catchup)**, reporting:
     - Current DAA score vs. network tip target score
     - Progress bar and completion percentage (`(currentDaa / targetDaa) * 100`)
     - Rolling estimated time remaining (ETA) calculated from DAA traversal rate.

3. **Stage 3 - Tip Synchronized State (`FR-5`, `UX-DR15`):**
   - **When** the node reaches the virtual DAA tip (`isSynced: true`)
   - **Then** the UI transitions smoothly to **Stage 3 (Synchronized)**: *"Synchronized (10 BPS) • Mining Active"* with a glowing green status indicator.

4. **Telemetry RPC Endpoint (`ARCH-2`, `ARCH-4`):**
   - **Given** the telemetry backend service
   - **When** client queries `/api/node/sync` or `/api/status`
   - **Then** it returns structured sync state: `{ stage: 1|2|3, stageName: string, headerCount: number, currentDaa: number, targetDaa: number, percent: number, etaSeconds: number | null, isSynced: boolean }`.

## Tasks / Subtasks

- [x] Task 1: Backend Sync Stage Categorization in `web/collector.js` (AC: 1, 2, 3, 4)
  - [x] Query `kaspad:18110` for `getDagInfo` and `getInfo`
  - [x] Implement stage categorization logic (Stage 1: headers < 92k proof, Stage 2: DAA catchup with rolling rate ETA calculation, Stage 3: synced)
  - [x] Expose `/api/node/sync` endpoint in `web/server.js`

- [x] Task 2: Frontend Sync Banner and Progress Card Component (AC: 1, 2, 3)
  - [x] Implement `SyncBanner` and `SyncProgressCard` in `web/src/App.jsx`
  - [x] Render Stage 1 proof validation banner with pulsating animation
  - [x] Render Stage 2 DAA catchup progress bar, percentage, and ETA
  - [x] Render Stage 3 green synchronized badge

- [x] Task 3: Unit and Integration Testing (AC: 1-4)
  - [x] Unit tests for stage categorization and ETA estimation
  - [x] API route tests for `/api/node/sync`
  - [x] Automated regression suite in `tests/test_story_1_2_ibd_sync.py`

## Dev Notes

### Relevant Architecture Patterns and Constraints
- JSON-RPC queries to `kaspad:18110`:
  - `getDagInfo`: returns `virtualDaaScore`, `headerCount`, `blockCount`, `pruningPointHash`.
  - `getInfo`: returns `isSynced`, `isUtxoIndexed`, `p2pId`, `serverVersion`.
- Real data ground truth (`ARCH-4`): zero mock fallbacks; if node is unreachable, report `degraded` or `connecting`.

### Source Tree Components Touched
- `web/collector.js`: Node RPC client & sync stage classification (`computeSyncStage`, rolling DAA rate window)
- `web/server.js`: `/api/node/sync` route & enriched `/api/status`
- `web/src/App.jsx`: `SyncBanner`, `SyncProgressCard`, and `formatEta` UI components
- `tests/test_story_1_2_ibd_sync.py`: Full test coverage across stages 1, 2, and 3

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### File List
- `web/collector.js`
- `web/server.js`
- `web/src/App.jsx`
- `tests/test_story_1_2_ibd_sync.py`
