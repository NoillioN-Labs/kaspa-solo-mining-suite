---
last_reviewed: 2026-09-06
title: Kaspa Solo Mining Suite - Living Architecture Map & Background Telemetry Spine
status: active
---

# Architecture Map: Kaspa Solo Mining Suite

> **This is the single living map** (AGENTS.md section 5.8): components, data flows, module boundaries, and the invariants that hold them together.

---

## 1. System Topology & Container Boundaries

The application executes as three isolated containerized services orchestrated by Umbrel via `docker-compose.yml`:

```
+---------------------------------------------------------------------------------------------------+
| UMBREL HOST ENVIRONMENT                                                                           |
|                                                                                                   |
|  [LAN ASICs] ---> Host TCP 55555 --------------------+                                            |
|  [Browser]   ---> Host TCP 5557 (Tor/App Proxy) -+   |                                            |
+---------------------------------------------------|---|-------------------------------------------+
                                                    |   |
                                 DOCKER BRIDGE NETWORK  |
                                                    |   |
  +-------------------------------------------------v---v----------------------------------------+
  | 1. STRATUM MINING BRIDGE (`bridge`)                                                          |
  |    Image: ghcr.io/noillion-labs/kaspa-stratum-manager:1.3.0                                  |
  |    - Internal Stratum: `:5555` (Mapped to host `55555:5555`)                                 |
  |    - Web Dashboard / Prometheus Metrics: `http://bridge:3030` & `:2114`                      |
  |    - Translates Stratum vardiff mining shares into Kaspa Node block templates               |
  +-------------------------------------------------+--------------------------------------------+
                                                    | RPC Templates (gRPC :16110)
                                                    v
  +----------------------------------------------------------------------------------------------+
  | 2. RUSTY KASPA NODE DAEMON (`kaspad`)                                                        |
  |    Image: supertypo/rusty-kaspad:latest                                                      |
  |    - Public P2P Listening: `0.0.0.0:16111` (Swarm sync)                                      |
  |    - gRPC Interface: `0.0.0.0:16110`                                                         |
  |    - wRPC / JSON-RPC Interface: `0.0.0.0:18110` (High-speed telemetry & DAG traversal)       |
  |    - Persistent Volume: `/app/data` (mapped to `${APP_DATA_DIR}/kaspad_data`)                |
  +-------------------------------------------------+--------------------------------------------+
                                                    ^
                                                    | wRPC / JSON-RPC polling
  +-------------------------------------------------+--------------------------------------------+
  | 3. TELEMETRY AGGREGATOR & WEB SERVICE (`web`)                                                |
  |    Image: ghcr.io/noillion-labs/kaspa-solo-mining-suite:latest                                 |
  |    - Background Daemon: Autonomous polling worker (runs every 5s without browser open)       |
  |    - Internal Database: SQLite / Append-only JSON ring-buffer in `/data/history.db`          |
  |    - Express HTTP & SSE API: `:8080` (Reverse proxied by Umbrel `app_proxy` on port 5557)    |
  |    - Static Frontend Assets: Compiled lightweight React/Vite SPA served from `/public`       |
  +----------------------------------------------------------------------------------------------+
```

---

## 2. Invariants & Architecture Decisions (ADs)

### AD-1: Autonomous Background Telemetry Collector (Non-Browser Dependent)
- **Binds:** The `web` backend daemon lifecycle.
- **Invariant:** Telemetry data collection **MUST NOT** be triggered by, or dependent on, an active browser session.
- **Rule:** The `web` service initializes a standalone background worker (`BackgroundCollectorService`) upon container start. Every 5 seconds, it polls:
  1. `http://bridge:3030/api/workers` and `/api/stats` for live hashrates, worker IP addresses, and share stats.
  2. `kaspad:18110` (JSON-RPC) for `getInfo`, `getDagInfo`, `getConnectedPeerInfo`, and `getFeeEstimate`.
  3. Records samples to persistent storage (`/data/telemetry_history.json` or SQLite).

