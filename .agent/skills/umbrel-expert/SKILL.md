---
name: umbrel-expert
description: >-
  Expert guidelines, packaging contracts, validation rules, and lifecycle requirements
  for developing, packaging, and deploying applications on the Umbrel and UmbrelOS platform.
  Use when validating or authoring umbrel-app.yml, docker-compose.yml, hooks, and community store structures.
---

# Umbrel Expert Skill

Comprehensive rules, invariants, and packaging requirements for Umbrel applications and Community App Stores based on official UmbrelOS specifications and real-world validation contracts.

---

## 1. Directory & Community App Store Hierarchy

An Umbrel Community App Store repository MUST adhere to this exact tree:

```
<repo-root>/
├── umbrel-app-store.yml          # Root store registration
└── <app-id>/                     # Must EXACTLY match 'id' inside umbrel-app.yml
    ├── umbrel-app.yml            # Application metadata manifest
    ├── docker-compose.yml        # Docker compose services
    ├── icon.svg                  # Vector application icon
    ├── 1.png, 2.png              # Gallery preview screenshots
    ├── exports.sh                # Optional: exported env variables evaluated on host
    ├── hooks/
    │   └── pre-start             # Crucial: runs BEFORE containers start (permissions/data init)
    └── config/ (optional)        # Configuration templates copied to persistent volumes
```

### `umbrel-app-store.yml` Rules:
```yaml
id: "<store-id>"       # Must match or harmonize with app category
name: "<Store Name>"   # Display name in Umbrel UI
```

---

## 2. The `umbrel-app.yml` Manifest Contract

The `umbrel-app.yml` is parsed strictly by Umbrel's store validator. Any missing required field or formatting issue causes Umbrel to silently hide the app card or fail validation:

```yaml
manifestVersion: 1.1                               # Use 1.1 for modern UmbrelOS
id: "<app-id>"                                     # MUST match directory name exactly (lowercase, hyphens only)
category: "<category-id>"                          # e.g., kaspa, crypto, media, etc.
name: "<App Display Name>"                         # Display title
version: "X.Y.Z"                                   # Semantic versioning (major.minor.patch)
tagline: "<One line elevator pitch>"
icon: "https://raw.githubusercontent.com/.../icon.svg" # MUST be an absolute public raw URL
description: >-
  <Full multi-line description of what the app does>
developer: "<Developer or Org Name>"
website: "https://..."
dependencies: []                                   # Array of dependent app IDs (e.g. [rusty-kaspad] or empty [])
repo: "https://github.com/..."
support: "https://github.com/.../issues"
port: <unique_host_port>                           # E.g. 5556, 5557 (DO NOT use 80, 8080, 3000, 2112 which conflict)
gallery:
  - "https://raw.githubusercontent.com/.../1.png"  # MUST be absolute public raw URLs
  - "https://raw.githubusercontent.com/.../2.png"
releaseNotes: >-
  <Release highlights>
path: ""                                           # Subpath if app doesn't serve root (typically "")
defaultUsername: ""                                # If app has default credentials
defaultPassword: ""
submitter: "<Author Name>"
submission: ""
```

---

## 3. The `docker-compose.yml` Invariants

Every Umbrel app is orchestrated via Docker Compose (version 3.7).

### Mandatory Service: `app_proxy`
Umbrel wraps apps in a built-in reverse proxy (Tor + local web proxy).
```yaml
version: "3.7"

services:
  app_proxy:
    environment:
      APP_HOST: <app-id>_<web-service-name>_1      # Exact Docker container name! (e.g. kaspa-solo-mining_web_1)
      APP_PORT: 8080                              # Internal port that web service listens on
```

### Web Service Rules:
1. **Never expose the web UI port on the host:**
   - ❌ WRONG: `ports: ["8080:8080"]` (causes port bind collision with Umbrel's proxy)
   - ✅ CORRECT: Let `app_proxy` connect internally over Docker's network bridge.
2. **Deterministic Healthchecks:**
   - Umbrel polls container health before reporting "Installed". If a container does not declare a healthcheck or exits immediately, Umbrel assumes installation failed (typically at 1% or after 10-20s timeout).
   - Add a lightweight healthcheck:
   ```yaml
   healthcheck:
     test: ["CMD", "node", "-e", "fetch('http://127.0.0.1:8080/api/status').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"]
     interval: 30s
     timeout: 5s
     retries: 3
     start_period: 20s
   ```
3. **Stop Grace Periods:**
   - Set `stop_grace_period: 30s` for database / blockchain node processes to prevent data corruption.

---

## 4. Permissions & Lifecycle Hooks (`hooks/pre-start`)

Umbrel mounts app data inside `${APP_DATA_DIR}`. On UmbrelOS, containers frequently execute under UID `1000:1000` (`node` or standard non-root user).

### Invariant:
If a volume directory does not exist or has incorrect ownership, containers crash with `EACCES` or `Permission Denied` upon startup.
`hooks/pre-start` MUST exist and set permissions:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Create all declared volume directories
install -d -m 0750 -o 1000 -g 1000 "${APP_DATA_DIR}/data"
install -d -m 0750 -o 1000 -g 1000 "${APP_DATA_DIR}/kaspad_data"

# Ensure recursive ownership
chown -R 1000:1000 "${APP_DATA_DIR}/data"
chown -R 1000:1000 "${APP_DATA_DIR}/kaspad_data"
```

---

## 5. Pre-Push Validation Checklist (Run Before Every Release)

Before pushing any new release or package update to GitHub, verify:
- [ ] Folder name in store matches `id` in `umbrel-app.yml`.
- [ ] `manifestVersion` is `1.1`.
- [ ] `icon` and `gallery` links are valid absolute `https://raw.githubusercontent.com/...` URLs.
- [ ] `port` in `umbrel-app.yml` is unique and does not collide with common ports (5557+ recommended).
- [ ] `app_proxy.APP_HOST` exactly matches `<folder_name>_<service>_1`.
- [ ] No internal web service exposes its HTTP port directly to the host `ports:` array.
- [ ] All declared Docker volumes in `docker-compose.yml` are initialized and permissioned in `hooks/pre-start`.
- [ ] Docker container entrypoints call `app.listen()` and keep the process in the foreground.
- [ ] Container images exist and are publicly pullable on `ghcr.io` or Docker Hub (multi-arch `linux/amd64` and `linux/arm64`).
