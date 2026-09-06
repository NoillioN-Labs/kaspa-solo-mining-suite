"""Tests for Story 1.1: Multi-Container Orchestration & Resilient Network Seeding.

Verifies:
- docker-compose.yml service topology, ports, and CLI parameters (FR-1, FR-2, FR-3, ARCH-1, ARCH-3)
- hooks/pre-start permission automation and ASCII purity (FR-4, ARCH-6)
- umbrel-app.yml manifest compliance (NFR-1)
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "kaspa-solo-mining"


def test_docker_compose_structure():
    compose_path = APP_DIR / "docker-compose.yml"
    assert compose_path.is_file(), "docker-compose.yml must exist"

    with open(compose_path, encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    assert "kaspad" in services, "kaspad service must be defined"
    assert "bridge" in services, "bridge service must be defined"
    assert "web" in services, "web service must be defined"
    assert "app_proxy" in services, "app_proxy service must be defined"


def test_kaspad_service_configuration():
    compose_path = APP_DIR / "docker-compose.yml"
    with open(compose_path, encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    kaspad = compose["services"]["kaspad"]
    assert kaspad.get("image") == "kaspanet/rusty-kaspad:v2.0.1", "Must use official rusty-kaspad v2.0.1"

    command = kaspad.get("command", [])
    assert len(command) > 0, "kaspad must specify command arguments"
    assert command[0] == "kaspad", "First argument must be 'kaspad' for su-exec entrypoint"

    # Verify critical CLI flags
    cmd_str = " ".join(command)
    assert "--rpclisten=0.0.0.0:16110" in cmd_str, "Must configure rpclisten without hyphen"
    assert "--listen=0.0.0.0:16111" in cmd_str, "Must listen on mainnet P2P port 16111"
    assert "--utxoindex" in cmd_str, "Must enable utxoindex"
    assert "--disable-upnp" in cmd_str, "Must disable upnp"
    assert "--addpeer=157.90.7.39:16111" in cmd_str, "Must configure fallback peer 1"
    assert "--addpeer=49.12.171.174:16111" in cmd_str, "Must configure fallback peer 2"

    # Verify upstream DNS
    dns = kaspad.get("dns", [])
    assert "1.1.1.1" in dns and "8.8.8.8" in dns, "Must include upstream DNS resolvers"

    # Verify P2P port mapping
    ports = kaspad.get("ports", [])
    assert any("16111:16111" in str(p) for p in ports), "Host port 16111 must map to container 16111"


def test_bridge_service_configuration():
    compose_path = APP_DIR / "docker-compose.yml"
    with open(compose_path, encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    bridge = compose["services"]["bridge"]
    ports = bridge.get("ports", [])
    assert any("55555:5555/tcp" in str(p) for p in ports), "Stratum port must map host 55555 to container 5555"

    command = bridge.get("command", [])
    cmd_str = " ".join(command)
    assert "--kaspad-address=kaspad:16110" in cmd_str, "Bridge must connect to internal kaspad RPC"


def test_pre_start_hook_permissions_and_ascii():
    pre_start = APP_DIR / "hooks" / "pre-start"
    assert pre_start.is_file(), "hooks/pre-start must exist"

    raw = pre_start.read_bytes()
    # Enforce pure ASCII per AGENTS 5.5.1
    try:
        content = raw.decode("ascii")
    except UnicodeDecodeError:
        raise AssertionError("hooks/pre-start must be pure ASCII")

    assert "kaspad_data" in content, "Must initialize kaspad_data directory"
    assert "1000:1000" in content, "Must assign UID/GID 1000:1000"


def test_umbrel_app_manifest():
    manifest_path = APP_DIR / "umbrel-app.yml"
    assert manifest_path.is_file(), "umbrel-app.yml must exist"

    with open(manifest_path, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    assert manifest.get("id") == "kaspa-solo-mining", "App id must match folder name"
    assert str(manifest.get("manifestVersion")) == "1.1", "Manifest version must be 1.1"
    assert manifest.get("port") == 5557, "Port must be 5557"
