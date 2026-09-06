# Story 1.1: Multi-Container Orchestration & Resilient Network Seeding

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a home miner installing the suite on Umbrel,
I want Docker Compose to orchestrate Rusty Kaspad v2.0.1 and Stratum Bridge v2.0.1 with automated permissions, dedicated port bindings, and reliable peer seeding,
So that my node connects to the Kaspa mainnet immediately without 0-peer network stalls, port collisions, or permission crashes.

## Acceptance Criteria

1. **Host Permission Automation (`FR-4`, `ARCH-6`):**
   - **Given** an UmbrelOS host running Docker Compose
   - **When** the app lifecycle triggers `hooks/pre-start` and boots the container stack
   - **Then** host data directories (`${APP_DATA_DIR}/kaspad_data` and `${APP_DATA_DIR}/data`) are created and assigned UID/GID `1000:1000` permissions (`0750` for data, `0777` or `1000:1000` for kaspad_data).

2. **Official Rusty Kaspad v2.0.1 Integration (`FR-1`, `ARCH-1`):**
   - **Given** the `kaspad` service defined in `docker-compose.yml`
   - **When** the service starts
   - **Then** it uses official image `kaspanet/rusty-kaspad:v2.0.1` with `kaspad` as the first CLI command argument (ensuring entrypoint `su-exec kaspa "$@"` executes correctly)
   - **And** runs with `--rpclisten=0.0.0.0:16110` (no hyphen in rpclisten), `--listen=0.0.0.0:16111`, `--rpclisten-json=0.0.0.0:18110`, `--utxoindex`, and `--disable-upnp`.

3. **Resilient Network Peering & DNS Seeding (`FR-2`):**
   - **Given** the `kaspad` node daemon booting on a home LAN
   - **When** P2P swarm discovery initiates
   - **Then** the container resolves peers via upstream DNS resolvers (`1.1.1.1`, `8.8.8.8`)
   - **And** connects directly to verified static fallback seeders (`--addpeer=157.90.7.39:16111`, `--addpeer=49.12.171.174:16111`), reliably establishing outbound peers within 60 seconds without 0-peer network isolation.

4. **Dedicated Stratum Port Binding (`FR-3`, `ARCH-3`):**
   - **Given** the Stratum Bridge container (`bridge`)
   - **When** the container binds its external stratum mining listener
   - **Then** it maps strictly to host TCP port `55555:5555/tcp` to prevent collisions with third-party mining proxies or standard pool endpoints
   - **And** connects internally to `kaspad:16110` across the internal Docker bridge network without exposing gRPC/wRPC ports on the host.

5. **Umbrel App Store Packaging Compliance (`NFR-1`):**
   - **Given** `umbrel-app.yml` manifest
   - **When** validated against Umbrel 1.7+ Community App Store specs
   - **Then** `manifestVersion` is `1.1`, `port` is `5557`, `app_proxy` maps to `web:8080`, and permissions adhere to Umbrel guidelines.

## Tasks / Subtasks

- [ ] Task 1: Verify and Harden `hooks/pre-start` Permissions (AC: 1)
  - [ ] Ensure `${APP_DATA_DIR}/kaspad_data` is initialized with UID/GID `1000:1000`
  - [ ] Ensure `${APP_DATA_DIR}/data/config.yaml` fallback template is populated with `1000:1000` ownership
  - [ ] Verify script is pure ASCII and executable (`chmod +x`)

- [ ] Task 2: Validate `docker-compose.yml` Service Configuration (AC: 2, 3, 4)
  - [ ] Verify `kaspad` service syntax: `image: kaspanet/rusty-kaspad:v2.0.1`, command array starts with `kaspad`
  - [ ] Verify RPC flags: `--rpclisten=0.0.0.0:16110` (no hyphen), `--rpclisten-json=0.0.0.0:18110`
  - [ ] Verify peer seeding: `--addpeer=157.90.7.39:16111`, `--addpeer=49.12.171.174:16111`, upstream DNS `1.1.1.1`, `8.8.8.8`
  - [ ] Verify port mapping: Host `16111:16111` for P2P, Host `55555:5555/tcp` for Stratum Bridge, internal RPC strictly unexposed
  - [ ] Verify `stop_grace_period` (30s for kaspad, 20s for bridge) to allow clean DB flushing

- [ ] Task 3: Umbrel Packaging & Manifest Validation (AC: 5)
  - [ ] Validate `umbrel-app.yml` manifest 1.1 fields (id, name, version, port, submitter)
  - [ ] Verify `app_proxy` points to `kaspa-solo-mining_web_1:8080`
  - [ ] Run automated packaging validation script (`validate_umbrel_package.mjs`)

