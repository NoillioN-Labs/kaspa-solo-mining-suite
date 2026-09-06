---
baseline_commit: NO_VCS
---

# Story 3.2: Profitability & Fiat Tracking

## Story Requirements

As a miner,
I want to see the fiat value of my mined Kaspa and my estimated daily profitability,
So that I can track the financial performance of my operation.

**Acceptance Criteria:**

**Given** the dashboard is actively monitoring hashrate and rewards
**When** the UI loads
**Then** the backend securely fetches the current Kaspa price from a reliable public API (e.g., CoinGecko) and caches it
**And** the dashboard displays the total mined fiat value and estimated daily profitability based on my average hashrate.

## Developer Context

We need an endpoint (e.g., `/api/fiat`) that returns the current Kaspa price (mocked or fetched from CoinGecko) and total mined/hashrate stats.
The frontend displays this as a widget alongside the Reward Composition.

### Tasks/Subtasks

- [x] Task 1: Backend API - Create `GET /api/fiat` in `server.js` returning mock price data (e.g., $0.15) and estimated profitability.
- [x] Task 2: Frontend Component - Create `ProfitabilityWidget` in `App.jsx`.
- [x] Task 3: Integration - Display the widget on the dashboard.

## Dev Agent Record
### Implementation Plan
- Implemented `/api/fiat` in `server.js` to return a mock fiat value and daily yield.
- Created `ProfitabilityWidget` in `App.jsx` showing "Estimated Daily Profit" and "Current KAS Price".
- Rendered widget alongside the Rewards Composition.
### Completion Notes
- The profitability widget smoothly integrates with the UI layout.

## File List
- `/web/server.js`
- `/web/src/App.jsx`

## Change Log
- Added Profitability & Fiat Tracking widget.

## Status
review
