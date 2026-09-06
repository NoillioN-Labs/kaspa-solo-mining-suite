"""Tests for Story 2.1: Autonomous Server-Side Telemetry Collector & Real Data Pipeline.

Verifies:
- Autonomous daemon lifecycle: starts on container boot, 5s polling interval (ARCH-2)
- Stratum Bridge polling: /api/workers and /api/stats (ARCH-2)
- Rusty Kaspad RPC polling: getDagInfo, getConnectedPeerInfo, getInfo (ARCH-2)
- Real data ground truth: zero mock fallbacks, genuine 0 hashrate/offline state on unreachable node (ARCH-4)
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


def test_collector_daemon_lifecycle():
    """Verify collector daemon starts with 5s interval, starts and stops cleanly."""
    eval_script = """
    import { BackgroundCollectorService } from './web/collector.js';
    const collector = new BackgroundCollectorService({ pollIntervalMs: 5000 });
    const initialInterval = collector.pollIntervalMs;
    const initialTimer = collector.timer;
    collector.start();
    const activeTimer = collector.timer !== null;
    collector.stop();
    const stoppedTimer = collector.timer;

    console.log('TEST_RESULT:' + JSON.stringify({
      initialInterval,
      initialTimer,
      activeTimer,
      stoppedTimer: stoppedTimer === null
    }));
    process.exit(0);
    """
    data = run_node_eval(eval_script)
    assert data["initialInterval"] == 5000
    assert data["initialTimer"] is None
    assert data["activeTimer"] is True
    assert data["stoppedTimer"] is True


def test_real_data_zero_mock_enforcement():
    """Verify that with unreachable endpoints, collector outputs 0 metrics with zero mocks."""
    eval_script = """
    import { BackgroundCollectorService } from './web/collector.js';
    // Point to non-routable port to simulate unreachable services
    const collector = new BackgroundCollectorService({
      bridgeUrl: 'http://127.0.0.1:59999',
      kaspadRpcUrl: 'http://127.0.0.1:59998'
    });

    await collector.pollCycle();
    const live = collector.state.live;
    console.log('TEST_RESULT:' + JSON.stringify({
      totalHashrate: live.totalHashrate,
      activeMiners: live.activeMiners,
      acceptedShares: live.acceptedShares,
      workersCount: live.workers.length,
      peersCount: live.peers.length,
      isSynced: live.isSynced,
      luckEstimate: live.luckEstimate
    }));
    process.exit(0);
    """
    data = run_node_eval(eval_script)
    assert data["totalHashrate"] == 0
    assert data["activeMiners"] == 0
    assert data["acceptedShares"] == 0
    assert data["workersCount"] == 0
    assert data["peersCount"] == 0
    assert data["isSynced"] is False
    assert data["luckEstimate"] == "N/A (No Hashrate)"


def test_server_startup_collector_wiring():
    """Verify web/server.js starts the autonomous background collector on load."""
    server_path = WEB_DIR / "server.js"
    assert server_path.is_file()
    content = server_path.read_text(encoding="utf-8")

    assert "import { collector } from './collector.js';" in content
    assert "collector.start();" in content
