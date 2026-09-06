import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_SRC_DIR = REPO_ROOT / "web" / "src"
GLOBAL_CSS_PATH = WEB_SRC_DIR / "styles" / "global.css"
SERVER_JS_PATH = REPO_ROOT / "web" / "server.js"


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


def test_worker_fleet_table_component_and_columns():
    """Verify WorkerFleetTable defines required columns and empty state."""
    app_jsx = (WEB_SRC_DIR / "App.jsx").read_text(encoding="utf-8")
    assert "export function WorkerFleetTable" in app_jsx
    assert "Worker Name" in app_jsx
    assert "Hashrate" in app_jsx
    assert "Shares (Acc / Stale / Inv)" in app_jsx
    assert "Difficulty" in app_jsx
    assert "Latency (Ping)" in app_jsx
    assert "Round Effort" in app_jsx
    # Empty state message
    assert "No workers currently connected. Connect an ASIC using" in app_jsx
    assert "stratum+tcp://" in app_jsx


def test_worker_fleet_table_effort_and_ping_styling():
    """Verify effort (<100% green, >100% amber) and ping latency coloring."""
    app_jsx = (WEB_SRC_DIR / "App.jsx").read_text(encoding="utf-8")
    assert "effort < 100" in app_jsx or "isLucky" in app_jsx
    assert "#10B981" in app_jsx  # lucky green
    assert "#F59E0B" in app_jsx  # amber/orange
    assert "ping" in app_jsx


def test_mobile_responsive_css_classes():
    """Verify responsive CSS classes for desktop table and mobile stacked cards."""
    app_jsx = (WEB_SRC_DIR / "App.jsx").read_text(encoding="utf-8")
    assert "worker-table-desktop" in app_jsx
    assert "worker-cards-mobile" in app_jsx
    assert "table-responsive" in app_jsx

    css = GLOBAL_CSS_PATH.read_text(encoding="utf-8")
    assert ".table-responsive" in css
    assert ".worker-table" in css
    assert ".worker-cards-mobile" in css
    assert "@media (max-width: 768px)" in css


def test_server_and_collector_workers_mapping():
    """Verify BackgroundCollectorService maps accepted, stale, invalid, ping, and effort."""
    eval_script = """
    import { BackgroundCollectorService } from './web/collector.js';
    const collector = new BackgroundCollectorService();
    const liveWorkers = collector.state.live.workers;
    console.log('TEST_RESULT:' + JSON.stringify({
      workersLength: liveWorkers.length,
      isArray: Array.isArray(liveWorkers)
    }));
    process.exit(0);
    """
    data = run_node_eval(eval_script)
    assert data["workersLength"] == 0
    assert data["isArray"] is True

    # Verify collector pollCycle worker parsing logic
    collector_js = (REPO_ROOT / "web" / "collector.js").read_text(encoding="utf-8")
    assert "accepted" in collector_js
    assert "stale" in collector_js
    assert "invalid" in collector_js
    assert "ping" in collector_js
    assert "effort" in collector_js

