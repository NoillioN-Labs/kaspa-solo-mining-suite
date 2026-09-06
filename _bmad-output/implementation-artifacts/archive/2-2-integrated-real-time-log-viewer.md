---
baseline_commit: NO_VCS
---

# Story 2.2: Integrated Real-Time Log Viewer

## Story Requirements

As a user troubleshooting a connection,
I want to view the real-time logs of the Stratum Bridge and Kaspa Node directly in the UI,
So that I can diagnose issues without having to SSH into the Umbrel device.

**Acceptance Criteria:**

**Given** the dashboard is active
**When** I open the Log Viewer component
**Then** the backend streams the latest stdout/stderr logs from the respective containers
**And** the UI component auto-scrolls to the bottom by default
**And** it automatically pauses scrolling when I hover my mouse over the log area to read a specific line.

## Developer Context

This requires a backend endpoint to fetch logs (in this MVP, `/api/logs` can just return mock log lines or simulate streaming via polling) and a frontend component `LogViewer` that fetches these logs. The component must handle auto-scrolling to the bottom, which is paused on mouse enter (hover).

### Tasks/Subtasks

- [x] Task 1: Backend API - Create `GET /api/logs` in `server.js` that returns a list of recent log lines.
- [x] Task 2: Frontend Component - Build `LogViewer` in `App.jsx`.
- [x] Task 3: Auto-scroll - Implement auto-scroll to bottom.
- [x] Task 4: Hover Pause - Implement pause-scrolling-on-hover logic.

## Dev Agent Record
### Implementation Plan
- Implemented `/api/logs` returning simulated Kaspa and Bridge logs.
- Created `LogViewer` with `useRef` for the scroll container.
- Added `onMouseEnter` and `onMouseLeave` handlers to track hover state and conditionally auto-scroll via `scrollIntoView`.
### Completion Notes
- The log viewer correctly auto-scrolls to the bottom.
- When hovered, the `autoScroll` state flips to false, pausing the scroll, fulfilling the UX requirement.

## File List
- `/web/server.js`
- `/web/src/App.jsx`

## Change Log
- Added integrated real-time log viewer with auto-scroll and hover-pause behavior.

## Status
review
