"""Shared pytest configuration for the NEON dev stack template.

Implements the constitution section 5.10 Playwright artifact policy:
traces and screenshots are captured on failure only, and all Playwright
artifacts land in `.data/test_artifacts/`.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
TEST_ARTIFACTS_DIR: Path = REPO_ROOT / ".data" / "test_artifacts"


def pytest_configure(config: pytest.Config) -> None:
    """Enforce the failure-only Playwright artifact policy (constitution 5.10)."""
    config.option.output = str(TEST_ARTIFACTS_DIR)
    config.option.screenshot = "only-on-failure"
    config.option.tracing = "retain-on-failure"
    config.option.video = "off"


@pytest.fixture(scope="session", autouse=True)
def ensure_test_artifacts_dir() -> Iterator[Path]:
    """Guarantee the artifact output directory exists before any test runs."""
    TEST_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    yield TEST_ARTIFACTS_DIR
