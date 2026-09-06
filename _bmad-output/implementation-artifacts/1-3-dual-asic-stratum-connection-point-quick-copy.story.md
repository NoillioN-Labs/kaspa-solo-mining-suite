---
baseline_commit: 60e63ee4cdbd6a35e768b36e82a144487d4d054e
---

# Story 1.3: Dual ASIC Stratum Connection Point & Quick-Copy Integration

Status: done

## Story

As a home miner ready to configure my ASICs,
I want the dashboard to display both my server's local LAN IPv4 and hostname connection strings with one-click copy buttons,
So that I can point my IceRiver or Antminer hardware directly to the bridge without failing due to ASIC firmware mDNS limitations.

## Acceptance Criteria

1. **Dual Connection String Resolution (`FR-6`, `UX-DR6`):**
   - **Given** the running server
   - **When** the ASIC Connection endpoint is queried
   - **Then** the primary connection string resolves to `stratum+tcp://<lan-ipv4>:55555` using dynamically detected LAN IPv4 (or configured host IP)
   - **And** the secondary connection string resolves to `stratum+tcp://umbrel.local:55555`.

2. **Quick-Copy Clipboard Action with Feedback (`UX-DR6`):**
   - **When** the miner clicks the copy button next to either connection string
   - **Then** the string is copied to the system clipboard
   - **And** visual tooltip/badge feedback displays *"Copied!"* for 2 seconds.

3. **Mining Readiness Callout (`UX-DR6`):**
   - **Then** the card displays the readiness notice:
     *"ASICs can be connected now; mining will commence automatically once the node reaches the DAG tip."*

4. **API Endpoint Wiring (`ARCH-2`):**
   - **When** client queries `/api/connection` or `/api/status`
   - **Then** the payload contains connection endpoints `{ lanIp: string, stratumLan: string, stratumHostname: string, port: 55555 }`.

## Tasks / Subtasks

- [x] Task 1: Backend LAN IP Resolution & Connection Endpoint (AC: 1, 4)
  - [x] Implement network interface discovery utility in `web/server.js` (detecting non-internal IPv4)
  - [x] Expose `GET /api/connection` returning structured Stratum endpoints
  - [x] Include `connection` object in `GET /api/status` payload

- [x] Task 2: Frontend AsicConnectionCard Component (AC: 1, 2, 3)
  - [x] Implement `AsicConnectionCard` with primary and secondary connection blocks
  - [x] Implement copy button with clipboard API and 2-second visual feedback badge
  - [x] Include the mining readiness callout notice

- [x] Task 3: Unit & Regression Testing (AC: 1-4)
  - [x] Author `tests/test_story_1_3_connection.py`
  - [x] Verify endpoint response structure and port 55555 binding
  - [x] Verify copy interaction and readiness text

## Dev Notes

### Relevant Architecture Patterns and Constraints
- Dedicated host port: 55555 (mapped to bridge container 5555)
- ASIC firmware compatibility: Many IceRiver/Antminer control boards lack mDNS resolvers, requiring direct IPv4 (`stratum+tcp://192.168.x.x:55555`).

### Source Tree Components Touched
- `web/server.js`: LAN IP detection & connection endpoint
- `web/src/App.jsx`: `AsicConnectionCard` component & copy interaction
- `tests/test_story_1_3_connection.py`: Automated verification

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### File List
- `web/server.js`
- `web/src/App.jsx`
- `tests/test_story_1_3_connection.py`
