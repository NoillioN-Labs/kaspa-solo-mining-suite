---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - "prds/prd-Kaspa-Solo-Mining-Suite-2026-09-04/prd.md"
  - "ARCHITECTURE.md"
  - "ux-designs/ux-Kaspa-Solo-Mining-Suite-2026-09-04/DESIGN.md"
  - "ux-designs/ux-Kaspa-Solo-Mining-Suite-2026-09-04/EXPERIENCE.md"
---

# Kaspa Solo Mining Suite (Umbrel All-In-One Edition) - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Kaspa Solo Mining Suite (Umbrel All-In-One Edition), decomposing the requirements from the PRD, UX Design contract, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR-1: Must bundle official Rusty Kaspad `v2.0.1` (`kaspanet/rusty-kaspad`) configured with `--utxoindex`, `--disable-upnp`, and internal RPC/P2P endpoints.
FR-2: Must automatically seed network peers via pre-configured reliable mainnet fallback seeders (`157.90.7.39:16111`, `49.12.171.174:16111`) and upstream DNS resolvers (`1.1.1.1`, `8.8.8.8`) to prevent 0-peer network isolation.
FR-3: Must bind Stratum Bridge v2.0.1 to dedicated TCP port `55555:5555/tcp` to prevent conflicts with other mining proxies.
FR-4: Must automate host directory ownership and permissions to UID/GID `1000:1000` via Umbrel `hooks/pre-start` lifecycle.
FR-5: (Multi-Stage IBD Tracking) Must distinguish and report:
  - Stage 1: Pruning point proof validation (~92k+ headers).
  - Stage 2: Header catchup against network tip DAA score with ETA.
  - Stage 3: Tip synchronization (10 BPS virtual tip active).
FR-6: (Dual Connection Display) Must detect and present both local LAN IPv4 (`stratum+tcp://<lan-ip>:55555`) and `umbrel.local` hostname stratum endpoints with quick-copy controls.
FR-7: (Overview Dashboard) Must display total active hashrate, active worker count, 24-hour solved blocks, dynamic luck estimate, and the GHOSTDAG 10 BPS visualizer.
FR-8: (Worker Telemetry) Must report worker IP, hashrate, share submission metrics (accepted/stale/invalid), difficulty, and color-coded effort (`<100%` lucky green, `>100%` amber).
FR-9: (Hardware Tuning Presets) Must provide tiered difficulty presets (Automatic Universal default, Low/KS0, Mid/KS1-KS2, High/KS3-KS5, Enterprise).
FR-10: (Block Discovery Celebration) Must trigger a celebratory confetti animation and worker card highlight upon block solution, with an updating 24-hour block count card.
FR-11: (Mined Blocks Ledger) Must maintain a permanent ledger of discovered blocks with blue score, worker attribution, effort, reward breakdown (subsidy + fees in KAS/USD), and direct links to Kaspa Explorer.
FR-12: (In-App Node & Log Telemetry) Must stream live system logs (bridge and node) and P2P peer swarm telemetry (inbound/outbound peers, ping, mempool txs) directly in the UI.
FR-13: (6-Month Tiered Storage) Must downsample telemetry metrics across three tiers to maintain total disk footprint under 4 MB:
  - 24 Hours: 1-minute averaged samples (~1,440 points).
  - 30 Days: 15-minute averaged rollups (~2,880 points).
  - 6 Months (180 Days): 1-hour averaged rollups (~4,320 points).
FR-14: (Danger Zone Reset) Must provide an interactive data reset capability guarded by a double-confirmation modal requiring explicit confirmation.

### NonFunctional Requirements

NFR-1: (Umbrel 1.7+ App Store Packaging) Must adhere strictly to Umbrel App Store specifications (`umbrel-app.yml` manifest 1.1, `app_proxy` adapter mapping to internal port 8080, no host HTTP port collisions).
NFR-2: (Resource Efficiency) Frontend and backend telemetry daemon must consume < 150 MB RAM combined, reserving CPU and memory for the Rusty Kaspad node and ASIC stratum handling.
NFR-3: (Design Language & Responsiveness) Must adopt Umbrel native dark-mode aesthetic with Kaspa-branded cyan accents (`#70c7ba`), subtle glassmorphism, responsive tables, and mobile viewport support.
NFR-4: (Port Conflict Isolation) P2P port `16111` mapped for community store release, with architectural path documented for official store submission (e.g. evaluating fallback port `15111` or dynamic P2P mode if standalone Rusty Kaspad is co-installed).

