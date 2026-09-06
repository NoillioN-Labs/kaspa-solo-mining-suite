---
baseline_commit: d938fcb9e58d2e86fdf069971a3d5c95c38c3872
---

# Story 2.4: Hardware Tuning Presets & Real-Time Vardiff Control

Status: done

## Story

As a miner with different ASIC models (e.g. IceRiver KS0 vs Antminer KS3/KS5),
I want the bridge to default to Automatic Universal auto-vardiff while providing one-click diagnostic presets,
So that my hardware maintains 15–20 shares/min automatically without manual bridge config file edits.

## Acceptance Criteria

1. **Preset Catalog & Automatic Default (`FR-9`, `UX-DR9`):**
   - **Given** the Hardware Tuning / Presets view
   - **When** Marcus views the tuning options
   - **Then** the active configuration defaults to **Automatic Universal (Auto-Vardiff)**
   - **And** the catalog provides diagnostic presets:
     1. Automatic Universal (Auto-Vardiff, targeting 15-20 shares/min)
     2. IceRiver KS0 / KS0 Pro / KS0 Ultra (Low difficulty, 100 - 400 GH/s)
     3. IceRiver KS1 / KS2 & Mid-Range (Medium difficulty, 1 - 4.5 TH/s)
     4. Bitmain Antminer KS3 / KS5 Pro (High difficulty, 8.3 - 21 TH/s)
     5. Enterprise Hashrate / Multi-Unit Farm (Ultra difficulty, 25+ TH/s)

2. **Real-Time Dynamic Tuning with Confirmation (`FR-9`, `UX-DR9`):**
   - **When** Marcus selects a different hardware preset
   - **Then** the system presents a confirmation prompt explaining the target difficulty change
   - **When** confirmed, the backend updates the active preset via `POST /api/presets/select`
   - **And** updates the Stratum Bridge vardiff parameters in real time without restarting the node.

3. **Active Preset Telemetry Badge (`UX-DR9`):**
   - **Then** the UI reflects the currently active preset badge, difficulty tier, and nominal hashrate range with an active visual indicator.

## Tasks / Subtasks

- [x] Task 1: Backend Presets API (`/api/presets` and `/api/presets/select`) (AC: 1, 2)
  - [x] Verify `web/server.js` exports `PRESET_CATALOG` with all 5 presets
  - [x] Implement `POST /api/presets/select` dynamically setting active preset and vardiff parameters
- [x] Task 2: Frontend `PresetSelector` in `web/src/App.jsx` (AC: 1, 2, 3)
  - [x] Enhance `PresetSelector` with preset cards, active indicators, and modal confirmation prompt
  - [x] Wire up real-time selection and state updating
- [x] Task 3: Unit & Regression Testing (AC: 1-3)
  - [x] Author `tests/test_story_2_4_presets.py`
  - [x] Test catalog defaults, dynamic POST selection, and UI rendering
- [x] Task 4: Epic 2 Completion & Retrospective
  - [x] Conduct Epic 2 Retrospective and write `docs/retrospectives/epic-2-retrospective_YYMMDD_HHMM.md`
  - [x] Mark Epic 2 as `done` in `sprint-status.yaml`
  - [x] Pass governance lint and merge to `main`

## Dev Notes

### Relevant Architecture Patterns and Constraints
- Presets adjust `minDiff`, `maxDiff`, and `targetTime` (seconds per share) in Stratum Bridge.
- Node does NOT restart; vardiff adjustments take effect on the next client share cycle.

### Source Tree Components Touched
- `web/server.js`: `/api/presets` and `POST /api/presets/select`
- `web/src/App.jsx`: `PresetSelector` component
- `tests/test_story_2_4_presets.py`: Automated tests

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### File List
- `web/server.js`
- `web/src/App.jsx`
- `tests/test_story_2_4_presets.py`
