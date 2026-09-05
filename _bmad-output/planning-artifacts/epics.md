---
stepsCompleted: [1, 2, 3]
inputDocuments: ["prd.md", "ARCHITECTURE-SPINE.md", "DESIGN.md", "EXPERIENCE.md"]
---

# Kaspa Solo Mining Suite Redesign - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Kaspa Solo Mining Suite Redesign, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Run a self-contained, fully-synced Rusty Kaspad node locally to ensure true solo mining and network decentralization.
FR2: An integrated Kaspa Stratum Bridge configured to securely translate stratum mining protocols to the local Kaspa node.
FR3: Built-in tuning presets (extending from the previous project) for popular ASIC hardware to optimize bridge performance instantly.
FR4: A completely new, modern, and responsive dashboard UI prioritizing visual graphs and charts over raw textual data.
FR5: A dedicated "Block Found" celebration animation or notification system.
FR6: An integrated real-time logs viewer to troubleshoot ASIC connections and stratum bridge issues directly from the UI.
FR7: Hardware health monitoring, specifically ASIC hardware temperature alerts.
FR8: Profitability and fiat tracking for mined Kaspa.
FR9: Reward tracking visualization over time, specifically splitting out Block Subsidies, Accepted Fees, and DAG rewards.

### NonFunctional Requirements

NFR1: Cleanly containerized for Umbrel OS, ensuring proper persistent volume mapping and robust permission handling to prevent startup crashes.
NFR2: The web dashboard must be extremely lightweight (Vite + React) to ensure it does not compete for resources.
NFR3: Intelligent port mapping to avoid conflicts with existing mining proxies (routing Stratum over 55555).
NFR4: The UI must mimic Umbrel's native design system to feel like a first-party application, utilizing Dark and Light modes with Kaspa-branded accent colors.

### Additional Requirements

- Docker Compose Orchestration (Umbrel OS Standard) prevents monolithic architecture. Stack MUST be separated into `kaspad`, `bridge`, and `web`.
- Explicit Port and Volume Mapping: Stratum Bridge MUST map to host port `55555`. The `kaspad` data directory MUST map persistently to `/app/data` with host-writeable permissions (e.g., `0777` or matching UID `50051`) via `pre-start` hooks.
- Web Backend as Telemetry Aggregator: The `web` backend acts as an aggregator (polling `bridge` and `kaspad`) so the frontend doesn't directly hit sensitive nodes.
- Reward Composition Extraction: To visualize the split between Subsidies, Fees, and DAG rewards, the backend MUST query the Kaspa Node RPC exclusively.

### UX Design Requirements

