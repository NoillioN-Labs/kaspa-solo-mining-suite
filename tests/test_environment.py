"""Environment sanity checks for the NEON dev stack template.

These tests verify the local development environment (venv isolation,
Playwright, log directories, governance docs) without calling any paid
external APIs. The single paid connectivity check is marked with
``@pytest.mark.paid`` and is deselected by default (see pyproject.toml);
run it explicitly with ``pytest -m paid``.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONFIG_PATH = "config.yaml"

# Provider registry: maps a provider slug (the prefix of models.primary.name,
# e.g. "google/gemini-3.5-flash" -> "google") to the environment variables
# that may hold its API key. Vendor-neutral: extend as providers change.
PROVIDER_ENV_VARS: dict[str, list[str]] = {
    "google": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
}


def _get_secret(names: list[str]) -> str | None:
    """Return the first matching secret from the environment or the local .env file."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    if os.path.exists(".env"):
        with open(".env", encoding="utf-8") as f:
            for line in f:
                for name in names:
                    if line.startswith(f"{name}="):
                        value = line.strip().split("=", 1)[1].strip("\"'")
                        if value:
                            return value
    return None


def _load_primary_model() -> str:
    """Read models.primary.name from config.yaml, skipping if unavailable."""
    if not os.path.exists(CONFIG_PATH):
        pytest.skip(f"{CONFIG_PATH} not found; cannot determine primary model.")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    model_name = ((config.get("models") or {}).get("primary") or {}).get("name")
    if not model_name:
        pytest.skip("models.primary.name is not defined in config.yaml.")
    return str(model_name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_playwright_installed():
    """Verify Playwright browsers are installed and can boot headless."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # Just launching the browser confirms dependencies are installed
        browser = p.chromium.launch(headless=True)
        assert browser.is_connected()
        browser.close()


@pytest.mark.paid
def test_llm_api_connectivity():
    """Verify the configured primary LLM provider is reachable and the API key is valid.

    Provider-aware: reads ``models.primary.name`` from config.yaml, derives the
    provider from its prefix (e.g. ``google/gemini-3.5-flash``), and skips when
    no API key for that provider is available. Marked ``paid`` because it makes
    a real (minimal) completion request.
    """
    model_name = _load_primary_model()
    provider, _, model_id = model_name.partition("/")
    if not model_id:
        # No prefix: infer provider from well-known model-name conventions.
        model_id = provider
        if model_id.startswith("claude"):
            provider = "anthropic"
        elif model_id.startswith("gemini"):
            provider = "google"
        elif model_id.startswith("gpt"):
            provider = "openai"
        else:
            pytest.skip(f"Cannot infer provider for model '{model_name}'.")

    env_vars = PROVIDER_ENV_VARS.get(provider)
    if env_vars is None:
        pytest.skip(f"No connectivity check implemented for provider '{provider}'.")

    api_key = _get_secret(env_vars)
    if not api_key:
        pytest.skip(f"No API key for provider '{provider}' (checked {', '.join(env_vars)}).")

    if provider == "google":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
        headers = {"x-goog-api-key": api_key, "content-type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": "Ping. Respond with 'Pong'."}]}],
            "generationConfig": {"maxOutputTokens": 10},
        }
        expected_key = "candidates"
    elif provider == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model_id,
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Ping. Respond with 'Pong'."}],
        }
        expected_key = "content"
    else:  # openai
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
        payload = {
            "model": model_id,
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Ping. Respond with 'Pong'."}],
        }
        expected_key = "choices"

    req = urllib.request.Request(url, method="POST")
    for header, value in headers.items():
        req.add_header(header, value)
    data = json.dumps(payload).encode("utf-8")

    try:
        with urllib.request.urlopen(req, data=data, timeout=30) as response:
            assert response.status == 200
            response_body = json.loads(response.read().decode("utf-8"))
            assert expected_key in response_body, (
                f"Unexpected {provider} response shape (missing '{expected_key}'): {response_body}"
            )
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        if e.code in (401, 403):
            pytest.fail(f"{provider} API authentication failed ({e.code}): invalid API key. Response: {error_body}")
        pytest.fail(f"{provider} API returned {e.code}: {error_body}")
    except urllib.error.URLError as e:
        pytest.fail(f"Could not reach {provider} API: {e.reason}")


def test_python_env_is_isolated():
    """Verify that Python execution is isolated to the project-local `.venv/`."""
    executable = sys.executable.replace("\\", "/").lower()

    assert "/.venv/" in executable, (
        f"Python interpreter '{sys.executable}' is not running inside the local '.venv' virtual environment."
    )


def test_logs_directory_writable():
    """Verify that the telemetry log directories exist and are writable."""
    log_dirs = ["logs", "logs/archive"]
    timestamp = time.strftime("%y%m%d_%H%M%S")
    for d in log_dirs:
        assert os.path.exists(d), f"Directory '{d}' does not exist."
        test_file = os.path.join(d, f"temp_perm_test_{timestamp}.tmp")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except OSError as e:
            pytest.fail(f"Directory '{d}' is not writable. Error: {e}")


def test_adr_ledger_consistency():
    """Verify every ADR file is linked from the decision register.

    For each ``docs/ADR/NNNN-*.md`` file, the register must contain a markdown
    link whose target resolves to exactly that filename (a bare mention of the
    ID number is not enough).
    """
    register_path = "docs/ADR/ADR_decision_register.md"
    adr_dir = "docs/ADR"

    if not os.path.exists(register_path) or not os.path.exists(adr_dir):
        pytest.skip("docs/ADR ledger not present in this project.")

    with open(register_path, encoding="utf-8") as f:
        register_content = f.read()

    # Collect the targets of all markdown links in the register, normalized to
    # bare filenames (strips optional './' prefixes and '#fragment' suffixes).
    link_targets = set()
    for target in re.findall(r"\]\(([^)\s]+)\)", register_content):
        target = target.split("#", 1)[0]
        if target.startswith("./"):
            target = target[2:]
        link_targets.add(os.path.basename(target))

    adr_files = sorted(f for f in os.listdir(adr_dir) if re.match(r"^\d{4}-.*\.md$", f))

    for adr_file in adr_files:
        assert adr_file in link_targets, (
            f"ADR file '{adr_file}' has no markdown link targeting it in '{register_path}'."
        )


def test_no_template_placeholders():
    """Ensure there are no un-cleansed NEON dev stack template references.

    Checks project-context.md and config.yaml for placeholders that
    `bootstrap_project.ps1` should have cleansed. Automatically skipped when
    running inside the master template itself.
    """
    project_root = os.path.basename(os.getcwd())
    if project_root == "_NEON dev stack":
        pytest.skip("Running inside the pristine template repository; cleansing not expected.")

    files_to_check = {
        "_bmad-output/project-context.md": [
            "_NEON dev stack",
            "_NEON%20dev%20stack",
            "project_production.sqlite",
            "[Insert Git Remote URL here]",
        ],
        "config.yaml": [
            "project_production.sqlite",
        ],
    }

    for filepath, placeholders in files_to_check.items():
        if not os.path.exists(filepath):
            continue

        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        for placeholder in placeholders:
            assert placeholder not in content, (
                f"Cleansing failed: Found template placeholder '{placeholder}' in '{filepath}'."
            )


# ---------------------------------------------------------------------------
# bootstrap_project.ps1 name derivation
#
# The project name is NEVER prompted for: it is the destination folder's leaf
# name. Two sanitized forms come off it, and the GitHub repo name must use
# hyphens -- GitHub forbids spaces, and the fleet's repos are hyphenated
# (this template is 'phil-neon/_NEON-dev-stack', not '_NEON_dev_stack').
#
# These tests execute the REAL derivation line out of bootstrap_project.ps1
# rather than reimplementing the regex in Python, so the test cannot silently
# drift away from the script it is guarding.
# ---------------------------------------------------------------------------

BOOTSTRAP = "bootstrap_project.ps1"


def _bootstrap_text() -> str:
    """Read bootstrap_project.ps1, skipping when absent.

    The bootstrapper is template-ONLY: robocopy excludes it (/XF) from every clone.
    An unguarded open() here therefore ships a guaranteed FileNotFoundError to every
    project created from this template -- caught by Phil's 260728 bootstrap test.
    """
    if not os.path.exists(BOOTSTRAP):
        pytest.skip(f"{BOOTSTRAP} is template-only and not present in child projects")
    with open(BOOTSTRAP, encoding="utf-8") as f:
        return f.read()


def _derivation_line(var: str) -> str:
    """Pull the single assignment line for `var` out of the bootstrap script."""
    for line in _bootstrap_text().splitlines():
        if line.strip().startswith(f"${var} ="):
            return line.strip()
    raise AssertionError(f"no '${var} =' assignment found in {BOOTSTRAP}")


def _run_derivation(var: str, project_name: str) -> str:
    import subprocess

    script = f"$ProjectName = $env:TEST_PROJECT_NAME\n{_derivation_line(var)}\nWrite-Output ${var}"
    out = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "TEST_PROJECT_NAME": project_name},
    )
    assert out.returncode == 0, f"powershell failed: {out.stderr}"
    return out.stdout.strip()


win_only = pytest.mark.skipif(sys.platform != "win32", reason="PowerShell derivation is Windows-only")


@win_only
@pytest.mark.parametrize(
    ("folder", "expected_repo"),
    [
        ("_NEON dev stack", "_NEON-dev-stack"),          # must match the real remote
        ("Horse racing tips", "Horse-racing-tips"),
        ("NEON PowerPoint creator", "NEON-PowerPoint-creator"),
        ("NEON Vision AI (platform)", "NEON-Vision-AI-platform"),  # no '__' or trailing '_'
        ("Expert tippers", "Expert-tippers"),
        ("already-hyphenated", "already-hyphenated"),
        ("Trailing punctuation!!!", "Trailing-punctuation"),
    ],
)
def test_repo_name_is_the_hyphenated_folder_name(folder: str, expected_repo: str) -> None:
    assert _run_derivation("RepoName", folder) == expected_repo


@win_only
def test_repo_name_matches_this_repos_actual_remote() -> None:
    """The template must derive its OWN repo name correctly, or the convention is wrong."""
    import subprocess

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"], capture_output=True, text=True, timeout=60
    ).stdout.strip()
    if not remote:
        pytest.skip("no origin remote configured")
    actual = remote.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    assert _run_derivation("RepoName", "_NEON dev stack") == actual


@win_only
def test_identifier_form_stays_underscored_for_filenames() -> None:
    """SafeProjectName feeds the production DB filename; '_' is right there, '-' is not."""
    assert _run_derivation("SafeProjectName", "Horse racing tips") == "Horse_racing_tips"


def test_bootstrap_never_prompts_for_a_project_name() -> None:
    """The folder name is the single source of truth -- asking creates a way to disagree."""
    if not os.path.exists(BOOTSTRAP):
        pytest.skip(f"{BOOTSTRAP} is template-only and not present in child projects")
    content = _bootstrap_text()
    prompts = re.findall(r"Read-Host[^\r\n]*", content)
    offenders = [p for p in prompts if re.search(r"project\s*name|call this project", p, re.I)]
    assert not offenders, f"bootstrap must not prompt for a project name: {offenders}"
    assert "$ProjectName = Split-Path -Path $DestinationPath -Leaf" in content


@win_only
def test_bootstrap_accepts_an_existing_empty_directory() -> None:
    """The 'I made the folder and I'm standing in it' workflow must not be refused.

    Requiring the script to CREATE the directory forces the caller to invent a name to
    type -- which is the exact prompt this design removes. An empty directory is not a
    merge. Verified by reading the guard, not by running a full 10-minute bootstrap.
    """
    content = _bootstrap_text()
    assert "$existing.Count -eq 0" in content, "no empty-directory fast path in the destination guard"
    # The NonInteractive refusal must be reachable only for a NON-empty directory.
    guard = content[content.index("# 4. Create Target Directory"):]
    guard = guard[: guard.index("try {")]
    empty_at = guard.index("$existing.Count -eq 0")
    refuse_at = guard.index("$NonInteractive")
    assert empty_at < refuse_at, "the empty-directory case must be tested BEFORE the refusal"


@win_only
def test_bootstrap_still_refuses_a_non_empty_directory() -> None:
    """A non-empty destination is a real merge and must never be silently overwritten."""
    content = _bootstrap_text()
    assert "is NOT empty" in content
    assert "Merging requires interactive confirmation" in content


@win_only
def test_rollback_never_deletes_a_directory_we_did_not_create() -> None:
    """$createdDir gates the rollback; bootstrapping into the user's own folder must not
    make that folder a deletion candidate if a later step fails."""
    content = _bootstrap_text()
    guard = content[content.index("# 4. Create Target Directory"):]
    guard = guard[: guard.index("try {")]
    # The only assignment of $createdDir = $true is in the branch that actually creates it.
    assert guard.count("$createdDir = $true") == 1
    created_at = guard.index("$createdDir = $true")
    newitem_at = guard.index("New-Item -ItemType Directory -Path $DestinationPath")
    assert newitem_at < created_at, "$createdDir must only be set where the directory is created"


@win_only
def test_bootstrap_filters_memory_by_inheritance() -> None:
    """A clone gets operating knowledge, not the template's provenance (AGENTS 7).

    Fail CLOSED matters here: the survivor test must be an explicit `inherit: true`,
    not merely "the field is present". A page that says nothing must be dropped.
    """
    content = _bootstrap_text()
    # Compared with backslashes stripped from both sides, so this asserts the SHAPE of
    # the guard (anchored, explicit `true`) without becoming an escaping puzzle itself.
    flat = content.replace(chr(92), "")
    assert "-match '(?m)^s*inherit:s*trueb'" in flat, (
        "memory filter is not fail-closed on an explicit, anchored `inherit: true`"
    )
    assert "dropped (template provenance)" in content


@win_only
def test_bootstrap_rebuilds_the_memory_index() -> None:
    """A stale MEMORY.md is the first thing memory_lint flags, and it is read first."""
    content = _bootstrap_text()
    assert "MEMORY.md" in content and "index rebuilt" in content


@win_only
def test_bootstrap_stubs_the_planning_artifacts() -> None:
    """ARCHITECTURE.md is the map an agent reads to orient itself (AGENTS 5.8); shipping
    the template's map points every new project at the wrong system."""
    content = _bootstrap_text()
    for artifact in ("ARCHITECTURE.md", "product-brief.md", "API-SPEC.md"):
        assert artifact in content, f"{artifact} is not reset for clones"
    assert "NOT YET WRITTEN" in content
    assert "last_reviewed" in content, "the stub map must carry last_reviewed or architecture-map lint fails"


def test_every_memory_page_is_classified_for_inheritance() -> None:
    """Belt and braces alongside the governance check: no page may be unclassified."""
    import glob

    pages = [p for p in glob.glob("docs/memory/*.md") if not p.endswith("MEMORY.md")]
    assert pages, "no memory pages found"
    unclassified = []
    for path in pages:
        with open(path, encoding="utf-8") as f:
            parts = f.read().split("---")
        front = parts[1] if len(parts) >= 3 else ""
        if not re.search(r"^\s*inherit:\s*(true|false)\s*(#.*)?$", front, re.M):
            unclassified.append(path)
    assert not unclassified, f"memory pages missing metadata.inherit: {unclassified}"
