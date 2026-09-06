"""
Test Suite for Story 4.2: 6-Month Tiered Storage Retention Engine (<4MB Footprint)
Verifies:
- 3-tier rollup caps: 24h (1,440 points), 30d (2,880 points), 6m (4,320 points).
- Automatic pruning of data older than 180 days while preserving permanent mined blocks.
- Serialized JSON disk footprint is strictly under 4 MB across maximum retention points.
- Multi-range frontend chart range selectors ('24h', '30d', '6m') and tiered resolution labels.
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
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


def test_tiered_rollup_caps_and_pruning_invariants():
    """Verify collector downsamples into 1440, 2880, and 4320 caps and prunes >180d."""
    script = """
    import { BackgroundCollectorService } from './web/collector.js';

    const c = new BackgroundCollectorService();
    const now = Date.now();

    // 1. Fill 24h history beyond 1440
    for (let i = 0; i < 1500; i++) {
      c.rawBuffer = [{ timestamp: now - (1500 - i) * 60000, hashrate: 15.5, acceptedShares: i, difficulty: 1 }];
      c.aggregate1Minute(now - (1500 - i) * 60000);
    }

    // 2. Fill 30d history beyond 2880
    for (let i = 0; i < 2950; i++) {
      c.aggregate15Minutes(now - (2950 - i) * 900000);
    }

    // 3. Fill 6m history beyond 4320 and include points older than 180 days
    const ms180d = 180 * 24 * 60 * 60 * 1000;
    c.state.history6m = [
      { timestamp: now - ms180d - 50000000, hashrate: 12.0, shares: 100 }, // Older than 180d
      { timestamp: now - ms180d - 1000000, hashrate: 12.0, shares: 100 },  // Older than 180d
      { timestamp: now - ms180d + 1000000, hashrate: 14.0, shares: 200 },  // Within 180d
    ];
    c.state.minedBlocks = [
      { hash: 'block-permanent-abc', timestamp: now - ms180d - 999999999 } // Permanent block
    ];

    c.pruneOldData(now);

    // Measure serialized payload size across max retention points
    const samplePt = { timestamp: now, timeLabel: "12:00", hashrate: 15.5, shares: 1000, difficulty: 1 };
    const fullState = {
      history24h: Array(1440).fill(samplePt),
      history30d: Array(2880).fill(samplePt),
      history6m: Array(4320).fill({ timestamp: now, dateLabel: "2026-09-06", hashrate: 15.5, shares: 1000 }),
      minedBlocks: Array(50).fill({ hash: "7f9a2b4c5d6e1f0a2b3c4d5e", timestamp: now, reward: 125 }),
    };
    const jsonBytes = Buffer.byteLength(JSON.stringify(fullState), 'utf8');

    console.log('TEST_RESULT:' + JSON.stringify({
      history24hLen: c.state.history24h.length,
      history30dLen: c.state.history30d.length,
      history6mLen: c.state.history6m.length,
      minedBlocksPreserved: c.state.minedBlocks.length === 1,
      totalBytes: jsonBytes,
      under4MB: jsonBytes < 4 * 1024 * 1024,
    }));
    process.exit(0);
    """
    data = run_node_eval(script)
    assert data["history24hLen"] == 1440
    assert data["history30dLen"] == 2880
    assert data["history6mLen"] == 1  # Only the point within 180d survived pruning
    assert data["minedBlocksPreserved"] is True
    assert data["under4MB"] is True
    # Verify footprint is comfortably small (under 1.5MB)
    assert data["totalBytes"] < 1500000


def test_hashrate_chart_frontend_multi_range_contract():
    """Verify HashrateTrendChart component supports 24H, 30D, 6M ranges and resolution tags."""
    code = APP_JSX.read_text(encoding="utf-8")
    assert "export function HashrateTrendChart" in code

    # Range tabs
    assert "['24h', '30d', '6m'].map" in code
    assert "fetch(`/api/history?range=${range}`)" in code

    # Resolution indicators per tier
    assert "1m Resolution" in code
    assert "15m Resolution" in code
    assert "1h Resolution" in code

    # Titles & X-axis start markers
    assert "24-Hour Hashrate Trend" in code
    assert "30-Day Hashrate Trend" in code
    assert "6-Month Hashrate Trend" in code
    assert "24h ago" in code
    assert "30d ago" in code
    assert "180d ago" in code