UX-DR1: Use "Dark Mode by Default" with Kaspa Teal (#70C7BA) for active states.
UX-DR2: Use Inter font for UI copy and Fira Code for numbers/data.
UX-DR3: Dashboard uses modular CSS grid with distinct cards (Hashrate, Rewards, Temps) and 24px padding.
UX-DR4: Implement 8px and 12px border radii for the Umbrel soft aesthetic.
UX-DR5: Graphs: Implement Area charts for Hashrate, stacked bar charts for Reward composition (Subsidies, Fees, DAG).
UX-DR6: Status Indicator: Implement Glowing dot (Green/Yellow/Red) for ASIC connection and Node Sync status.
UX-DR7: Hovering over charts reveals a tooltip with exact numbers and timestamps.
UX-DR8: Log Viewer component auto-scrolls to the bottom and pauses on hover.
UX-DR9: Changing an ASIC tuning preset prompts a simple confirmation popup.
UX-DR10: Empty State: When first installed, graphs show a flatline with a "Waiting for ASIC connection on port 55555..." placeholder.
UX-DR11: Syncing State: Node sync shows a circular progress indicator.
UX-DR12: Alert State: Hardware temperature alerts pulse red and persist in a notification list at the top of the dashboard until explicitly acknowledged.
UX-DR13: "Block Found" Event: Trigger a prominent visual celebration (confetti or Kaspa coin animation) and save to a persistent notification inbox/list until clicked away.

### FR Coverage Map

FR1: Epic 1 - Run a fully-synced local node
FR2: Epic 1 - Integrated Stratum Bridge
FR3: Epic 2 - Built-in tuning presets
FR4: Epic 1 - Modern dashboard UI
FR5: Epic 3 - "Block Found" celebration
FR6: Epic 2 - Real-time logs viewer
FR7: Epic 2 - Hardware health/temperature alerts
FR8: Epic 3 - Profitability and fiat tracking
FR9: Epic 3 - Reward tracking visualization (Subsidies/Fees/DAG)

## Epic List

### Epic 1: Core Mining Engine & Dashboard
**User Outcome:** Users can spin up a fully-synced local node, securely connect their ASIC, and instantly verify their mining status on a modern, responsive dashboard.
**FRs covered:** FR1, FR2, FR4

### Epic 2: Hardware Optimization & Diagnostics
**User Outcome:** Users can tune their ASIC for peak performance and troubleshoot connection issues directly from the web interface, without ever needing to use SSH.
**FRs covered:** FR3, FR6, FR7

### Epic 3: Mining Economics & Rewards Tracking
**User Outcome:** Users can track the exact financial performance of their mining operation, visualize how their rewards are composed over time, and enjoy a visual celebration when they successfully mine a block.
**FRs covered:** FR5, FR8, FR9

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 1: Core Mining Engine & Dashboard

**Goal:** Users can spin up a fully-synced local node, securely connect their ASIC, and instantly verify their mining status on a modern, responsive dashboard.

### Story 1.1: Multi-Container Orchestration & Engine Setup

As a home miner,
I want the Kaspa node and Stratum Bridge to automatically boot up and map to the correct ports/volumes upon installation,
So that I can connect my ASIC without facing startup crashes or port conflicts.

**Acceptance Criteria:**

**Given** the Umbrel OS environment
**When** the app is installed and started
**Then** Docker Compose launches three distinct services (`kaspad`, `bridge`, `web`)
**And** the bridge binds correctly to host port `55555`
**And** the `kaspad` persistent volume maps securely to `/app/data` (e.g., 0777 or UID 50051) via pre-start hooks.

### Story 1.2: Web Dashboard Foundation & UI Styling

As a user,
I want the dashboard to look and feel like a native Umbrel OS application,
So that my experience is cohesive and visually pleasing.

**Acceptance Criteria:**

**Given** the `web` service is running
**When** I load the dashboard
**Then** a lightweight React (Vite) SPA is served
**And** it natively uses "Dark Mode by Default" with Kaspa Teal (#70C7BA) accents
**And** it utilizes a modular CSS grid (24px padding, 8px/12px border radii) and Inter/Fira Code fonts.

### Story 1.3: Telemetry Aggregation & Initial Connection States

As a user,
I want to instantly see if my node is syncing or if my ASIC is connected,
So that I know the system is working before I start tracking hashrate.

**Acceptance Criteria:**

**Given** the backend aggregator is active
**When** the node is syncing or waiting for an ASIC
**Then** the backend securely polls the `bridge` and `kaspad` RPCs without exposing them directly
**And** the UI displays the "Waiting for ASIC on port 55555" empty state or a circular syncing progress indicator
**And** a glowing status dot (Green/Yellow/Red) reflects the current connection health.

<!-- Repeat for each epic in epics_list (N = 2, 3...) -->

## Epic 2: Hardware Optimization & Diagnostics

**Goal:** Users can tune their ASIC for peak performance and troubleshoot connection issues directly from the web interface, without ever needing to use SSH.

### Story 2.1: ASIC Tuning Presets & Applying Changes

As a user,
I want to select built-in tuning presets for my specific ASIC hardware from the dashboard,
So that I can optimize mining performance instantly without writing custom bridge configurations.

**Acceptance Criteria:**

**Given** the dashboard is loaded
**When** I select a tuning preset from the dropdown (e.g., IceRiver, Antminer)
**Then** a simple confirmation popup warns me of a temporary mining interruption
**And** upon confirmation, the backend updates the bridge configuration and restarts the bridge service to apply the tuning.

### Story 2.2: Integrated Real-Time Log Viewer

As a user troubleshooting a connection,
I want to view the real-time logs of the Stratum Bridge and Kaspa Node directly in the UI,
So that I can diagnose issues without having to SSH into the Umbrel device.

**Acceptance Criteria:**

**Given** the dashboard is active
**When** I open the Log Viewer component
**Then** the backend streams the latest stdout/stderr logs from the respective containers
**And** the UI component auto-scrolls to the bottom by default
**And** it automatically pauses scrolling when I hover my mouse over the log area to read a specific line.

### Story 2.3: Hardware Health Monitoring & Alerts

As a home miner,
I want the dashboard to monitor my ASIC's temperature and fan speeds,
So that I can prevent hardware damage from overheating.

**Acceptance Criteria:**

**Given** an ASIC is connected and mining
**When** the hardware temperature crosses a critical threshold
**Then** the UI displays an alert state that pulses red
**And** a persistent alert is added to the notification list at the top of the dashboard, remaining there until I explicitly acknowledge or dismiss it.

## Epic 3: Mining Economics & Rewards Tracking

**Goal:** Users can track the exact financial performance of their mining operation, visualize how their rewards are composed over time, and enjoy a visual celebration when they successfully mine a block.

### Story 3.1: Reward Composition Visualization

As a user,
I want to see exactly how my mined rewards are broken down into Block Subsidies, Accepted Fees, and DAG rewards over time,
So that I understand where my Kaspa is coming from.

**Acceptance Criteria:**

**Given** the node has mined at least one block
**When** I view the Rewards Breakdown card on the dashboard
**Then** the backend queries the Kaspa Node RPC exclusively to retrieve the exact block reward split
**And** the UI renders this as a stacked bar chart with distinct colors/patterns
**And** hovering over the chart reveals a tooltip with exact numbers and timestamps.

### Story 3.2: Profitability & Fiat Tracking

As a miner,
I want to see the fiat value of my mined Kaspa and my estimated daily profitability,
So that I can track the financial performance of my operation.

**Acceptance Criteria:**

**Given** the dashboard is actively monitoring hashrate and rewards
**When** the UI loads
**Then** the backend securely fetches the current Kaspa price from a reliable public API (e.g., CoinGecko) and caches it
**And** the dashboard displays the total mined fiat value and estimated daily profitability based on my average hashrate.

### Story 3.3: "Block Found" Celebration & Notifications

As a solo miner,
I want a clear, exciting notification when my node successfully finds a block,
So that I can celebrate my success.

**Acceptance Criteria:**

**Given** my node is actively mining
**When** the node successfully mines a block and it is accepted by the network
**Then** the UI triggers a prominent visual celebration (e.g., confetti or Kaspa coin animation)
**And** the event is logged as a persistent notification in the inbox/list so I see it even if I was away from the screen when it happened.