### Additional Requirements

- ARCH-1: Docker Multi-Container Topology: Orchestrate three isolated container services (`kaspad`, `bridge`, `web`) via `docker-compose.yml` with isolated failure blast radiuses so mining continues if `web` restarts.
- ARCH-2: Autonomous Background Collector (AD-1): Server-side `BackgroundCollectorService` in `web` daemon polls `bridge:3030` and `kaspad:18110` (JSON-RPC) every 5 seconds independently of active browser sessions.
- ARCH-3: Explicit Port Binding Standards (AD-3): Stratum on host `55555`, Web on host `5557` (via Umbrel proxy), P2P on host `16111`. Internal RPC interfaces (`16110`, `18110`, `3030`) strictly internal to Docker bridge network.
- ARCH-4: Real Data Ground Truth (AD-4): Zero mock fallbacks in production. When node or bridge is offline or syncing, backend must report actual connection state and genuine 0 hashrate.
- ARCH-5: Tiered Rollup Retention Engine (AD-5): Rollup engine enforces 24h @ 1m, 30d @ 15m, 180d @ 1h retention with automatic hourly purging; Mined Block Ledger records are permanent and never purged.
- ARCH-6: Host Ownership Automation: Umbrel `hooks/pre-start` script guarantees host volume permissions to UID/GID `1000:1000` before containers boot.
- ARCH-7: Brownfield Codebase Evolution: Extend and refactor existing `kaspa-solo-mining/` Umbrel package structure rather than greenfield initialization.

### UX Design Requirements

UX-DR1: (Dark Mode System) Umbrel native dark theme with `#121212` base, `#1E1E1E` surface cards/modals, `#333333` subtle borders, and Kaspa Teal (`#70C7BA`) primary accents.
UX-DR2: (Typography Hierarchy) Standardize on `Inter` for UI copy/headers and `Fira Code` monospace for numeric readouts (hashrate, DAA score, block hashes, currency).
UX-DR3: (Modular Layout & Mobile Support) Modular CSS Grid with 24px card padding, 8px/12px border radii, and responsive hamburger drawer navigation with 48px touch targets for mobile devices.
UX-DR4: (GHOSTDAG Stream Visualizer) Real-time HTML5 canvas rendering 10 BPS DAG blocks with blue/gold consensus coloring and pulsing peer connections.
UX-DR5: (Multi-Stage Sync Banner & Progress) Unambiguous sync tracking covering Stage 1 (pruning proof validation ~92k headers), Stage 2 (DAA catchup with ETA and progress bar), and Stage 3 (synchronized 10 BPS active).
UX-DR6: (Dual ASIC Connection Point) Prominent ASIC connection card displaying primary LAN IPv4 (`stratum+tcp://<lan-ip>:55555`) and secondary hostname (`stratum+tcp://umbrel.local:55555`) with quick-copy buttons and connection readiness status.
UX-DR7: (Overview Metric Cards) Stat cards for Fleet Hashrate (with area chart), Active Miners count, 24-Hour Solved Blocks, and Round Effort percentage.
UX-DR8: (Miners & Workers Table) Mobile-responsive worker table displaying Worker Name, Hashrate, Shares (Accepted/Stale/Invalid), Difficulty, Latency (Ping), and color-coded Effort (`<100%` lucky green, `>100%` amber).
UX-DR9: (Hardware Tuning Selector) Preset selector defaulting to Automatic Universal (auto-vardiff), offering diagnostic presets (IceRiver KS0, KS1/KS2, Antminer KS3/KS5, Enterprise) with active preset feedback.
UX-DR10: (Block Discovery Celebration) Confetti burst animation and winning worker card accent glow upon block solution event, plus manual Easter egg trigger on Kaspa header logo.
UX-DR11: (Mined Blocks Ledger) Comprehensive block discovery ledger with blue score, worker attribution, effort %, reward decomposition (subsidy + fees in KAS/USD), DAG confirmation badge, and Kaspa Explorer hyperlinks.
UX-DR12: (Live Streaming Log Console) Real-time streaming log console for Stratum Bridge and Rusty Kaspad with auto-scroll to bottom and hover-to-pause functionality.
UX-DR13: (P2P Swarm & Node Health) Kaspa Node health view with inbound/outbound peer donut chart, peer swarm details (IP, ping, version), mempool transaction counter, and port 16111 status.
UX-DR14: (Danger Zone Confirmation Modal) Destructive historical data reset action guarded by an explicit double-confirmation modal requiring user confirmation.
UX-DR15: (Empty & State Indicators) Flatline chart state with "Waiting for ASIC connection on port 55555..." message and pulsating status indicators for ASIC connection and Node Sync.

