---
baseline_commit: cab534a14eac2acd631493ee933bb193d9fe1c74
---

# Story 4.2: 6-Month Tiered Storage Retention Engine (<4MB Footprint)

Status: done

## Story

As a long-term home miner running on compact Umbrel hardware,
I want historical telemetry downsampled into tiered resolution buckets,
So that I can analyze mining trends over 6 months without expanding disk usage or slowing query latency.

## Acceptance Criteria

1. **Tiered Rollup Storage Structure (`FR-13`, `ARCH-5`):**
   - **Given** continuous mining operations over time
   - **When** metrics are consolidated by `BackgroundCollectorService`
   - **Then** data is structured into 3 distinct tiers:
     - **Tier 1 (24 Hours):** 1-minute averaged samples (~1,440 points max)
     - **Tier 2 (30 Days):** 15-minute averaged rollups (~2,880 points max)
     - **Tier 3 (6 Months / 180 Days):** 1-hour averaged rollups (~4,320 points max)

2. **180-Day Automated Pruning & <4MB Footprint (`FR-13`, `ARCH-5`):**
   - **When** `pruneOldData()` runs
   - **Then** points older than 180 days are pruned from `history6m`
   - **And** total historical JSON footprint remains strictly under 4 MB across 6 months
   - **And** `minedBlocks` records are completely exempt from pruning (`AD-5`).

3. **Multi-Range Frontend Trend Chart (`FR-13`, `UX-DR13`):**
   - **When** Marcus views the Hashrate Trend chart in `web/src/App.jsx`
   - **Then** range selector buttons allow toggling between `24H`, `30D`, and `6M`
   - **And** the chart dynamically loads `/api/history?range=24h`, `30d`, or `6m` and adjusts time labels and resolution tags accordingly.

## Tasks / Subtasks

- [x] Task 1: Backend Tiered Storage Engine & Pruning Invariant (AC: 1, 2)
  - [x] Verify `BackgroundCollectorService` tiered caps (1440, 2880, 4320)
  - [x] Verify `pruneOldData()` purges records older than 180 days while preserving `minedBlocks`
  - [x] Verify total disk payload serialized footprint is < 4 MB
- [x] Task 2: Multi-Range Frontend Hashrate Chart in `web/src/App.jsx` (AC: 3)
  - [x] Enhance `HashrateTrendChart` with `24H`, `30D`, `6M` range buttons
  - [x] Wire dynamic range query to `/api/history?range={range}`
  - [x] Display resolution indicator and peak hashrate per selected range
- [x] Task 3: Unit & Regression Testing (AC: 1-3)
  - [x] Author `tests/test_story_4_2_tiered_storage.py`
  - [x] Verify tiered downsampling caps, 180d pruning, storage footprint < 4MB, and frontend range selectors
- [x] Task 4: Code Review & Merging
  - [x] Conduct adversarial self-review gate and write `docs/code review/story-4-2-review_YYMMDD_HHMM.md`
  - [x] Mark Story 4.2 as `done` and merge to `main`

## Dev Notes

### Relevant Architecture Patterns and Constraints
- Invariant AD-5: Mined Blocks Ledger is permanent and exempt from tiered pruning.
- Compact single-file persistence in `telemetry_history.json`.

### Source Tree Components Touched
- `web/collector.js`: `aggregate1Minute`, `aggregate15Minutes`, `aggregate1Hour`, `pruneOldData`
- `web/src/App.jsx`: `HashrateTrendChart` range selector
- `tests/test_story_4_2_tiered_storage.py`: Automated test suite

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### File List
- `web/collector.js`
- `web/src/App.jsx`
- `tests/test_story_4_2_tiered_storage.py`
