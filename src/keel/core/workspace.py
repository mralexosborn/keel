"""Workspace management — project CRUD, active project tracking."""

from __future__ import annotations

from pathlib import Path

from keel.errors import KeelError, StateError

# Repo root — the directory containing pyproject.toml
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def keel_dir() -> Path:
    """Return the keel home directory, creating it if needed."""
    d = _REPO_ROOT
    d.mkdir(exist_ok=True)
    return d


def projects_dir() -> Path:
    d = keel_dir() / "projects"
    d.mkdir(exist_ok=True)
    return d


def archive_dir() -> Path:
    d = keel_dir() / "archive"
    d.mkdir(exist_ok=True)
    return d


def project_path(slug: str) -> Path:
    return projects_dir() / slug


def get_active_project() -> str | None:
    """Return the active project slug, or None."""
    active_file = keel_dir() / ".active"
    if active_file.exists():
        slug = active_file.read_text().strip()
        if slug and project_path(slug).exists():
            return slug
    return None


def set_active_project(slug: str) -> None:
    """Set the active project."""
    p = project_path(slug)
    if not p.exists():
        raise StateError(f"Project '{slug}' does not exist.")
    active_file = keel_dir() / ".active"
    active_file.write_text(slug)


def require_active_project(explicit_slug: str | None = None) -> str:
    """Return the project slug to operate on, raising if none is available."""
    if explicit_slug:
        p = project_path(explicit_slug)
        if not p.exists():
            raise StateError(f"Project '{explicit_slug}' does not exist.")
        return explicit_slug
    slug = get_active_project()
    if not slug:
        raise KeelError(
            "No active project. Run 'keel new <topic>' or 'keel set <slug>'."
        )
    return slug


def create_project(slug: str, topic: str) -> Path:
    """Create a new project directory with subdirectories."""
    p = project_path(slug)
    if p.exists():
        raise KeelError(f"Project '{slug}' already exists.")
    p.mkdir(parents=True)
    (p / "sources").mkdir()
    (p / "extracts").mkdir()
    set_active_project(slug)
    return p


def list_projects() -> list[dict[str, str]]:
    """List all projects with their slugs and paths."""
    pdir = projects_dir()
    results = []
    for d in sorted(pdir.iterdir()):
        if d.is_dir():
            results.append({"slug": d.name, "path": str(d)})
    return results


def archive_project(slug: str) -> Path:
    """Move a project to the archive directory."""
    src = project_path(slug)
    if not src.exists():
        raise StateError(f"Project '{slug}' does not exist.")
    dest = archive_dir() / slug
    if dest.exists():
        raise KeelError(f"Archived project '{slug}' already exists.")
    src.rename(dest)

    # Clear active if this was the active project
    if get_active_project() == slug:
        active_file = keel_dir() / ".active"
        active_file.unlink(missing_ok=True)

    return dest