### FR Coverage Map

FR-1: Epic 1 - Official Rusty Kaspad v2.0.1 node container integration with UTXO index
FR-2: Epic 1 - Automatic P2P network peer seeding & upstream DNS resolvers
FR-3: Epic 1 - Dedicated Stratum Bridge port 55555:5555/tcp binding
FR-4: Epic 1 - Automated host directory UID/GID 1000:1000 permissions via hooks/pre-start
FR-5: Epic 1 - Multi-Stage IBD tracking (proof validation, DAA catchup with ETA, tip sync)
FR-6: Epic 1 - Dual ASIC connection endpoint display (LAN IPv4 & umbrel.local with copy buttons)
FR-7: Epic 2 - Overview dashboard metrics and real-time 10 BPS GHOSTDAG canvas visualizer
FR-8: Epic 2 - Worker fleet telemetry table with latency and color-coded effort metrics
FR-9: Epic 2 - Hardware tuning presets with Automatic Universal (auto-vardiff) default
FR-10: Epic 3 - Block discovery celebration animation, worker card glow, and 24h counter
FR-11: Epic 3 - Permanent Mined Blocks ledger with reward decomposition & Explorer hyperlinks
FR-12: Epic 4 - In-app live streaming logs console & P2P swarm telemetry view
FR-13: Epic 4 - 6-month tiered telemetry storage retention (<4MB disk cap)
FR-14: Epic 4 - Interactive data reset capability guarded by double-confirmation Danger Zone modal

## Epic List

### Epic 1: Zero-Config Mining Engine & Initial Sync Experience
Home miners can install the suite on Umbrel, automatically seed and sync their Rusty Kaspad full node and Stratum Bridge with automated permissions, track multi-stage Initial Block Download with zero ambiguity, and connect ASICs seamlessly via verified LAN IP and mDNS endpoints.
**FRs covered:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-6

### Epic 2: Live Mining Operations & Worker Fleet Telemetry
Miners can monitor real-time mining operations on a high-speed dashboard featuring the 10 BPS GHOSTDAG visualizer, inspect individual worker health (hashrate, shares, difficulty, ping, color-coded effort), and manage hardware tuning presets backed by a 5-second server-side autonomous background collector.
**FRs covered:** FR-7, FR-8, FR-9

### Epic 3: Solo Block Discovery Celebration & Mined Blocks Ledger
Miners experience an immediate, non-disruptive celebration upon finding a mainnet Kaspa block and can audit an immutable ledger of all discovered blocks with blue scores, worker attribution, effort %, reward decomposition (KAS/USD), and direct Kaspa Explorer verification.
**FRs covered:** FR-10, FR-11

### Epic 4: Node Diagnostics, Tiered Historical Storage & Fleet Maintenance
Miners can diagnose node and bridge health via in-app streaming logs and P2P swarm telemetry, review historical hashrate trends over 6 months without disk bloat (<4MB storage cap), and perform controlled telemetry data maintenance via a guarded Danger Zone.
**FRs covered:** FR-12, FR-13, FR-14

---

## Epic 1: Zero-Config Mining Engine & Initial Sync Experience

Home miners can install the suite on Umbrel, automatically seed and sync their Rusty Kaspad full node and Stratum Bridge with automated permissions, track multi-stage Initial Block Download with zero ambiguity, and connect ASICs seamlessly via verified LAN IP and mDNS endpoints.

### Story 1.1: Multi-Container Orchestration & Resilient Network Seeding

As a home miner installing the suite on Umbrel,
I want Docker Compose to orchestrate Rusty Kaspad v2.0.1 and Stratum Bridge v2.0.1 with automated permissions, dedicated port bindings, and reliable peer seeding,
So that my node connects to the Kaspa mainnet immediately without 0-peer network stalls, port collisions, or permission crashes.

**Acceptance Criteria:**

