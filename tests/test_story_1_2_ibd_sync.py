"""Tests for Story 1.2: Multi-Stage Initial Block Download (IBD) Telemetry & Visualizer.

Verifies:
- Stage 1: Pruning Point Proof Validation (~92,160 headers) (FR-5, UX-DR5)
- Stage 2: DAA Header Catchup with rolling ETA (FR-5, UX-DR5)
- Stage 3: Tip Synchronized State (10 BPS) (FR-5, UX-DR15)
- Telemetry RPC Endpoint (/api/node/sync and /api/status) (ARCH-2, ARCH-4)
- Frontend SyncBanner and SyncProgressCard integration
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
    # Find the JSON output line
    for line in res.stdout.strip().split("\n"):
        if line.startswith("TEST_RESULT:"):
            return json.loads(line.replace("TEST_RESULT:", ""))
    raise AssertionError(f"No TEST_RESULT found in stdout: {res.stdout}\nstderr: {res.stderr}")


def test_stage_1_pruning_proof_validation():
    """Verify Stage 1: headerCount < 92,160 and !isSynced."""
    eval_script = """
    import { computeSyncStage } from './web/collector.js';
    const res = computeSyncStage({
      isSynced: false,
      headerCount: 46080,
      currentDaa: 0,
      targetDaa: 100000000
    });
    console.log('TEST_RESULT:' + JSON.stringify(res));
    """
    data = run_node_eval(eval_script)
    assert data["stage"] == 1
    assert data["stageName"] == "Proof Validation"
    assert "Validating DAG Pruning Proofs (~92k headers)..." in data["syncMessage"]
    assert data["percent"] == 50.0  # 46080 / 92160 * 100
    assert data["etaSeconds"] is None
    assert data["isSynced"] is False


def test_stage_2_daa_catchup_with_eta():
    """Verify Stage 2: headerCount >= 92,160 and DAA rate rolling ETA."""
    eval_script = """
    import { computeSyncStage } from './web/collector.js';
    const samples = [
      { timestamp: 10000, daa: 100000 },
      { timestamp: 20000, daa: 110000 } // 10,000 DAA in 10s = 1,000 DAA/s
    ];
    const res = computeSyncStage({
      isSynced: false,
      headerCount: 95000,
      currentDaa: 110000,
      targetDaa: 160000, // 50,000 remaining / 1,000 = 50s ETA
      daaSamples: samples
    });
    console.log('TEST_RESULT:' + JSON.stringify(res));
    """
    data = run_node_eval(eval_script)
    assert data["stage"] == 2
    assert data["stageName"] == "Header Catchup"
    assert "Catching up DAG headers" in data["syncMessage"]
    assert data["percent"] > 0
    assert data["etaSeconds"] == 50
    assert data["isSynced"] is False


def test_stage_3_synchronized():
    """Verify Stage 3: isSynced is true."""
    eval_script = """
    import { computeSyncStage } from './web/collector.js';
    const res = computeSyncStage({
      isSynced: true,
      headerCount: 150000,
      currentDaa: 100000000,
      targetDaa: 100000000
    });
    console.log('TEST_RESULT:' + JSON.stringify(res));
    """
    data = run_node_eval(eval_script)
    assert data["stage"] == 3
    assert data["stageName"] == "Synchronized"
    assert "Synchronized (10 BPS)" in data["syncMessage"]
    assert "Mining Active" in data["syncMessage"]
    assert data["percent"] == 100
    assert data["etaSeconds"] == 0
    assert data["isSynced"] is True


def test_server_routes_wiring():
    """Verify /api/node/sync and /api/status route definitions in server.js."""
    server_path = WEB_DIR / "server.js"
    assert server_path.is_file()
    content = server_path.read_text(encoding="utf-8")

    assert "app.get('/api/node/sync'" in content
    assert "collector.getSyncState()" in content
    assert "stage: live.syncStage" in content
    assert "syncMessage: live.syncMessage" in content
    assert "etaSeconds: live.etaSeconds" in content


def test_frontend_sync_components_and_formatting():
    """Verify SyncBanner and SyncProgressCard in App.jsx."""
    app_jsx = WEB_DIR / "src" / "App.jsx"
    assert app_jsx.is_file()
    content = app_jsx.read_text(encoding="utf-8")

    assert "function SyncBanner" in content
    assert "function SyncProgressCard" in content
    assert "function formatEta" in content
    assert "Validating DAG Pruning Proofs (~92k headers)..." in content
    assert "Stage 2: DAA Header Catchup" in content
    assert "Synchronized (10 BPS)" in content
    assert "Mining Active" in content

