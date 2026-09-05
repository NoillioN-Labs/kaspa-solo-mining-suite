---
title: Kaspa Solo Mining Suite EXPERIENCE
status: final
created: 2026-09-04
updated: 2026-09-04
---
# Foundation
**Form Factor:** Desktop Web and Mobile Web (Responsive).
**UI System:** Inherits Umbrel Native Design behaviors. The goal is zero-friction interaction where the user consumes data at a glance. Visual styles defined in `{DESIGN.md}`.

# Information Architecture
1. **Overview (Dashboard)**
   - Live 10 BPS GHOSTDAG Network Stream Canvas Visualizer.
   - Global Node Sync Status alert banner & ASIC Connection Point.
   - Fleet Hashrate, 24h Mined Blocks yield highlight, and round effort metrics.
2. **Miners & Workers**
   - Fleet Mining Power hero summary.
   - Mobile-responsive table with color-coded Effort metrics (<100% green luck, >100% amber).
3. **Mined Blocks & Rewards**
   - 3-Way Fee composition stacked visualization (Subsidies, Priority Tx, DAG Merged).
   - Historical mined block ledger with Effort metric and Kaspa Explorer links.
4. **Kaspa Node**
   - Node health, peer connection donut visualizer (outbound/inbound), and port 16111 guidance.
   - Detailed initial DAG sync progress (DAA score tracking, estimated time remaining).
   - Connected peer swarm telemetry table.
5. **Hardware Presets & Diagnostics**
   - Difficulty & Hashrate tiered presets with compatible ASIC model chips.
   - Integrated live logs viewer (Stratum & Kaspad).

# Voice and Tone
- **Tone:** Concise, technical but accessible, reassuring. 
- **Voice:** Let the data speak. Avoid chatty copy. Use standard Umbrel system terminology ("Starting", "Syncing", "Active").

# Component Patterns
- **Data Cards:** Hovering over a chart reveals a tooltip with exact numbers and timestamps.
- **Log Viewer:** Auto-scrolls to the bottom. Pauses on hover.
- **Tuning Presets:** Presets are categorized by difficulty floor and hashrate tier (Adaptive, Low, Medium, High, Ultra/Enterprise) with compatible ASIC model chips. "Automatic (Universal)" is the recommended default. Selecting a preset updates vardiff in real time.

# State Patterns
- **Empty State:** When first installed, graphs show a flatline with a "Waiting for ASIC connection on port 55555..." placeholder.
- **Syncing State:** Initial DAG synchronization (which can take 1–2 days) displays a dedicated sync progress card with live DAA tip tracking, ETA, and progress bar on the Kaspa Node page, as well as a prominent alert banner on the Overview dashboard.
- **Alert State:** Hardware temperature alerts pulse red and persist in a notification list at the top of the dashboard until explicitly acknowledged or dismissed by the user.

# Interaction Primitives
- **"Block Found" Event:** When a block is successfully solo mined while the dashboard is running, an Easter Egg confetti shower triggers automatically without disruptive modal popups. Clicking the Kaspa header emblem also triggers the celebration.

# Accessibility Floor
- Text contrast must pass WCAG AA on the dark background.
- Charts must use distinct colors/patterns to differentiate Subsidies, Fees, and DAG rewards for colorblind users.

# Key Flows
**Flow 1: First-Time Setup**
- **Protagonist:** Dave, a home miner.
- **Steps:**
  1. Dave installs the app via Umbrel.
  2. Opens the app and sees the "Waiting for ASIC" state with the IP/Port clearly displayed.
  3. Dave points his ASIC to the IP.
  4. The dashboard instantly comes alive: hashrate spikes, node sync progresses, and the UI shifts to the active monitoring state.