**Given** an UmbrelOS host running Docker Compose
**When** the app lifecycle triggers `hooks/pre-start` and boots the container stack
**Then** host data directories (`kaspad_data`) are automatically assigned UID/GID `1000:1000` permissions (`FR-4`, `ARCH-6`)
**And** `docker-compose.yml` spins up `kaspad` using official `kaspanet/rusty-kaspad:v2.0.1` configured with `kaspad` binary execution, `--rpclisten=0.0.0.0:16110`, `--utxoindex`, and `--disable-upnp` (`FR-1`)
**And** the `kaspad` service includes upstream DNS resolvers (`1.1.1.1`, `8.8.8.8`) and fallback static peers (`--addpeer=157.90.7.39:16111`, `--addpeer=49.12.171.174:16111`), reliably establishing outbound peers within 60 seconds (`FR-2`)
**And** the Stratum Bridge container binds its external mining port strictly to host TCP `55555:5555/tcp` (`FR-3`, `ARCH-3`)
**And** internal gRPC (`16110`) and wRPC (`18110`) interfaces are kept internal to the Docker bridge network (`ARCH-3`).

### Story 1.2: Multi-Stage Initial Block Download (IBD) Telemetry & Visualizer

As a home miner watching my node synchronize,
I want the dashboard to explicitly distinguish pruning proof validation from DAA header catchup with real-time ETA,
So that I know exactly which sync stage my node is in without thinking it is frozen.

**Acceptance Criteria:**

**Given** a syncing Rusty Kaspad node
**When** the node is downloading and verifying the initial pruning point proof
**Then** the UI sync banner and Kaspa Node card display **Stage 1 (Proof Validation)**: *"Validating DAG Pruning Proofs (~92k headers)... Network consensus verification in progress."* with an animated progress pulse (`FR-5`, `UX-DR5`)
**When** the pruning proof completes and the node catches up headers to the network tip
**Then** the UI transitions to **Stage 2 (Header Catchup)**, reporting the current DAA score vs. network tip target, completion percentage, and rolling estimated time remaining (ETA) (`FR-5`, `UX-DR5`)
**When** the node reaches the virtual DAA tip
**Then** the UI transitions smoothly to **Stage 3 (Synchronized)**: *"Synchronized (10 BPS) • Mining Active"* with a glowing green status indicator (`FR-5`, `UX-DR15`).

### Story 1.3: Dual ASIC Stratum Connection Point & Quick-Copy Integration

As a home miner ready to configure my ASICs,
I want the dashboard to display both my server's local LAN IPv4 and hostname connection strings with one-click copy buttons,
So that I can point my IceRiver or Antminer hardware directly to the bridge without failing due to ASIC firmware mDNS limitations.

**Acceptance Criteria:**

**Given** the dashboard Overview screen
**When** Marcus views the ASIC Connection card
**Then** the card displays the Primary connection string: `stratum+tcp://<lan-ipv4>:55555` where `<lan-ipv4>` is dynamically detected from the server host (`FR-6`, `UX-DR6`)
**And** the card displays the Secondary connection string: `stratum+tcp://umbrel.local:55555` (`FR-6`, `UX-DR6`)
**And** clicking the copy button next to either string copies the full URL to the clipboard and provides visual tooltip feedback ("Copied!")
**And** the card includes the readiness callout: *"ASICs can be connected now; mining will commence automatically once the node reaches the DAG tip."* (`UX-DR6`).

---

## Epic 2: Live Mining Operations & Worker Fleet Telemetry

Miners can monitor real-time mining operations on a high-speed dashboard featuring the 10 BPS GHOSTDAG visualizer, inspect individual worker health (hashrate, shares, difficulty, ping, color-coded effort), and manage hardware tuning presets backed by a 5-second server-side autonomous background collector.

### Story 2.1: Autonomous Server-Side Telemetry Collector & Real Data Pipeline

As a home miner running Umbrel headless,
I want the backend to continuously poll Stratum Bridge and Rusty Kaspad every 5 seconds even when my browser is closed,
So that telemetry records are never missed and metrics reflect genuine real-world node data without artificial mocks.

**Acceptance Criteria:**

**Given** the running `web` container
**When** the container boots up
**Then** a standalone `BackgroundCollectorService` daemon starts immediately without requiring an active browser HTTP or WebSocket connection (`ARCH-2`)
**And** the collector polls `http://bridge:3030/api/workers` and `/api/stats` every 5 seconds for live worker hashrates, shares, and vardiff (`ARCH-2`)
**And** the collector queries `http://kaspad:18110` (JSON-RPC) for live DAA tip, header count, and difficulty (`ARCH-2`)
**And** in production environments, the collector serves strictly real telemetry (reporting genuine 0 hashrate, syncing, or degraded status when nodes are unavailable), with mock data generators restricted exclusively to unit test fixtures (`ARCH-4`).

### Story 2.2: Reactive Overview Dashboard & 10 BPS GHOSTDAG Canvas Visualizer

