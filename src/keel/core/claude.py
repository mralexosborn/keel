"""Claude Code subprocess wrapper."""

from __future__ import annotations

import subprocess
from pathlib import Path

from keel.errors import ClaudeError
from keel.utils.console import info


def invoke_claude(
    prompt: str,
    project_dir: str | Path,
    *,
    verbose: bool = False,
    model: str = "opus",
    timeout: int = 600,
) -> str:
    """Invoke Claude Code with a prompt piped via stdin.

    Returns the stdout output on success.
    Raises ClaudeError on non-zero exit or timeout.
    """
    cmd = ["claude", "--print", "--model", model]

    if verbose:
        info(f"Invoking Claude Code ({model})...")
        info(f"Prompt length: {len(prompt):,} chars")

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=timeout,
        )
    except FileNotFoundError:
        raise ClaudeError(
            "Claude Code CLI not found. Install it and ensure 'claude' is on PATH."
        )
    except subprocess.TimeoutExpired:
        raise ClaudeError(
            f"Claude Code timed out after {timeout}s. "
            "Try running the stage again or increase the timeout."
        )

    if verbose and result.stderr:
        info(f"stderr: {result.stderr[:500]}")

    if result.returncode != 0:
        raise ClaudeError(
            f"Claude Code exited with code {result.returncode}.\n"
            f"stderr: {result.stderr[:500]}\n"
            f"stdout (partial): {result.stdout[:500]}"
        )

    return result.stdout


def invoke_claude_with_files(
    prompt: str,
    project_dir: str | Path,
    *,
    verbose: bool = False,
    model: str = "opus",
    timeout: int = 600,
) -> str:
    """Invoke Claude Code, instructing it to read files from the project directory.

    Use this when context is too large to inline in the prompt.
    """
    file_aware_prompt = (
        "Your working directory is the project folder. "
        "You can read any files referenced below using their relative paths.\n\n"
        f"{prompt}"
    )
    return invoke_claude(
        file_aware_prompt,
        project_dir,
        verbose=verbose,
        model=model,
        timeout=timeout,
    )
