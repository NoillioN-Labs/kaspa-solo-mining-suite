---
title: Kaspa Solo Mining Suite Redesign
status: final
created: 2026-09-04
updated: 2026-09-06
---

# PRD: Kaspa Solo Mining Suite (Umbrel All-In-One Edition)

## 1. Vision & Objectives
Make solo mining Kaspa dead simple for the decentralized home-mining community. The Kaspa Solo Mining Suite is an all-in-one, zero-dependency package engineered for Umbrel Home and UmbrelOS servers. It packages an official Kaspa full node, high-performance Stratum Bridge, and a real-time reactive management dashboard into a single click-to-install experience that qualifies for the official Umbrel App Store (launching initially in the Community Store).

## 2. Target Personas & Stakeholders
- **Primary Persona (Marcus - Home ASIC Miner):** Enthusiast home-lab operator running Umbrel with 1–4 compact ASICs (IceRiver KS0/KS0 Pro/Ultra, Antminer KS3/KS5, or Desiwe K11). Needs a zero-maintenance, plug-and-play mining endpoint without needing terminal commands, port debugging, or third-party pool fees.
- **Secondary Persona (Advanced Operator / Farm Manager):** Multi-rig operator seeking granular difficulty tuning, live per-worker telemetry (ping, shares, difficulty, effort), and exportable historical data.

## 3. Product Principles
- **Dead Simple:** Install from Umbrel, point your ASIC to the displayed IP/port, and start solo mining. Zero CLI configuration required.
- **Zero Ambiguity During Sync:** Transparent, multi-stage Initial Block Download (IBD) tracking so the user always knows whether the node is validating cryptographic proofs or streaming live DAG headers.
- **Resilient & Self-Contained:** Runs the official Rusty Kaspad node, official Stratum Bridge, and an ultra-lightweight telemetry dashboard inside a unified Docker network with automated permission management.
- **Tasteful Celebration:** Subtle, non-disruptive feedback (confetti burst + worker card glow) on block discoveries without blocking operational workflows.

---

## 4. User Journeys (Marcus's Lifecycle)

### Journey 1: First-Time Setup & The Initial Sync Experience
1. Marcus installs "Kaspa Solo Mining Suite" from the Umbrel App Store.
2. Upon opening the dashboard, Marcus is immediately greeted by the GHOSTDAG live block visualizer and an unambiguous **Multi-Stage Sync Banner**:
   - **Stage 1 (Proof Validation):** Displays *"Validating DAG Pruning Proofs (~92k headers)... Network consensus verification in progress."*
   - **Stage 2 (Header Catchup):** Displays current DAA score vs. network tip target with percentage progress and estimated time to completion.
   - **Stage 3 (Synchronized):** Transitions smoothly to *"Synchronized (10 BPS) • Mining Active"*.
3. Below the banner, Marcus sees a dedicated **ASIC Connection Guide** with dual connection options:
   - **Primary (LAN IP):** `stratum+tcp://<resolved-umbrel-lan-ip>:55555` with a one-click copy button (avoiding ASIC firmware mDNS lookup issues).
   - **Secondary (Hostname):** `stratum+tcp://umbrel.local:55555`.
4. The dashboard explicitly clarifies: *"ASICs can be connected now; mining will commence automatically once the node reaches the DAG tip."*

### Journey 2: Daily Solo Mining Monitoring & Diagnostics
1. Once synced, Marcus points his IceRiver KS0 Pro to the stratum endpoint.
2. Within seconds, the **Overview** page updates:
   - **Active Miners** increments to `1 Active`.
   - **Total Hashrate** registers Marcus's real-time hashrate (e.g. `200.0 GH/s`).
   - The **GHOSTDAG Live 10 BPS animation** streams live blocks.
3. Marcus navigates to **Miners & Workers** to inspect his hardware:
   - Worker table displays Worker Name, Hashrate, Shares (Accepted/Stale/Invalid), Difficulty, Latency (Ping), and color-coded **Effort** (`<100%` lucky green, `>100%` amber).
   - Responsive horizontal scroll ensures seamless mobile monitoring on phones and tablets.
4. Marcus visits **Hardware Presets**:
   - The suite defaults to **Automatic Universal (Auto-Vardiff)**, targeting 15–20 shares/min across all ASIC scales.
   - Marcus only needs to select dedicated hardware profiles (IceRiver KS0, KS1/KS2, Antminer KS3/KS5, Enterprise) if diagnosing unusual share submission or latency issues.

### Journey 3: The Solo Block Discovery & Ledger
1. Marcus's KS0 Pro solves a valid mainnet Kaspa block.
2. If Marcus has the dashboard open, a celebratory **confetti burst** fires, and a subtle visual accent glows on the winning miner card.
3. On the Overview screen, the **"BLOCKS (LAST 24H)"** metric increments immediately.
4. Marcus switches to the **Mined Blocks** tab to review the immutable ledger:
   - Block hash with one-click link to `https://explorer.kaspa.org/blocks/<hash>`.
   - Blue score and solve timestamp.
   - Worker name and solve effort percentage.
   - Reward decomposition: Block Subsidy + Transaction Fees (in KAS and USD equivalent).
   - DAG confirmation status (Blue Block).