As a home miner opening the dashboard,
I want to see my total fleet hashrate, active worker counts, round effort, and a live 10 BPS GHOSTDAG animation,
So that I get an immediate, high-fidelity visual pulse of my mining operation and network consensus.

**Acceptance Criteria:**

**Given** the Overview dashboard view
**When** telemetry is received from the collector API
**Then** the primary metric cards display Fleet Hashrate (formatted with dynamic scale e.g. GH/s, TH/s in Fira Code monospace), Active Miners count, 24-Hour Solved Blocks, and Current Round Effort percentage (`FR-7`, `UX-DR7`)
**And** an interactive area chart renders the real-time hashrate trend (`UX-DR7`)
**And** the HTML5 canvas visualizer streams real-time 10 BPS GHOSTDAG blocks with distinctive blue (selected/consensus) and gold/red block styling, smooth horizontal flow, and pulsing peer connections (`FR-7`, `UX-DR4`).

### Story 2.3: Mobile-Responsive Worker Fleet Table with Effort Telemetry

As a miner operating one or multiple ASICs,
I want to inspect granular per-worker telemetry on both desktop and mobile screens,
So that I can spot stale shares, high network latency, or unlucky rounds on any worker instantly.

**Acceptance Criteria:**

**Given** one or more connected ASICs submitting shares to the bridge
**When** Marcus opens the **Miners & Workers** tab
**Then** the worker table renders Worker Name, Hashrate, Shares (Accepted / Stale / Invalid with percentage), Difficulty, and Network Latency (Ping) (`FR-8`, `UX-DR8`)
**And** the Effort column displays a badge color-coded by luck: lucky green for `< 100%` effort and amber/gold for `> 100%` effort (`FR-8`, `UX-DR8`)
**And** on mobile viewports (< 768px), the table smoothly supports horizontal swipe or converts into stacked worker cards ensuring full legibility without clipped data (`UX-DR3`, `UX-DR8`).

### Story 2.4: Hardware Tuning Presets & Real-Time Vardiff Control

As a miner with different ASIC models (e.g. IceRiver KS0 vs Antminer KS3/KS5),
I want the bridge to default to Automatic Universal auto-vardiff while providing one-click diagnostic presets,
So that my hardware maintains 15–20 shares/min automatically without manual bridge config file edits.

**Acceptance Criteria:**

**Given** the Hardware Presets tab
**When** Marcus views the tuning options
**Then** the active configuration defaults to **Automatic Universal (Auto-Vardiff)** (`FR-9`, `UX-DR9`)
**When** Marcus selects a diagnostic hardware preset (IceRiver KS0/Pro/Ultra, KS1/KS2, Antminer KS3/KS5, or Enterprise)
**Then** the system presents a confirmation prompt and dynamically updates the Stratum Bridge vardiff parameters in real time without restarting the node (`FR-9`, `UX-DR9`)
**And** the UI reflects the currently active preset badge with target difficulty parameters (`UX-DR9`).

---

## Epic 3: Solo Block Discovery Celebration & Mined Blocks Ledger

Miners experience an immediate, non-disruptive celebration upon finding a mainnet Kaspa block and can audit an immutable ledger of all discovered blocks with blue scores, worker attribution, effort %, reward decomposition (KAS/USD), and direct Kaspa Explorer verification.

### Story 3.1: Block Discovery Event Detection & Non-Disruptive Celebration

As a solo miner whose ASIC solves a valid mainnet block,
I want an immediate, non-blocking celebration to fire in the browser with an accent on the winning worker and an updated 24h block counter,
So that I know I hit a block without modal dialogs obstructing my workflow.

**Acceptance Criteria:**

**Given** an ASIC worker that solves a valid mainnet block template
**When** the bridge submits the block to `kaspad` and logs the solution event
**Then** the `BackgroundCollectorService` detects the solved block and pushes a `block_found` event over Server-Sent Events (SSE) `/api/events` (`FR-10`, `ARCH-2`)
**When** the frontend receives the event while the dashboard is active
**Then** a celebratory confetti burst fires across the screen (`FR-10`, `UX-DR10`)
**And** the winning worker card in the Miners view illuminates with a subtle glowing teal accent border (`FR-10`, `UX-DR10`)
**And** the "BLOCKS (LAST 24H)" stat card on the Overview dashboard increments immediately (`FR-10`, `UX-DR7`)
**And** clicking the Kaspa header emblem manually triggers the confetti shower as an interactive Easter egg (`UX-DR10`).