### AD-2: Strict Multi-Container Isolation
- **Binds:** Service boundaries and failure blast radiuses.
- **Rule:** If the `web` container restarts, mining on `bridge` continues uninterrupted. If `bridge` restarts, `kaspad` maintains DAG sync without restart.

### AD-3: Explicit Port Mapping Standards
- **ASIC Stratum Port:** Host `55555` -> Container `5555` (prevents collision with standard pools or proxies).
- **Web Dashboard Port:** Host `5557` (Umbrel manifest assigned).
- **P2P Node Port:** Host `16111` for Community Store (Outstanding decision recorded for Official Store evaluating `15111` or outbound-only P2P).
- **Internal RPC Ports:** Never exposed on the host; resolved across internal Docker DNS (`bridge:3030`, `kaspad:16110`, `kaspad:18110`).

### AD-4: Real Data Ground Truth (Zero Mock Fallback in Production)
- **Rule:** Mock data generators are restricted strictly to unit testing fixtures (`NODE_ENV === 'test'`). In production, if `kaspad` or `bridge` is offline or syncing, the backend MUST report actual status (`connecting`, `syncing`, `degraded`), real peer count, and genuine 0 hashrate instead of seeded example data.

### AD-5: Tiered Rollup Retention Policy (6-Month Cap)
- **Binds:** Storage footprint and query latency on resource-constrained Umbrel hardware.
- **Invariant:** Telemetry data footprint must not exceed 10 MB total or cause query degradation on low-power devices.
- **Rule:** The background collector persists telemetry using a tiered rollup schedule:
  1. **24-Hour Tier (High Resolution):** 1-minute raw samples (max 1,440 data points).
  2. **30-Day Tier (Medium Resolution):** 15-minute averaged rollups (max 2,880 data points).
  3. **6-Month / 180-Day Tier (Low Resolution):** 1-hour averaged rollups (max 4,320 data points).
  4. Data older than 180 days is automatically purged during the hourly aggregation cycle.
  5. **Mined Block Ledger:** Blocks found, rewards, and solve events are stored permanently in the ledger and are never pruned by the retention lifecycle.

### AD-6: Reset Data Mechanism & Danger Zone Safety Gate
- **Binds:** Administrative telemetry maintenance and user confirmation contract.
- **Rule:** A destructive reset action is provided via `POST /api/data/reset` to wipe all historical hashrate, worker samples, and share statistics.
- **Invariant:** The user interface MUST NOT allow triggering this reset directly without an explicit, interactive warning confirmation modal ("Are you sure? This will erase historical hashrate, shares, and telemetry data. This action cannot be undone.").

---

## 3. Data Flows & Polling Contracts

### Data Flow 1: Live Mining Telemetry
1. `ASIC Worker` submits share to `bridge:5555`.
2. `bridge` records accepted/stale/invalid share and instantaneous vardiff.
3. `BackgroundCollectorService` polls `http://bridge:3030` every 5s.
4. Telemetry is stored and rolled up into 24h, 30d, and 6m resolution buckets.
5. Frontend fetches `/api/stats`, `/api/workers`, or `/api/history?range=24h|30d|6m`.

### Data Flow 2: DAG Sync & Peer Telemetry
1. `BackgroundCollectorService` posts JSON-RPC request to `http://kaspad:18110`:
   ```json
   { "jsonrpc": "2.0", "id": 1, "method": "getDagInfo", "params": [] }
   ```
2. Extracts: `virtualDaaScore`, `headerCount`, `blockCount`, `pruningPointHash`, `difficulty`.
3. Calls `getConnectedPeerInfo` to extract peer IP, ping, direction (inbound/outbound), and version.
4. Synthesizes Sync Progress: `(currentDaa / targetDaa) * 100` and computes rolling ETA.

### Data Flow 3: Block Discovery & Celebration
1. `bridge` discovers valid block matching network target.
2. Bridge broadcasts block to `kaspad:16110` and logs block solve event.
3. Collector detects new block in `getBlocks` or bridge webhook.
4. Emits `block_found` event over SSE `/api/events` to trigger frontend Easter Egg confetti burst.

