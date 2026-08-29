"""Project-scoped filesystem locations.

The point of this module is that **the OS default temp directory is never the
right answer** for generated output, and the machine-level `TEMP`/`TMP` redirect
that bootstrap_project.ps1 configures is a mitigation, not a guarantee.

See AGENTS 5.5.1.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

#: Repo root: backend/core/paths.py -> core -> backend -> root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def project_temp_dir(prefix: str = "") -> Path:
    """The project's own scratch root -- NEVER the OS default temp (usually C:).

    `tempfile.mkdtemp()` / `TemporaryDirectory()` with no `dir=` resolve via the
    `TEMP`/`TMP` environment variables. bootstrap_project.ps1 redirects those off
    the boot drive at machine level, but that **only helps processes that inherit
    the redirected environment**. A scheduled task, a Windows service, a fresh
    machine before bootstrap has run, or a long-running shell started before the
    redirect will all silently fall back to the boot drive -- and "silently" is the
    problem: the code works, the disk fills, and nothing connects the two.

    Passing this as `dir=` makes the location correct regardless of environment.

    Callers still own cleanup; this only decides WHERE. Prefer
    `TemporaryDirectory(dir=project_temp_dir())`, which cleans up on exit, over
    `mkdtemp(dir=...)`, which does not.

    Returns a directory under a git-ignored path, so scratch output can never be
    committed by accident.
    """
    root = PROJECT_ROOT / ".data" / "tmp"
    if prefix:
        root = root / prefix
    root.mkdir(parents=True, exist_ok=True)
    return root


def temp_dir_for_embedded_script(script_template: str, token: str) -> tuple[str, str]:
    """Substitute a caller-owned temp path into a script destined for ANOTHER interpreter.

    THE PROBLEM THIS SOLVES. Code that builds a script as a STRING and hands it to
    a different interpreter (a 3D renderer, node, a notebook kernel, any subprocess
    runner) frequently has the embedded script call `mkdtemp()` itself. That
    directory is then unreachable: `mkdtemp` has no auto-cleanup, the outer process
    never learns the path, and nothing is in scope to delete it. One project
    accumulated **141** orphaned directories exactly this way.

    THE FIX. The CALLER creates the directory -- inside a `TemporaryDirectory()` it
    already owns, so cleanup is guaranteed -- and substitutes the path into the
    script text via a sentinel token::

        _PROBE_OUT = "__PROJECT_PROBE_OUT__"
        TEMPLATE = "tmp_dir = r'__PROJECT_PROBE_OUT__'\\n..."

        with tempfile.TemporaryDirectory(dir=project_temp_dir()) as tmp:
            body, _ = temp_dir_for_embedded_script(TEMPLATE, _PROBE_OUT)
            script_path.write_text(body.replace(_PROBE_OUT, Path(tmp).as_posix()),
                                   encoding="utf-8")

    Use a TOKEN rather than an f-string or `.format()`: embedded scripts are full
    of braces and both will bite you.

    Returns `(script_template, token)` unchanged -- this function exists to make
    the pattern discoverable and to hold its rationale where a future author will
    trip over it. Verify by COUNTING: record the directory count in your temp roots
    before and after a full run of the affected code; it must not change.
    """
    if token not in script_template:
        raise ValueError(
            f"sentinel token {token!r} not found in the script template; the "
            "substitution would silently no-op and the embedded script would fall "
            "back to its own mkdtemp() -- the exact leak this pattern prevents"
        )
    return script_template, token


def new_temp_dir(prefix: str = "") -> tempfile.TemporaryDirectory[str]:
    """A self-cleaning temp directory under the project's own scratch root.

    Convenience wrapper so the correct call is shorter than the incorrect one::

        with new_temp_dir("render") as tmp:
            ...
    """
    return tempfile.TemporaryDirectory(dir=project_temp_dir(prefix))