### Story 3.2: Permanent Mined Blocks Ledger & Reward Analytics

As a solo miner tracking my historical blocks and revenue,
I want an immutable ledger recording every mined block with blue score, worker attribution, effort, reward breakdown, and Explorer links,
So that I have a permanent audit trail of my mining rewards that is never pruned by data retention cleanup.

**Acceptance Criteria:**

**Given** a solved block recorded by the system
**When** Marcus opens the **Mined Blocks** tab
**Then** the ledger displays:
  - Solve Timestamp and Blue Score (`FR-11`)
  - Winning Worker Name and Effort % at time of solution (`FR-11`)
  - Reward Decomposition: Block Subsidy + Transaction Fees formatted in both KAS and USD equivalent (`FR-11`)
  - DAG Confirmation status badge (`FR-11`)
  - Block Hash with a direct hyperlink pointing to `https://explorer.kaspa.org/blocks/<hash>` (`FR-11`, `UX-DR11`)
**And** all block records in the ledger are flagged as permanent and are strictly preserved across historical data purges (`AD-5`).

---

## Epic 4: Node Diagnostics, Tiered Historical Storage & Fleet Maintenance

Miners can diagnose node and bridge health via in-app streaming logs and P2P swarm telemetry, review historical hashrate trends over 6 months without disk bloat (<4MB storage cap), and perform controlled telemetry data maintenance via a guarded Danger Zone.

### Story 4.1: Live Streaming Log Viewer & Node Swarm Telemetry

As a miner troubleshooting a connection drop or verifying network health,
I want to view real-time container logs and P2P swarm telemetry directly in the dashboard,
So that I can diagnose issues without opening an SSH terminal session on my Umbrel server.

**Acceptance Criteria:**

**Given** the **Kaspa Node** and **Logs** views
**When** Marcus opens the Logs console
**Then** the UI streams live stdout/stderr logs from both the Stratum Bridge and Rusty Kaspad containers (`FR-12`, `UX-DR12`)
**And** the console automatically scrolls to the newest log entries, pausing scroll when hovered (`UX-DR12`)
**When** Marcus views the Kaspa Node swarm dashboard
**Then** the UI displays an Inbound vs. Outbound peer donut chart, connected peer table (IP, ping, version), mempool transaction counter, and port 16111 status (`FR-12`, `UX-DR13`).

### Story 4.2: 6-Month Tiered Storage Retention Engine (<4MB Footprint)

As a long-term home miner running on compact Umbrel hardware,
I want historical telemetry downsampled into tiered resolution buckets,
So that I can analyze mining trends over 6 months without expanding disk usage or slowing query latency.

**Acceptance Criteria:**

**Given** the background telemetry collector persisting historical records
**When** the hourly retention aggregator runs
**Then** raw 5-second metrics are consolidated into:
  - **Tier 1 (24 Hours):** 1-minute averaged samples (~1,440 points) (`FR-13`, `ARCH-5`)
  - **Tier 2 (30 Days):** 15-minute averaged rollups (~2,880 points) (`FR-13`, `ARCH-5`)
  - **Tier 3 (6 Months / 180 Days):** 1-hour averaged rollups (~4,320 points) (`FR-13`, `ARCH-5`)
**And** data points older than 180 days are automatically purged from disk (`ARCH-5`)
**And** total historical telemetry storage remains strictly under 4 MB (`FR-13`)
**And** the Mined Blocks Ledger records are completely exempt from pruning (`AD-5`).

### Story 4.3: Danger Zone Historical Telemetry Reset & Safety Gate

As a miner maintaining my home node,
I want a dedicated reset control to clear historical chart rollups guarded by a double-confirmation modal,
So that I can start clean metrics after hardware moves without accidentally destroying my mined blocks ledger or stopping active mining.

**Acceptance Criteria:**

**Given** the **Danger Zone** section in Settings / Presets
**When** Marcus clicks the **Reset Historical Data** button
**Then** an explicit double-confirmation modal appears warning that historical hashrate, shares, and rollup charts will be erased (`FR-14`, `UX-DR14`, `AD-6`)
**When** Marcus confirms the warning in the modal
**Then** the frontend dispatches `POST /api/data/reset`
**And** the backend wipes all historical rollup buckets while preserving the permanent Mined Blocks Ledger and active Stratum mining uninterrupted (`FR-14`, `AD-6`)
**And** the UI notifies Marcus of successful reset and resets the hashrate area charts to the current active sample (`UX-DR14`).





