---
baseline_commit: c2f27fc09d57a223f6c8d76916a4f91d5754407b
---

# Story 2.2: Reactive Overview Dashboard & 10 BPS GHOSTDAG Canvas Visualizer

Status: done

## Story

As a home miner opening the dashboard,
I want to see my total fleet hashrate, active worker counts, round effort, and a live 10 BPS GHOSTDAG animation,
So that I get an immediate, high-fidelity visual pulse of my mining operation and network consensus.

## Acceptance Criteria

1. **Primary Metric Cards Grid (`FR-7`, `UX-DR7`):**
   - **Given** the Overview dashboard view
   - **When** telemetry is received from `/api/status` or `/api/stats`
   - **Then** four primary metric cards render in an adaptive grid:
     1. **Fleet Hashrate**: dynamically scaled (GH/s, TH/s, PH/s) formatted in `Fira Code` monospace
     2. **Active Miners**: count of online workers connected to stratum port 55555
     3. **Blocks (24H)**: count of solved blocks in the past 24 hours
     4. **Round Effort %**: color-coded badge (<100% lucky green, >100% amber/orange)

2. **Interactive Hashrate Trend Chart (`UX-DR7`):**
   - **Then** an SVG / Canvas area chart renders historical hashrate telemetry (24h 1-minute samples) with gradient area fill under the curve.

3. **HTML5 Canvas 10 BPS GHOSTDAG Visualizer (`FR-7`, `UX-DR4`):**
   - **Then** an animated HTML5 `<canvas>` streams real-time 10 BPS blocks flowing from right to left
   - **And** blocks visually distinguish blue selected consensus blocks (`#70C7BA` / `#3B82F6`) from parallel red blocks (`#F59E0B` / `#EF4444`)
   - **And** subtle DAG parent-child directional edges connect blocks as they traverse the canvas.

## Tasks / Subtasks

- [x] Task 1: Overview Metric Cards Grid in `web/src/App.jsx` (AC: 1)
  - [x] Implement `MetricCardsGrid` rendering Fleet Hashrate, Active Miners, 24H Blocks, and Effort %
  - [x] Apply dynamic scaling format utility (`formatHashrate`) and `Fira Code` styling
- [x] Task 2: Real-Time Hashrate Trend Chart (AC: 2)
  - [x] Implement `HashrateTrendChart` fetching from `/api/history?range=24h`
  - [x] Render smooth SVG area curve with teal gradient fill
- [x] Task 3: HTML5 Canvas 10 BPS GHOSTDAG Visualizer (AC: 3)
  - [x] Implement `GhostdagCanvas` with 10 BPS block generator animation loop
  - [x] Render blue consensus chain and parallel red blocks with parent-child connective edges
- [x] Task 4: Unit & Regression Testing (AC: 1-3)
  - [x] Author `tests/test_story_2_2_dashboard.py`
  - [x] Verify metric card formatting, canvas lifecycle, and trend chart data loading

## Dev Notes

### Relevant Architecture Patterns and Constraints
- Kaspa produces 10 blocks per second on mainnet.
- Canvas animation utilizes `requestAnimationFrame` and cleans up timers on unmount to prevent memory leaks.

### Source Tree Components Touched
- `web/src/App.jsx`: `MetricCardsGrid`, `HashrateTrendChart`, and `GhostdagCanvas`
- `tests/test_story_2_2_dashboard.py`: Automated tests

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### File List
- `web/src/App.jsx`
- `tests/test_story_2_2_dashboard.py`
