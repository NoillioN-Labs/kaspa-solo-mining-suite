"""Tests for Story 1.3: Dual ASIC Stratum Connection Point & Quick-Copy UX.

Verifies:
- Dynamic LAN IP detection and Stratum endpoints (FR-6, UX-DR6)
- Primary connection string: stratum+tcp://<lan-ip>:55555 (UX-DR6)
- Secondary connection string: stratum+tcp://umbrel.local:55555 (UX-DR6)
- Readiness notice callout (UX-DR6)
- API endpoint wiring (/api/connection and /api/status bridge.connection) (ARCH-2)
- Frontend AsicConnectionCard and clipboard copy interaction in App.jsx
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "web"


def run_node_eval(script: str) -> dict:
    cmd = ["node", "--input-type=module", "-e", script]
    res = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    for line in res.stdout.strip().split("\n"):
        if line.startswith("TEST_RESULT:"):
            return json.loads(line.replace("TEST_RESULT:", ""))
    raise AssertionError(f"No TEST_RESULT found in stdout: {res.stdout}\nstderr: {res.stderr}")


def test_dual_connection_string_resolution():
    """Verify primary and secondary Stratum connection strings and port 55555."""
    eval_script = """
    import { getConnectionEndpoints } from './web/server.js';
    const conn = getConnectionEndpoints(55555);
    console.log('TEST_RESULT:' + JSON.stringify(conn));
    process.exit(0);
    """
    data = run_node_eval(eval_script)
    assert data["port"] == 55555
    assert data["stratumLan"].startswith("stratum+tcp://")
    assert ":55555" in data["stratumLan"]
    assert data["stratumHostname"] == "stratum+tcp://umbrel.local:55555"
    assert "ASICs can be connected now" in data["readinessNotice"]


def test_lan_ip_custom_override():
    """Verify HOST_LAN_IP environment variable override."""
    cmd = [
        "node",
        "--input-type=module",
        "-e",
        """
        process.env.HOST_LAN_IP = '10.0.1.99';
        import('./web/server.js').then(m => {
          const conn = m.getConnectionEndpoints(55555);
          console.log('TEST_RESULT:' + JSON.stringify(conn));
          process.exit(0);
        });
        """,
    ]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
    for line in res.stdout.strip().split("\n"):
        if line.startswith("TEST_RESULT:"):
            data = json.loads(line.replace("TEST_RESULT:", ""))
            assert data["lanIp"] == "10.0.1.99"
            assert data["stratumLan"] == "stratum+tcp://10.0.1.99:55555"
            return
    raise AssertionError("No TEST_RESULT found")


def test_api_route_wiring():
    """Verify /api/connection route and bridge.connection in server.js."""
    server_path = WEB_DIR / "server.js"
    assert server_path.is_file()
    content = server_path.read_text(encoding="utf-8")

    assert "app.get('/api/connection'" in content
    assert "getConnectionEndpoints()" in content
    assert "connection: getConnectionEndpoints()" in content


def test_frontend_asic_connection_card():
    """Verify AsicConnectionCard, quick-copy, and readiness notice in App.jsx."""
    app_jsx = WEB_DIR / "src" / "App.jsx"
    assert app_jsx.is_file()
    content = app_jsx.read_text(encoding="utf-8")

    assert "function AsicConnectionCard" in content
    assert "stratumLan" in content
    assert "stratumHostname" in content
    assert "ASICs can be connected now" in content
    assert "reaches the DAG tip" in content
    assert "Copied!" in content
    assert "<AsicConnectionCard" in content
