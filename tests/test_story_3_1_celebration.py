"""
Automated unit & regression tests for Story 3.1:
Block Discovery Event Detection & Non-Disruptive Celebration
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_SRC_DIR = REPO_ROOT / "web" / "src"
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


def test_block_celebration_confetti_component():
    """Verify BlockCelebration renders canvas overlay with non-blocking pointer events."""
    app_jsx = (WEB_SRC_DIR / "App.jsx").read_text(encoding="utf-8")
    assert "export function BlockCelebration" in app_jsx
    assert "pointerEvents: 'none'" in app_jsx or 'pointerEvents: "none"' in app_jsx
    assert "zIndex: 9999" in app_jsx
    assert "#70C7BA" in app_jsx  # Kaspa Teal confetti
    assert "cancelAnimationFrame" in app_jsx
    assert "onComplete" in app_jsx


def test_header_easter_egg_and_winning_worker_glow():
    """Verify interactive header Easter egg click and winning worker glow badge."""
    app_jsx = (WEB_SRC_DIR / "App.jsx").read_text(encoding="utf-8")
    # Easter egg on header
    assert "setShowCelebration(true)" in app_jsx
    assert "Easter egg" in app_jsx or "💎" in app_jsx
    # Winning worker highlight in table
    assert "winningWorker" in app_jsx
    assert "BLOCK SOLVED" in app_jsx
    assert "WINNER" in app_jsx
    # Kaspa explorer link in alert
    assert "explorer.kaspa.org/blocks/" in app_jsx


def test_server_block_event_detection_and_registration():
    """Verify server exposes /api/block_event and registerMinedBlock records blocks."""
    eval_script = """
    import { registerMinedBlock, collector } from './web/server.js';
    const initialCount = collector.state.minedBlocks.length;
    const testBlock = {
      hash: 'abc123def456kaspa789',
      worker: 'ks0-hero-worker',
      reward: 125.8,
      timestamp: Date.now()
    };
    const registered = registerMinedBlock(testBlock);
    const recent = collector.state.minedBlocks[0];

    console.log('TEST_RESULT:' + JSON.stringify({
      registeredHash: registered.hash,
      recentWorker: recent.worker,
      reward: recent.reward,
      countIncreased: collector.state.minedBlocks.length === initialCount + 1
    }));
    process.exit(0);
    """
    data = run_node_eval(eval_script)
    assert data["registeredHash"] == "abc123def456kaspa789"
    assert data["recentWorker"] == "ks0-hero-worker"
    assert data["reward"] == 125.8
    assert data["countIncreased"] is True

    server_js = SERVER_JS_PATH.read_text(encoding="utf-8")
    assert "app.get('/api/block_event'" in server_js
    assert "app.post('/api/block_event/test'" in server_js
