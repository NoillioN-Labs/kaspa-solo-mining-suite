"""
NEON Dev Stack environment smoke test.

Boots Playwright (Chromium, headless) against example.com to verify the
local execution environment is intact. Logging is initialized via
`backend.core.logger.initialize_logging`, which automatically archives
stale `logs/*.log` files into `logs/archive/` before opening the new
timestamped log file (per AGENTS.md § 4.5 Log Archiving Protocol).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is importable when this script is run directly
# (e.g. `python3 scripts/utilities/data_util__smoke_test.py`).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.core.logger import initialize_logging  # noqa: E402

logger = initialize_logging("pipeline_smoke_test")


def run_playwright_test() -> None:
    logger.info("Initializing Playwright Smoke Test...")
    try:
        from playwright.sync_api import sync_playwright  # local import: heavy dep
    except ImportError as exc:
        logger.error(
            "Playwright is not installed in the active interpreter (%s). "
            "Install it via `uv pip install playwright && playwright install chromium`.",
            exc,
        )
        sys.exit(1)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            logger.info("Navigating to example.com...")
            page.goto("https://example.com")

            title = page.title()
            logger.info("Page Title Extracted: %s", title)

            browser.close()
            logger.info("Playwright shutdown successful.")
    except Exception as exc:
        logger.error("Playwright Execution Failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    logger.info("Starting Kaspa Solo Mining Suite Environment Verification")
    run_playwright_test()
    logger.info("Smoke Test Completed Successfully.")
