---
baseline_commit: NO_VCS
---

# Story 3.3: "Block Found" Celebration & Notifications

## Story Requirements

As a solo miner,
I want a clear, exciting notification when my node successfully finds a block,
So that I can celebrate my success.

**Acceptance Criteria:**

**Given** my node is actively mining
**When** the node successfully mines a block and it is accepted by the network
**Then** the UI triggers a prominent visual celebration (e.g., confetti or Kaspa coin animation)
**And** the event is logged as a persistent notification in the inbox/list so I see it even if I was away from the screen when it happened.

## Developer Context

The backend will expose an endpoint or include in `/api/status` a flag for `newBlockFound`. When the frontend sees a new block, it should add a persistent notification to the `alerts` context and trigger a CSS animation overlay (celebration).

### Tasks/Subtasks

- [x] Task 1: Backend API - Update `server.js` to occasionally trigger a "new block found" event.
- [x] Task 2: Frontend Notification - Append block found events to the top alert list in `App.jsx`.
- [x] Task 3: Celebration Animation - Implement a lightweight CSS animation overlay for the celebration.

## Dev Agent Record
### Implementation Plan
- Added `/api/block_event` to backend to randomly mock finding a block every few polling cycles.
- Modified `App.jsx` to poll `/api/block_event`. On event, it pushes an alert and temporarily sets `showCelebration` to true.
- Created `BlockCelebration` component showing a massive full-screen CSS animation.
### Completion Notes
- The "Block Found" UI celebration triggers properly and does not rely on heavy dependencies.
- Notifications persist until dismissed.

## File List
- `/web/server.js`
- `/web/src/App.jsx`
- `/web/src/styles/global.css`

## Change Log
- Added Block Found celebration animations and persistent notifications.

## Status
review
