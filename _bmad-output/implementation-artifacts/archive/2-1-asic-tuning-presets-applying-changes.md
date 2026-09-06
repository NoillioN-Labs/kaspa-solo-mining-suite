---
baseline_commit: NO_VCS
---

# Story 2.1: ASIC Tuning Presets & Applying Changes

## Story Requirements

As a user,
I want to select built-in tuning presets for my specific ASIC hardware from the dashboard,
So that I can optimize mining performance instantly without writing custom bridge configurations.

**Acceptance Criteria:**

**Given** the dashboard is loaded
**When** I select a tuning preset from the dropdown (e.g., IceRiver, Antminer)
**Then** a simple confirmation popup warns me of a temporary mining interruption
**And** upon confirmation, the backend updates the bridge configuration and restarts the bridge service to apply the tuning.

## Developer Context

The backend (`web/server.js`) needs an endpoint to accept a tuning preset (like `KS0`, `KS1`, `Antminer`), update the bridge's `config.yaml`, and gracefully restart the bridge container. In a real environment, it would write to `/data/config.yaml` and maybe use Docker API or send a signal to restart. For this mock/MVP, the backend endpoint `/api/tuning` should just accept the POST request and return success.
The frontend (`App.jsx` or a new component) needs a dropdown, a warning modal (native-looking), and to call the POST endpoint.

### Tasks/Subtasks

- [x] Task 1: Backend API - Create `POST /api/tuning` in `server.js` that accepts `{ preset: "IceRiver" }` and returns success.
- [x] Task 2: Frontend Dropdown - Add a Tuning Preset dropdown to the Settings or Dashboard area.
- [x] Task 3: UI Confirmation - Implement a warning popup when a preset is selected.
- [x] Task 4: Integration - Call `/api/tuning` when confirmed and show a success message.

## Dev Agent Record
### Implementation Plan
- Added `POST /api/tuning` to `server.js`.
- Created `PresetSelector` component in `App.jsx`.
- Implemented standard browser `window.confirm` for the popup (or a custom modal if time permits, but `confirm` satisfies MVP). Actually, a custom modal is better for "Umbrel native" feel.
### Completion Notes
- A custom modal was implemented to match the native dark aesthetic.
- The backend successfully accepts tuning requests.

## File List
- `/web/server.js`
- `/web/src/App.jsx`

## Change Log
- Implemented ASIC tuning preset selection and warning modal.

## Status
review
