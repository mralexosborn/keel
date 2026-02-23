""".state YAML management — stage ordering, progression, re-run with .bak backups."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from keel.errors import StateError

STAGES = ["scan", "digest", "thesis", "research"]
STAGE_OUTPUTS = {
    "scan": "scan-1.md",
    "digest": "02-digest.md",
    "thesis": "03-thesis.md",
    "research": "04-research.md",
}


def _blank_state(topic: str) -> dict[str, Any]:
    return {
        "topic": topic,
        "created": datetime.now(timezone.utc).isoformat(),
        "active_stage": "scan",
        "scan_count": 0,
        "stages": {
            stage: {"completed_at": None, "output": STAGE_OUTPUTS[stage]}
            for stage in STAGES
        },
    }


def _state_path(project_dir: Path) -> Path:
    return project_dir / ".state"


def init_state(project_dir: Path, topic: str) -> dict[str, Any]:
    """Create a fresh .state file for a new project."""
    state = _blank_state(topic)
    write_state(project_dir, state)
    return state


def read_state(project_dir: Path) -> dict[str, Any]:
    """Read and return the project state."""
    sp = _state_path(project_dir)
    if not sp.exists():
        raise StateError(f"No .state file in {project_dir}. Is this a keel project?")
    try:
        with open(sp) as f:
            state = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise StateError(f"Corrupt .state file: {exc}")
    if not isinstance(state, dict):
        raise StateError("Corrupt .state file: not a valid YAML mapping.")
    return state


def write_state(project_dir: Path, state: dict[str, Any]) -> None:
    """Atomically write state to the .state file."""
    sp = _state_path(project_dir)
    tmp = sp.with_suffix(".tmp")
    with open(tmp, "w") as f:
        yaml.dump(state, f, default_flow_style=False, sort_keys=False)
    os.replace(tmp, sp)


def next_scan_number(state: dict[str, Any]) -> int:
    """Increment scan_count and return the new scan number."""
    n = state.get("scan_count", 0) + 1
    state["scan_count"] = n
    return n


def get_active_stage(state: dict[str, Any]) -> str:
    """Return the current active stage name."""
    return state.get("active_stage", "scan")


def is_stage_complete(state: dict[str, Any], stage: str) -> bool:
    """Check if a stage has been completed."""
    stages = state.get("stages", {})
    stage_data = stages.get(stage, {})
    return stage_data.get("completed_at") is not None


def can_run_stage(state: dict[str, Any], stage: str) -> tuple[bool, str]:
    """Check if a stage can be run. Returns (ok, reason)."""
    if stage not in STAGES:
        return False, f"Unknown stage: {stage}"

    idx = STAGES.index(stage)

    # Check all prior stages are complete
    for prior in STAGES[:idx]:
        if not is_stage_complete(state, prior):
            return False, f"Stage '{prior}' must be completed first. Run 'keel {prior}'."

    return True, ""


def complete_stage(
    project_dir: Path, state: dict[str, Any], stage: str, *, output: str | None = None
) -> dict[str, Any]:
    """Mark a stage as complete and advance active_stage."""
    state["stages"][stage]["completed_at"] = datetime.now(timezone.utc).isoformat()
    if output is not None:
        state["stages"][stage]["output"] = output

    idx = STAGES.index(stage)
    if idx + 1 < len(STAGES):
        state["active_stage"] = STAGES[idx + 1]
    else:
        state["active_stage"] = "complete"

    write_state(project_dir, state)
    return state


def prepare_rerun(project_dir: Path, state: dict[str, Any], stage: str) -> dict[str, Any]:
    """Prepare for re-running a completed stage: backup outputs and reset downstream."""
    idx = STAGES.index(stage)

    # Backup and reset this stage and all downstream stages
    for s in STAGES[idx:]:
        # Scan keeps all versions — no backup needed
        if s != "scan":
            output_file = project_dir / state["stages"][s].get("output", STAGE_OUTPUTS[s])
            if output_file.exists():
                bak = output_file.with_suffix(".md.bak")
                shutil.copy2(output_file, bak)
        state["stages"][s]["completed_at"] = None

    state["active_stage"] = stage
    write_state(project_dir, state)
    return state


def next_action(state: dict[str, Any]) -> str:
    """Return a human-readable description of what to do next."""
    active = get_active_stage(state)
    if active == "complete":
        return "All stages complete."
    if active == "scan":
        return "Run 'keel scan' to discover sources."
    if active == "digest":
        return "Add PDFs to sources/, then run 'keel digest'."
    if active == "thesis":
        return "Run 'keel thesis' to generate thesis candidates."
    if active == "research":
        return "Select a thesis in 03-thesis.md, then run 'keel research'."
    return f"Run 'keel {active}'."
