"""
Automated unit & regression tests for Story 2.4:
Hardware Tuning Presets & Real-Time Vardiff Control
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


def test_preset_catalog_and_default_state():
    """Verify PRESET_CATALOG contains 5 presets defaulting to automatic auto-vardiff."""
    eval_script = """
    import { PRESET_CATALOG, getActivePreset, setActivePreset } from './web/server.js';
    const initial = getActivePreset();
    const catalogIds = PRESET_CATALOG.map(p => p.id);
    const hasAuto = catalogIds.includes('automatic');
    const hasKs0 = catalogIds.includes('iceriver-ks0');
    const hasKs1 = catalogIds.includes('iceriver-ks1-ks2');
    const hasKs3 = catalogIds.includes('antminer-ks3-ks5');
    const hasEnterprise = catalogIds.includes('enterprise-ks7-farm');

    // Test dynamic switching
    const switched = setActivePreset('iceriver-ks0');
    const current = getActivePreset();
    // Revert back to automatic
    setActivePreset('automatic');

    console.log('TEST_RESULT:' + JSON.stringify({
      initial,
      catalogLength: PRESET_CATALOG.length,
      hasAuto,
      hasKs0,
      hasKs1,
      hasKs3,
      hasEnterprise,
      switched,
      current
    }));
    process.exit(0);
    """
    data = run_node_eval(eval_script)
    assert data["initial"] == "automatic"
    assert data["catalogLength"] == 5
    assert data["hasAuto"] is True
    assert data["hasKs0"] is True
    assert data["hasKs1"] is True
    assert data["hasKs3"] is True
    assert data["hasEnterprise"] is True
    assert data["switched"] is True
    assert data["current"] == "iceriver-ks0"


def test_preset_selector_component_structure_and_modal():
    """Verify PresetSelector component in App.jsx renders grid and confirmation modal."""
    app_jsx = (WEB_SRC_DIR / "App.jsx").read_text(encoding="utf-8")
    assert "export function PresetSelector" in app_jsx
    assert "Hardware Tuning & Vardiff Presets" in app_jsx
    assert "Active:" in app_jsx
    assert "Nominal:" in app_jsx
    assert "Confirm Hardware Tuning Change" in app_jsx
    assert "without restarting Rusty Kaspad" in app_jsx
    assert "/api/presets/select" in app_jsx


def test_server_routes_for_presets():
    """Verify server.js defines /api/presets and /api/presets/select endpoints."""
    server_js = SERVER_JS_PATH.read_text(encoding="utf-8")
    assert "app.get('/api/presets'" in server_js
    assert "app.post('/api/presets/select'" in server_js
    assert "app.post('/api/tuning'" in server_js
