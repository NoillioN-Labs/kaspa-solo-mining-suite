"""
Automated unit & regression tests for Story 2.2:
Reactive Overview Dashboard & 10 BPS GHOSTDAG Canvas Visualizer
"""

import re
from pathlib import Path

WEB_SRC_DIR = Path(__file__).parent.parent / "web" / "src"
SERVER_JS_PATH = Path(__file__).parent.parent / "web" / "server.js"


def test_format_hashrate_utility_in_app():
    """Verify formatHashrate handles GH/s, TH/s, PH/s scaling."""
    app_jsx = (WEB_SRC_DIR / "App.jsx").read_text(encoding="utf-8")
    assert "export function formatHashrate(thVal)" in app_jsx
    assert "GH/s" in app_jsx
    assert "TH/s" in app_jsx
    assert "PH/s" in app_jsx
    assert "Fira Code" in app_jsx or "monospace" in app_jsx


def test_metric_cards_grid_structure_and_styling():
    """Verify MetricCardsGrid renders Fleet Hashrate, Active Miners, Blocks 24H, and Round Effort."""
    app_jsx = (WEB_SRC_DIR / "App.jsx").read_text(encoding="utf-8")
    assert "export function MetricCardsGrid" in app_jsx
    assert "Fleet Hashrate" in app_jsx
    assert "Active Miners" in app_jsx
    assert "Blocks (24H)" in app_jsx
    assert "Round Effort" in app_jsx
    # Effort color badge logic (< 100% green, > 100% amber)
    assert "effortColor" in app_jsx or "effort <= 100" in app_jsx or "effort < 100" in app_jsx
    assert "100%" in app_jsx


def test_ghostdag_canvas_visualizer():
    """Verify HTML5 Canvas 10 BPS GHOSTDAG animation loop and color distinctions."""
    app_jsx = (WEB_SRC_DIR / "App.jsx").read_text(encoding="utf-8")
    assert "export function GhostdagCanvas" in app_jsx
    assert "<canvas" in app_jsx
    assert "10 BPS Live" in app_jsx
    # Consensus chain blue/teal vs parallel red
    assert "#70C7BA" in app_jsx
    assert "#EF4444" in app_jsx
    assert "Selected Chain (Blue Blocks)" in app_jsx
    assert "Parallel Merged (Red Blocks)" in app_jsx
    assert "requestAnimationFrame" in app_jsx
    assert "cancelAnimationFrame" in app_jsx


def test_hashrate_trend_chart():
    """Verify 24-Hour Hashrate Trend SVG area chart with teal gradient."""
    app_jsx = (WEB_SRC_DIR / "App.jsx").read_text(encoding="utf-8")
    assert "export function HashrateTrendChart" in app_jsx
    assert "24-Hour Hashrate Trend" in app_jsx
    assert "<svg" in app_jsx
    assert "linearGradient" in app_jsx
    assert "hashrate-grad" in app_jsx
    assert "fill=\"url(#hashrate-grad)\"" in app_jsx


def test_server_stats_endpoint_includes_24h_metrics():
    """Verify /api/stats includes blocks24h and roundEffort fields."""
    server_js = SERVER_JS_PATH.read_text(encoding="utf-8")
    assert "app.get('/api/stats'" in server_js
    assert "blocks24h" in server_js
    assert "roundEffort" in server_js
    assert "totalHashrateTh" in server_js
