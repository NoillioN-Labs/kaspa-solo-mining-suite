---
baseline_commit: ca1943e061ff63cb478cbfd97607787320494df9
---

# Story 2.1: Autonomous Server-Side Telemetry Collector & Real Data Pipeline

Status: done

## Story

As a home miner running Umbrel headless,
I want the backend to continuously poll Stratum Bridge and Rusty Kaspad every 5 seconds even when my browser is closed,
So that telemetry records are never missed and metrics reflect genuine real-world node data without artificial mocks.

## Acceptance Criteria

1. **Autonomous Daemon Lifecycle (`ARCH-2`):**
   - **Given** the running `web` container
   - **When** the container boots up
   - **Then** a standalone `BackgroundCollectorService` daemon starts immediately without requiring an active browser HTTP or WebSocket connection.

2. **Stratum Bridge Polling (`ARCH-2`):**
   - **Then** the collector polls `http://bridge:3030/api/workers` and `/api/stats` every 5 seconds for live worker hashrates, shares, and vardiff.

3. **Rusty Kaspad RPC Polling (`ARCH-2`):**
   - **Then** the collector queries `http://kaspad:18110` (JSON-RPC) for live DAA tip, header count, and difficulty.

4. **Zero Mock Fallback Discipline (`ARCH-4`):**
   - **Then** in production environments, the collector serves strictly real telemetry (reporting genuine 0 hashrate, syncing, or connecting/degraded status when nodes are unavailable), with mock data generators restricted exclusively to unit test fixtures.

## Tasks / Subtasks

- [x] Task 1: BackgroundCollectorService Lifecycle & Invariant Verification (AC: 1, 2, 3)
  - [x] Verify 5-second interval timer daemon starts unconditionally on module execution
  - [x] Ensure `fetchBridge` queries `bridge:3030/api/stats` and `bridge:3030/api/workers` with timeout guards
  - [x] Ensure `fetchRpc` queries `kaspad:18110` for `getDagInfo`, `getConnectedPeerInfo`, and `getInfo`
- [x] Task 2: Real Data Ground Truth Enforcement (AC: 4)
  - [x] Audit all state initializers to guarantee 0 / real baseline defaults
  - [x] Ensure non-responsive bridge / kaspad returns degraded/connecting state without fabricating numbers
- [x] Task 3: Unit and Integration Testing (AC: 1-4)
  - [x] Author `tests/test_story_2_1_collector.py`
  - [x] Verify daemon polling lifecycle, error tolerance, and zero mock behavior

## Dev Notes

### Relevant Architecture Patterns and Constraints
- Background daemon runs in NodeJS event loop, decoupled from client sessions.
- In-memory rollup buffers update every 60s (24h), 15m (30d), 1h (6m).

### Source Tree Components Touched
- `web/collector.js`: 5s background collector daemon
- `web/server.js`: Server startup & collector lifecycle
- `tests/test_story_2_1_collector.py`: Automated tests

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### File List
- `web/collector.js`
- `web/server.js`
- `tests/test_story_2_1_collector.py`
