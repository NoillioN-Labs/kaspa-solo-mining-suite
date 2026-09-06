"""
Test Suite for Story 3.2: Permanent Mined Blocks Ledger & Reward Analytics
Verifies:
- Zero-loss permanent storage invariant (AD-5): collector.resetData() preserves minedBlocks.
- Backend registerMinedBlock and /api/rewards endpoint schema.
- MinedBlocksLedger component structure, columns, reward decomposition, explorer links, and empty state.
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


def test_collector_reset_preserves_mined_blocks_permanence():
    """Verify AD-5 zero-loss invariant: collector.resetData() wipes telemetry but preserves minedBlocks."""
    script = """
    import { BackgroundCollectorService } from './web/collector.js';

    const c = new BackgroundCollectorService();
    c.state.history24h = [{ hashrate: 10 }];
    c.state.history30d = [{ hashrate: 10 }];
    c.state.history6m = [{ hashrate: 10 }];
    c.state.minedBlocks = [
      { hash: 'block-abc-123', worker: 'miner-01', reward: 128.5, timestamp: Date.now() }
    ];
    c.state.live.acceptedShares = 50;

    const res = c.resetData();
    const result = {
      resetResponse: res,
      history24hLen: c.state.history24h.length,
      history30dLen: c.state.history30d.length,
      history6mLen: c.state.history6m.length,
      minedBlocksLen: c.state.minedBlocks.length,
      preservedBlock: c.state.minedBlocks[0],
      acceptedShares: c.state.live.acceptedShares,
    };
    console.log('TEST_RESULT:' + JSON.stringify(result));
    process.exit(0);
    """
    data = run_node_eval(script)
    assert data["history24hLen"] == 0
    assert data["history30dLen"] == 0
    assert data["history6mLen"] == 0
    assert data["acceptedShares"] == 0
    assert data["minedBlocksLen"] == 1
    assert data["preservedBlock"]["hash"] == "block-abc-123"
    assert "permanently preserved" in data["resetResponse"]["message"].lower()


def test_register_mined_block_and_schema():
    """Verify registerMinedBlock in server.js produces complete reward and confirmation metadata."""
    script = """
    import { registerMinedBlock, collector } from './web/server.js';

    collector.state.minedBlocks = [];
    const block = registerMinedBlock({
      hash: 'abcdef1234567890',
      worker: 'iceriver-ks0-unit2',
      reward: 130.25,
      subsidy: 125.0,
      fees: 5.25,
      usdValue: 22.14,
      effort: 72.4,
      blueScore: 89123456,
      timestamp: 1772880000000,
    });

    console.log('TEST_RESULT:' + JSON.stringify({
      registered: block,
      ledgerCount: collector.state.minedBlocks.length,
    }));
    process.exit(0);
    """
    data = run_node_eval(script)
    assert data["ledgerCount"] == 1
    reg = data["registered"]
    assert reg["hash"] == "abcdef1234567890"
    assert reg["worker"] == "iceriver-ks0-unit2"
    assert reg["reward"] == 130.25
    assert reg["subsidy"] == 125.0
    assert reg["fees"] == 5.25
    assert reg["usdValue"] == 22.14
    assert reg["effort"] == 72.4
    assert reg["blueScore"] == 89123456
    assert reg["confirmed"] is True


def test_mined_blocks_ledger_frontend_contract():
    """Verify MinedBlocksLedger UI component specifications in App.jsx."""
    code = APP_JSX.read_text(encoding="utf-8")
    assert "export function MinedBlocksLedger" in code
    assert "<MinedBlocksLedger" in code

    # Columns / Content
    assert "Timestamp & Blue Score" in code
    assert "Winning Worker" in code
    assert "Round Effort" in code
    assert "Reward (Subsidy + Fees)" in code
    assert "Tip Confirmed" in code
    assert "https://explorer.kaspa.org/blocks/" in code

    # Effort color coding / lucky indicator
    assert "isLucky ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)'" in code
    assert "(Lucky)" in code

    # Empty State (UX-DR15)
    assert "No blocks mined yet. Active mining on port 55555 will record solved blocks here permanently." in code
    assert "All discovered blocks are permanently preserved across historical data purges (AD-5)." in code

    # Responsive table + mobile cards
    assert "worker-table-desktop" in code
    assert "worker-cards-mobile" in code
