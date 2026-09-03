# Task List

> Current-milestone checklist only (see AGENTS.md section 3). Completed milestones are pruned - history lives in git.

- [x] Initialize modular TypeScript backend structure (package.json, tsconfig, dependencies)
- [x] Implement backend ASIC Hardware Presets Catalog (`backend/src/presets.ts`)
- [x] Implement Metrics Engine, 7-Day Moving Averages & Event Store (`backend/src/history.ts`)
- [x] Implement Kaspad Node gRPC / RPC Adapter & Reward Decomposition (`backend/src/kaspad.ts`)
- [x] Implement Stratum Bridge Supervisor (`backend/src/supervisor.ts`)
- [x] Implement REST / SSE API Server (`backend/src/server.ts`)
- [x] Implement unit & integration test suite for backend services (`backend/tests/core.test.ts`)
- [x] Scaffold Vite + React + TypeScript frontend with modern design system (`frontend/`)
- [x] Build UI Components (Overview, MinersTable, PresetsSettings, CelebrationModal with confetti)
- [x] Wire frontend live data stream and block celebration trigger
- [x] Build Umbrel packaging files (`docker-compose.yml`, `umbrel-app.yml`)
