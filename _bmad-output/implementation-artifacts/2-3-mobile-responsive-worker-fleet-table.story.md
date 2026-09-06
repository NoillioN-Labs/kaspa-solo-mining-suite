---
baseline_commit: c46f882c206995a30cac06ced95868bbbade3d13
---

# Story 2.3: Mobile-Responsive Worker Fleet Table with Effort Telemetry

Status: done

## Story

As a miner operating one or multiple ASICs,
I want to inspect granular per-worker telemetry on both desktop and mobile screens,
So that I can spot stale shares, high network latency, or unlucky rounds on any worker instantly.

## Acceptance Criteria

1. **Worker Table Columns & Telemetry (`FR-8`, `UX-DR8`):**
   - **Given** one or more connected ASICs submitting shares to the bridge
   - **When** Marcus opens the **Miners & Workers** tab / view
   - **Then** the worker table renders:
     1. Worker Name (with status badge)
     2. Hashrate (formatted with `formatHashrate` in `Fira Code` monospace)
     3. Shares: Accepted / Stale / Invalid (counts and stale/invalid percentages)
     4. Difficulty (current vardiff target)
     5. Latency (Ping in ms with quality color indicator)
     6. Effort: color-coded badge (<100% lucky green, >100% amber/orange)

2. **Mobile Viewport Optimization (`UX-DR3`, `UX-DR8`):**
   - **When** viewed on mobile screens (<768px)
   - **Then** the worker table cleanly adapts with horizontal scroll wrapper and stacked card layout fallback, ensuring full legibility without clipped data or broken layout.

3. **Real-Time Data Integration (`ARCH-2`, `ARCH-4`):**
   - **Then** the table fetches worker data from `/api/workers` (polled from Stratum Bridge port 3030)
   - **And** when no workers are connected, displays an informative empty state: *"No workers currently connected. Connect an ASIC using stratum+tcp://<lan-ip>:55555"*.

## Tasks / Subtasks

- [x] Task 1: Backend `/api/workers` Endpoint & Schema Validation (AC: 1, 3)
  - [x] Verify `web/server.js` provides `/api/workers` returning worker array with shares, hashrate, diff, ping, and effort
- [x] Task 2: Frontend Worker Fleet Table in `web/src/App.jsx` (AC: 1, 2, 3)
  - [x] Implement `WorkerFleetTable` component with responsive desktop table and mobile card view
  - [x] Add share breakdown percentage formatting, latency ping badges, and color-coded effort badges
  - [x] Add empty state for 0 active workers
- [x] Task 3: Unit & Regression Testing (AC: 1-3)
  - [x] Author `tests/test_story_2_3_workers.py`
  - [x] Verify columns, empty state, effort coloring, and mobile responsive classes
- [x] Task 4: Story Lifecycle & Governance Gate
  - [x] Run full test suite and governance lint
  - [x] Document code review at `docs/code review/story-2-3-review_YYMMDD_HHMM.md`

## Dev Notes

### Relevant Architecture Patterns and Constraints
- Polled every 5 seconds by `web/collector.js` from `http://bridge:3030/api/workers`.
- Effort percentage is computed as `(sharesSub / targetShares) * 100`.

### Source Tree Components Touched
- `web/server.js`: `/api/workers` payload formatting
- `web/src/App.jsx`: `WorkerFleetTable` component
- `tests/test_story_2_3_workers.py`: Automated tests

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### File List
- `web/server.js`
- `web/src/App.jsx`
- `tests/test_story_2_3_workers.py`
