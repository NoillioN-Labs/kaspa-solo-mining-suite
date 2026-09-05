---
baseline_commit: NO_VCS
---

# Story 2.3: Hardware Health Monitoring & Alerts

## Story Requirements

As a home miner,
I want the dashboard to monitor my ASIC's temperature and fan speeds,
So that I can prevent hardware damage from overheating.

**Acceptance Criteria:**

**Given** an ASIC is connected and mining
**When** the hardware temperature crosses a critical threshold
**Then** the UI displays an alert state that pulses red
**And** a persistent alert is added to the notification list at the top of the dashboard, remaining there until I explicitly acknowledge or dismiss it.

## Developer Context

We need an endpoint (e.g. `/api/health`) that simulates temperature. We can make it fluctuate and occasionally spike above 85C to trigger an alert.
The frontend needs an `AlertsContext` or a `NotificationList` at the top of the dashboard that persists the alert until dismissed.
The health widget itself should display the temp and fan speed, turning pulsing red if temp > threshold.

### Tasks/Subtasks

- [x] Task 1: Backend API - Create `GET /api/health` in `server.js` returning random temp (70-90) and fan speed (4000-6000 RPM).
- [x] Task 2: Frontend Alert List - Add an alert tracking state at the top of `App.jsx`.
- [x] Task 3: Health Widget - Build `HealthMonitor` component to display temp/fans, and trigger alert additions when temp is high.
- [x] Task 4: Dismiss logic - Allow user to dismiss persistent alerts.

## Dev Agent Record
### Implementation Plan
- Implemented `/api/health` in `server.js` with occasional high temp generation.
- Created `HealthMonitor` component and an alerts list rendered just below the Header.
- Set a threshold of 85C. When `temp >= 85`, `HealthMonitor` pulses red and propagates an alert to the main state.
- Alerts render as dismissible banners.
### Completion Notes
- The health system correctly detects spikes and pushes persistent notifications.
- The UI properly pulses red using CSS keyframes when temp is critical.

## File List
- `/web/server.js`
- `/web/src/App.jsx`
- `/web/src/styles/global.css` (added pulse animation)

## Change Log
- Implemented hardware health monitor and critical temperature alerts.

## Status
review
