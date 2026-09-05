---
title: Kaspa Solo Mining Suite Redesign
status: final
created: 2026-09-04
updated: 2026-09-04
---

# PRD: Kaspa Solo Mining Suite Redesign

## 1. Vision & Objectives
Make solo mining Kaspa dead simple for the community. The goal is to redesign and rebuild the existing Kaspa Solo Mining Suite from the ground up to achieve a premium, high-quality standard that ultimately qualifies for the official Umbrel App Store (launching first in the Community Store).

## 2. Target Audience
- **Primary:** Kaspa enthusiasts and home miners using Umbrel who want a zero-configuration solo mining setup.
- **Secondary:** Advanced miners seeking granular ASIC tuning and stratum bridge management without needing to manually configure separate servers.

## 3. Product Principles
- **Dead Simple:** The user should be able to install the app, point their ASIC to the provided IP/port, and start mining immediately. No complex terminal commands.
- **Premium Quality:** UI/UX must meet official Umbrel App Store standards—polished, responsive, fast, and visually cohesive.
- **Self-Contained:** Must securely and seamlessly orchestrate the Rusty Kaspad node, Stratum Bridge, and Web Dashboard.

## 4. Key Features & Requirements (FRs)

### 4.1. Core Mining Stack
- **FR-1:** The app must run a self-contained, fully-synced Rusty Kaspad node locally to ensure true solo mining and network decentralization.
- **FR-2:** An integrated Kaspa Stratum Bridge configured to securely translate stratum mining protocols to the local Kaspa node.
- **FR-3:** Built-in tuning presets (extending from the previous project) for popular ASIC hardware (IceRiver, Antminer, etc.) to optimize bridge performance instantly.

### 4.2. Web Dashboard (Redesign)
- **FR-4:** A completely new, modern, and responsive dashboard UI prioritizing visual graphs and charts over raw textual data to make monitoring network hashrate, active miners, and shares instantly readable.
- **FR-5:** A dedicated "Block Found" celebration animation or notification system to reward users visually when they successfully solo mine a block.
- **FR-6:** An integrated real-time logs viewer to troubleshoot ASIC connections and stratum bridge issues directly from the UI, bypassing the need for SSH.
- **FR-7:** Hardware health monitoring, specifically ASIC hardware temperature alerts.
- **FR-8:** Profitability and fiat tracking for mined Kaspa.
- **FR-9:** Reward tracking visualization over time, specifically splitting out the three distinct reward types: Block Subsidies, Accepted Fees, and DAG rewards. 

## 5. Non-Functional Requirements (NFRs)
- **NFR-1 (Architecture):** The application must be cleanly containerized for Umbrel OS, ensuring proper persistent volume mapping and robust permission handling to prevent startup crashes.
- **NFR-2 (Performance):** The web dashboard must be extremely lightweight (e.g., using Vite + React or similar) to ensure it does not compete for resources with the node and mining bridge.
- **NFR-3:** Intelligent port mapping to avoid conflicts with existing mining proxies (e.g., routing Stratum over `55555`).
- **NFR-4 (Design Language):** The UI must mimic Umbrel's native design system to feel like a first-party application, heavily utilizing Dark and Light modes with Kaspa-branded accent colors. Future extensibility for custom themes should be considered.