### Journey 4: Troubleshooting, Swarm Telemetry & Maintenance
1. If Marcus suspects a connection issue, he navigates to **Logs & Node**:
   - Live browser-based log viewer displays real-time bridge handshakes and node events without opening SSH or terminal.
2. In the **Kaspa Node** tab, Marcus verifies network health:
   - P2P Swarm telemetry (inbound vs. outbound peer counts, peer latency, mempool transaction count).
   - UTXO index confirmation badge.
3. Under **Hardware Presets > Danger Zone**, Marcus has access to a **Reset Historical Data** action guarded by an explicit double-confirmation modal, wiping historical rollup charts while leaving live mining intact.

---

## 5. Functional Requirements (FRs)

### 5.1. Core Node & Stratum Infrastructure
- **FR-1:** Must bundle official Rusty Kaspad `v2.0.1` (`kaspanet/rusty-kaspad`) configured with `--utxoindex`, `--disable-upnp`, and internal RPC/P2P endpoints.
- **FR-2:** Must automatically seed network peers via pre-configured reliable mainnet fallback seeders (`157.90.7.39:16111`, `49.12.171.174:16111`) and upstream DNS resolvers (`1.1.1.1`, `8.8.8.8`) to prevent 0-peer network isolation.
- **FR-3:** Must bind Stratum Bridge v2.0.1 to dedicated TCP port `55555:5555/tcp` to prevent conflicts with other mining proxies.
- **FR-4:** Must automate host directory ownership and permissions to UID/GID `1000:1000` via Umbrel `hooks/pre-start` lifecycle.

### 5.2. Telemetry, Sync & Mining Experience
- **FR-5 (Multi-Stage IBD Tracking):** Must distinguish and report:
  - Pruning point proof validation (92k+ headers).
  - Header catchup against network tip DAA score.
  - Tip synchronization (10 BPS virtual tip).
- **FR-6 (Dual Connection Display):** Must detect and present both local LAN IPv4 and `umbrel.local` hostname stratum endpoints with quick-copy controls.
- **FR-7 (Overview Dashboard):** Must display total active hashrate, active worker count, 24-hour solved blocks, dynamic luck estimate, and the GHOSTDAG 10 BPS visualizer.
- **FR-8 (Worker Telemetry):** Must report worker IP, hashrate, share submission metrics, difficulty, and color-coded effort (`<100%` lucky green, `>100%` amber).
- **FR-9 (Hardware Tuning Presets):** Must provide tiered difficulty presets (Automatic Universal, Low/KS0, Mid/KS1-KS2, High/KS3-KS5, Enterprise) with Automatic Universal as default.
- **FR-10 (Block Discovery Celebration):** Must trigger a celebratory confetti animation and worker card highlight upon block solution, with an updating 24-hour block count card.
- **FR-11 (Mined Blocks Ledger):** Must maintain a permanent ledger of discovered blocks with blue score, worker attribution, effort, reward breakdown (subsidy + fees in KAS/USD), and direct links to Kaspa Explorer.
- **FR-12 (In-App Node & Log Telemetry):** Must stream live system logs and P2P peer statistics (inbound/outbound peers, ping, mempool txs) directly in the UI.

### 5.3. Data Retention & Maintenance
- **FR-13 (6-Month Tiered Storage):** Must downsample telemetry metrics across three tiers to maintain a total disk footprint under 4 MB:
  - 24 Hours: 1-minute averaged samples (~1,440 points).
  - 30 Days: 15-minute averaged rollups (~2,880 points).
  - 6 Months (180 Days): 1-hour averaged rollups (~4,320 points).
- **FR-14 (Danger Zone Reset):** Must provide an interactive data reset capability guarded by a double-confirmation modal requiring explicit confirmation.

---

## 6. Non-Functional Requirements (NFRs)

- **NFR-1 (Umbrel 1.7+ App Store Packaging):** Must adhere strictly to Umbrel App Store specifications (`umbrel-app.yml` manifest 1.1, `app_proxy` adapter mapping to internal port 8080, no host HTTP port collisions).
- **NFR-2 (Resource Efficiency):** Frontend and backend telemetry daemon must consume < 150 MB RAM combined, reserving CPU and memory for the Rusty Kaspad node and ASIC stratum handling.
- **NFR-3 (Design Language & Responsiveness):** Must adopt Umbrel native dark-mode aesthetic with Kaspa-branded cyan accents (`#70c7ba`), subtle glassmorphism, responsive tables, and mobile viewport support.
- **NFR-4 (Port Conflict Isolation):** P2P port `16111` mapped for community store release, with architectural path documented for official store submission (e.g. evaluating fallback port `15111` or dynamic P2P mode if standalone Rusty Kaspad is co-installed).
