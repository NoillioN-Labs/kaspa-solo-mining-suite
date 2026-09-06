---
baseline_commit: 6c37809fa92d53201ad0f13a21678a01afc9326a
---

# Story 3.1: Block Discovery Event Detection & Non-Disruptive Celebration

Status: done

## Story

As a solo miner whose ASIC solves a valid mainnet block,
I want an immediate, non-blocking celebration to fire in the browser with an accent on the winning worker and an updated 24h block counter,
So that I know I hit a block without modal dialogs obstructing my workflow.

## Acceptance Criteria

1. **Block Event Detection & Polling/SSE (`FR-10`, `ARCH-2`):**
   - **Given** an ASIC worker that solves a valid mainnet block template
   - **When** the bridge submits the block to `kaspad` and logs the solution event
   - **Then** the `BackgroundCollectorService` detects the solved block and makes it available via `/api/block_event`
   - **And** returns `blockFound: true`, `hash`, `worker`, `reward`, and `timestamp`.

2. **Non-Disruptive Celebration Experience (`FR-10`, `UX-DR10`):**
   - **When** the frontend detects a block event or receives `block_found`
   - **Then** a celebratory confetti burst fires across the screen (`BlockCelebration`)
   - **And** a non-blocking toast alert displays with block details and Kaspa explorer link
   - **And** the winning worker card/row in the Miners view illuminates with a glowing teal accent border (`#70C7BA`)
   - **And** the "Blocks (24H)" stat card increments immediately.

3. **Interactive Easter Egg Trigger (`UX-DR10`):**
   - **Then** clicking the Kaspa header emblem / logo manually triggers the confetti celebration as an interactive Easter egg.

## Tasks / Subtasks

- [x] Task 1: Backend Block Discovery Event Detection (AC: 1)
  - [x] Enhance `/api/block_event` in `web/server.js` to return `blockFound`, `hash`, `worker`, `reward`, and `timestamp`
  - [x] Ensure `BackgroundCollectorService` records block solution and marks winning worker
- [x] Task 2: Frontend Non-Disruptive Confetti & Winning Worker Glow (AC: 2, 3)
  - [x] Verify `BlockCelebration` confetti canvas animation
  - [x] Add winning worker pulse/glow border (`winningWorkerId`) in `WorkerFleetTable`
  - [x] Wire up Kaspa header emblem click handler as interactive confetti Easter egg
- [x] Task 3: Unit & Regression Testing (AC: 1-3)
  - [x] Author `tests/test_story_3_1_celebration.py`
  - [x] Verify event response format, confetti trigger, worker glow, and Easter egg clickability
- [x] Task 4: Story Lifecycle & Governance Gate
  - [x] Pass full test suite and governance lint
  - [x] Document code review at `docs/code review/story-3-1-review_YYMMDD_HHMM.md`

## Dev Notes

### Relevant Architecture Patterns and Constraints
- Celebration is strictly non-blocking (no modal popups that pause mining or require dismissal).
- Confetti runs for ~4 seconds and self-cleans without memory leaks.

### Source Tree Components Touched
- `web/server.js`: `/api/block_event`
- `web/src/App.jsx`: `BlockCelebration`, `WorkerFleetTable`, `App` header
- `tests/test_story_3_1_celebration.py`: Automated tests

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### File List
- `web/server.js`
- `web/src/App.jsx`
- `tests/test_story_3_1_celebration.py`
