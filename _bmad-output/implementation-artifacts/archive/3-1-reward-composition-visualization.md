---
baseline_commit: NO_VCS
---

# Story 3.1: Reward Composition Visualization

## Story Requirements

As a user,
I want to see exactly how my mined rewards are broken down into Block Subsidies, Accepted Fees, and DAG rewards over time,
So that I understand where my Kaspa is coming from.

**Acceptance Criteria:**

**Given** the node has mined at least one block
**When** I view the Rewards Breakdown card on the dashboard
**Then** the backend queries the Kaspa Node RPC exclusively to retrieve the exact block reward split
**And** the UI renders this as a stacked bar chart with distinct colors/patterns
**And** hovering over the chart reveals a tooltip with exact numbers and timestamps.

## Developer Context

For this UI implementation, we will use a pure CSS flexbox approach to create a stacked bar chart rather than importing a heavy charting library, adhering to the "extremely lightweight" NFR.
The backend (`/api/rewards`) will serve a list of historical blocks, each with `subsidy`, `fees`, and `dag` reward values.

### Tasks/Subtasks

- [x] Task 1: Backend API - Create `GET /api/rewards` returning an array of objects with timestamps and reward splits.
- [x] Task 2: Frontend Component - Create `RewardsChart` component in `App.jsx`.
- [x] Task 3: UI Implementation - Build CSS-based stacked bar chart.
- [x] Task 4: Interaction - Add native `title` tooltips for hover data.

## Dev Agent Record
### Implementation Plan
- Implemented `/api/rewards` returning mock data.
- Created `RewardsChart` component using flexbox columns.
- Mapped block rewards to percentage heights for Subsidy, Fees, and DAG components.
- Added standard `title` attributes on segments for tooltip hovers.
### Completion Notes
- The stacked bar chart works entirely via lightweight HTML/CSS without dependencies.
- Distinct colors correctly show the split.

## File List
- `/web/server.js`
- `/web/src/App.jsx`

## Change Log
- Added Reward Composition Visualization stacked bar chart.

## Status
review