- [ ] Task 4: End-to-End Orchestration Verification (AC: 1-5)
  - [ ] Validate syntax with `docker compose config`
  - [ ] Verify clean startup sequence: `kaspad` boots, peers connect > 0 within 60s, `bridge` connects to `kaspad:16110`

## Dev Notes

### Relevant Architecture Patterns and Constraints
- **Multi-Container Topology (`ARCH-1`):** Three isolated services (`kaspad`, `bridge`, `web`) on Docker bridge network. `bridge` depends on `kaspad`; `web` depends on both.
- **Port Mapping Invariant (`ARCH-3`):**
  - Stratum Mining Port: Host `55555` -> Container `5555/tcp`.
  - P2P Swarm Port: Host `16111` -> Container `16111`.
  - Web UI Port: Host `5557` via Umbrel `app_proxy` -> Container `8080`.
  - Internal RPC Interfaces (`16110`, `18110`, `3030`): strictly unexposed on host.
- **Entrypoint Trap in `kaspanet/rusty-kaspad:v2.0.1`:**
  - The image entrypoint executes `su-exec kaspa "$@"`.
  - Therefore, `kaspad` MUST be specified as the very first argument in the Docker `command:` list, or the container will fail with command not found.
- **CLI Flags in Rusty Kaspad v2.0.1:**
  - RPC flag is `--rpclisten=0.0.0.0:16110` (no hyphen between rpc and listen).
  - `--dnsseed` does not exist in v2.0.1 (only `--nodnsseed`).
  - `--addpeer` requires strict `<IP:PORT>` syntax; hostnames/domain names crash the binary on startup.

### Source Tree Components Touched
- `kaspa-solo-mining/docker-compose.yml`: Orchestration definition
- `kaspa-solo-mining/hooks/pre-start`: Host permissions and config provisioning
- `kaspa-solo-mining/umbrel-app.yml`: Umbrel App Store manifest
- `kaspa-solo-mining/config/bridge.yaml`: Default bridge configuration template

### Testing Standards Summary
- Native command execution on Windows/PowerShell must verify exit codes.
- Validate compose YAML syntax and port mapping contracts.
- Automated Umbrel manifest check via `scripts/utilities/validate_umbrel_package.mjs`.

### Project Structure Notes
- Alignment with `kaspa-solo-mining/` Umbrel app root.
- All persistent runtime state mapped to `${APP_DATA_DIR}`.

### References
- [PRD: Core Node & Stratum Infrastructure](file:///c:/Users/natha/OneDrive/Documents/Side%20Hussle/Kaspa%20Stratum%20Bridge/_bmad-output/planning-artifacts/prds/prd-Kaspa-Solo-Mining-Suite-2026-09-04/prd.md#51-core-node--stratum-infrastructure) (`FR-1`, `FR-2`, `FR-3`, `FR-4`)
- [Architecture Map: System Topology](file:///c:/Users/natha/OneDrive/Documents/Side%20Hussle/Kaspa%20Stratum%20Bridge/_bmad-output/planning-artifacts/ARCHITECTURE.md#1-system-topology--container-boundaries)
- [Architecture Decisions: AD-2 & AD-3](file:///c:/Users/natha/OneDrive/Documents/Side%20Hussle/Kaspa%20Stratum%20Bridge/_bmad-output/planning-artifacts/ARCHITECTURE.md#ad-3-explicit-port-mapping-standards)
- [Umbrel App Store Packaging Spec](file:///c:/Users/natha/OneDrive/Documents/Side%20Hussle/Kaspa%20Stratum%20Bridge/.agent/skills/umbrel-expert/SKILL.md)

## Dev Agent Record

### Agent Model Used
Gemini 2.5 Pro (Antigravity Agentic Pair)

### Debug Log References
- Live Umbrel verification session: peer connection resolution on port 16111 with static peers (`157.90.7.39:16111`, `49.12.171.174:16111`).
- Pruning point proof download (~92k headers) verified on Rusty Kaspad v2.0.1.

### Completion Notes List
- Comprehensive developer guide and acceptance criteria created for Story 1.1.

### File List
- `kaspa-solo-mining/docker-compose.yml`
- `kaspa-solo-mining/hooks/pre-start`
- `kaspa-solo-mining/umbrel-app.yml`
- `kaspa-solo-mining/config/bridge.yaml`
