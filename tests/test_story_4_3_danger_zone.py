"""
Test Suite for Story 4.3: Danger Zone Historical Telemetry Reset & Safety Gate
Verifies:
- Safety gate invariant (AD-6): POST /api/data/reset wipes rollups while preserving minedBlocks and active stratum.
- DangerZone UI component specifications: double-confirmation modal, protected invariants disclosure,
  risk checkbox, and endpoint dispatch.
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_JS = REPO_ROOT / "web" / "server.js"
APP_JSX = REPO_ROOT / "web" / "src" / "App.jsx"


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


def test_server_danger_zone_reset_endpoint_and_invariants():
    """Verify POST /api/data/reset wipes historical curves but preserves mined blocks."""
    script = """
    import { collector } from './web/server.js';

    collector.state.history24h = [{ hashrate: 10 }];
    collector.state.history30d = [{ hashrate: 10 }];
    collector.state.history6m = [{ hashrate: 10 }];
    collector.state.minedBlocks = [
      { hash: 'permanent-block-001', worker: 'antminer-ks3', reward: 125 }
    ];
    collector.state.live.acceptedShares = 500;

    const resetResult = collector.resetData();

    const payload = {
      success: resetResult.success,
      message: resetResult.message,
      h24Count: collector.state.history24h.length,
      h30Count: collector.state.history30d.length,
      h6mCount: collector.state.history6m.length,
      sharesReset: collector.state.live.acceptedShares === 0,
      minedBlocksPreserved: collector.state.minedBlocks.length === 1,
      minedBlockHash: collector.state.minedBlocks[0].hash,
    };

    console.log('TEST_RESULT:' + JSON.stringify(payload));
    process.exit(0);
    """
    data = run_node_eval(script)
    assert data["success"] is True
    assert data["h24Count"] == 0
    assert data["h30Count"] == 0
    assert data["h6mCount"] == 0
    assert data["sharesReset"] is True
    assert data["minedBlocksPreserved"] is True
    assert data["minedBlockHash"] == "permanent-block-001"

    # Server route check
    server_code = SERVER_JS.read_text(encoding="utf-8")
    assert "app.post('/api/data/reset'" in server_code


def test_danger_zone_frontend_modal_and_safety_gate():
    """Verify DangerZone component requires explicit checkbox confirmation before reset."""
    code = APP_JSX.read_text(encoding="utf-8")
    assert "export function DangerZone" in code
    assert "<DangerZone" in code

    # Safety Gate & Warning Elements (UX-DR14, AD-6)
    assert "Danger Zone" in code
    assert "Reset Historical Data" in code
    assert "Erase Historical Mining Telemetry?" in code
    assert "Protected Invariants" in code
    assert "Active Stratum mining connections on port 55555 remain connected" in code
    assert "Mined Blocks Ledger is permanent and will NOT be erased (AD-5)" in code

    # Risk confirmation checkbox
    assert "confirmedRisk" in code
    assert "I understand that historical telemetry curves will be erased" in code
    assert "disabled={!confirmedRisk || resetting}" in code

    # Dispatch & Notification
    assert "fetch('/api/data/reset', { method: 'POST' })" in code
    assert "Confirm Reset Telemetry" in code
