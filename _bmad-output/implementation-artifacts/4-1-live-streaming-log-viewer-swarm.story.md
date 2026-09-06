---
baseline_commit: f90999bde561d291162ccf5738c2aa5fbd234e8b
---

# Story 4.1: Live Streaming Log Viewer & Node Swarm Telemetry

Status: done

## Story

As a miner troubleshooting a connection drop or verifying network health,
I want to view real-time container logs and P2P swarm telemetry directly in the dashboard,
So that I can diagnose issues without opening an SSH terminal session on my Umbrel server.

## Acceptance Criteria

1. **Live Container Log Viewer (`FR-12`, `UX-DR12`):**
   - **Given** the dashboard Diagnostic section
   - **When** Marcus views the **Live Logs** console
   - **Then** the UI displays live timestamped stdout/stderr logs from both Stratum Bridge (`[STRATUM]`) and Rusty Kaspad (`[KASPAD]`)
   - **And** the log viewer auto-scrolls to the newest entries, pausing auto-scroll when Marcus hovers over the viewer
   - **And** provides an active/paused status indicator and filter toggle (All / Stratum / Kaspad).

2. **Node Swarm & P2P Telemetry Dashboard (`FR-12`, `UX-DR13`):**
   - **When** Marcus inspects the **Node Swarm & Network** section
   - **Then** the UI displays:
     1. Inbound vs. Outbound peer counter and ratio breakdown
     2. Connected peer table (Peer IP/Host, Ping Latency, User Agent/Version)
     3. Mempool pending transaction counter
     4. P2P Port 16111 listener status (Active/Listening).

3. **Backend Swarm & Log Endpoints:**
   - **Then** `/api/logs` returns log stream with source tagging
   - **And** `/api/peers` returns peer swarm data, mempool count, and port 16111 status.

## Tasks / Subtasks

- [x] Task 1: Backend `/api/peers` & Enhanced `/api/logs` (AC: 1, 2, 3)
  - [x] Add `/api/peers` endpoint to `web/server.js` returning peer swarm info and mempool counter
  - [x] Enhance `/api/logs` with stream tags and level indicators
- [x] Task 2: Frontend LogViewer & NodeSwarmView Components in `web/src/App.jsx` (AC: 1, 2)
  - [x] Enhance `LogViewer` with hover-to-pause auto-scroll, filter buttons (All / Stratum / Kaspad), and clear/copy controls
  - [x] Implement `NodeSwarmView` component showing Inbound/Outbound breakdown, peer table with IP/Ping/Version, mempool count, and Port 16111 status
  - [x] Mount components cleanly in App.jsx layout
- [x] Task 3: Unit & Regression Testing (AC: 1-3)
  - [x] Author `tests/test_story_4_1_swarm_logs.py`
  - [x] Verify endpoints, auto-scroll hover pause logic, peer table structure, and mempool counter
- [x] Task 4: Code Review & Merging
  - [x] Conduct adversarial self-review gate and write `docs/code review/story-4-1-review_YYMMDD_HHMM.md`
  - [x] Mark Story 4.1 as `done` and merge to `main`

## Dev Notes

### Relevant Architecture Patterns and Constraints
- High-density dark UI styling matching Kaspa branding (`var(--kaspa-teal)` #70C7BA).
- Monospace font `'Fira Code', monospace` for IP addresses, latency, and log outputs.
- Hover-to-pause auto-scroll behavior implemented using `onMouseEnter` / `onMouseLeave` state.

### Source Tree Components Touched
- `web/server.js`: `/api/logs`, `/api/peers`
- `web/src/App.jsx`: `LogViewer`, `NodeSwarmView`
- `tests/test_story_4_1_swarm_logs.py`: Automated tests

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### File List
- `web/server.js`
- `web/src/App.jsx`
- `tests/test_story_4_1_swarm_logs.py`
