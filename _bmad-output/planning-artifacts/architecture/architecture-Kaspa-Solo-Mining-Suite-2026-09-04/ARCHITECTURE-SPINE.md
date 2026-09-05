---
title: Kaspa Solo Mining Suite - Architecture Spine
status: final
created: 2026-09-04
updated: 2026-09-04
---

# Architecture Spine

## 1. Paradigm
**Docker Compose Orchestration (Umbrel OS Standard).** The application is a multi-container stack orchestrated via `docker-compose.yml` to fit natively within the Umbrel OS ecosystem. The web layer aggregates telemetry and logs from the underlying mining infrastructure without owning the core mining logic.

## 2. Invariants (ADs)

### AD-1: Multi-Container Separation of Concerns
- **Binds:** The application structure.
- **Prevents:** A monolithic "fat container" that breaks when one component crashes.
- **Rule:** The stack MUST be separated into at least three distinct Docker services:
  1. `kaspad`: The Rusty Kaspa node (maintaining the DAG).
  2. `bridge`: The Kaspa Stratum Bridge (handling stratum protocol and ASIC connections).
  3. `web`: The Node/Express backend and React frontend (providing the dashboard, RPC aggregation, and settings management).

### AD-2: Explicit Port and Volume Mapping
- **Binds:** Network and persistent storage definitions.
- **Prevents:** Port collisions with existing mining proxies and data loss on restart.
- **Rule:** The Stratum Bridge MUST map to host port `55555` rather than `5555`. The `kaspad` data directory MUST map persistently to `/app/data` with host-writeable permissions (e.g., `0777` or matching UID `50051`) via `pre-start` hooks to ensure stability.

### AD-3: Telemetry Aggregation Strategy
- **Binds:** How the Web Dashboard acquires data.
- **Prevents:** The frontend directly polling the mining bridge or node (CORS/security issues).
- **Rule:** The `web` backend acts as an aggregator. It polls the `bridge` for ASIC hashrate/shares and polls the `kaspad` RPC for Node Sync status and Reward Composition (Subsidies, Fees, DAG rewards). The frontend receives this via a unified JSON REST API or WebSocket from the `web` backend.

### AD-4: Reward Composition Extraction
- **Binds:** The source of truth for Kaspa rewards.
- **Prevents:** Inaccurate or hardcoded block reward assumptions and fragmented data fetching.
- **Rule:** To visualize the split between Block Subsidies, Accepted Fees, and DAG rewards, the backend MUST query the Kaspa Node RPC exclusively. No other data sources will be used for this metric.

### AD-5: Frontend Technology Stack
- **Binds:** Web dashboard implementation.
- **Prevents:** Heavy, slow-loading frameworks that compete for CPU with the bridge.
- **Rule:** The frontend MUST be implemented as a lightweight React SPA (e.g., Vite) utilizing CSS Modules or Tailwind to replicate Umbrel's native Design System.

## 3. Deferred Decisions
- **Log Streaming Protocol:** Whether the backend streams Kaspad and Bridge logs to the frontend via WebSockets or HTTP long-polling is deferred to the implementation phase.
- **Storage for Profitability/Fiat Data:** Whether historical fiat conversion rates are cached locally in SQLite or fetched dynamically on load is deferred.
