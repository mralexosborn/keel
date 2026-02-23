"""keel digest — Stage 2 content extraction and synthesis orchestrator."""

from __future__ import annotations

import os
from pathlib import Path

import click

from keel.cli import KeelContext, pass_ctx
from keel.core.claude import invoke_claude, invoke_claude_with_files
from keel.core.config import get_model
from keel.core.state import (
    can_run_stage,
    complete_stage,
    is_stage_complete,
    prepare_rerun,
    read_state,
)
from keel.core.workspace import project_path, require_active_project
from keel.formatters.digest_output import parse_extract_frontmatter, render_digest_header
from keel.processors.pdf import extract_pdf_text
from keel.prompts.digest_prompts import (
    extraction_prompt,
    synthesis_prompt_file_reading,
    synthesis_prompt_inline,
)
from keel.utils.console import error, info, stage_header, success, warn

# If combined extract content exceeds this, use file-reading mode
INLINE_THRESHOLD = 100_000


@click.command()
@pass_ctx
def digest(ctx: KeelContext) -> None:
    """Stage 2: Extract PDFs and synthesize across sources."""
    slug = require_active_project(ctx.project_slug)
    pdir = project_path(slug)
    state = read_state(pdir)

    # Check stage progression
    if is_stage_complete(state, "digest"):
        if not click.confirm("02-digest.md already exists. Overwrite?"):
            return
        state = prepare_rerun(pdir, state, "digest")
    else:
        ok, reason = can_run_stage(state, "digest")
        if not ok:
            raise click.ClickException(reason)

    topic = state.get("topic", slug)
    stage_header("Stage 2", f"Content Extraction & Synthesis: {topic}")

    # Check for PDFs
    sources_dir = pdir / "sources"
    pdfs = sorted(sources_dir.glob("*.pdf"))
    if not pdfs:
        raise click.ClickException(
            "No PDFs found in sources/. "
            "Add PDFs from your scan results, then run again."
        )

    info(f"Found {len(pdfs)} PDFs to process")
    notes = _load_notes(pdir, ctx.context_file)

    # Step 1: Extract each PDF
    extract_model = get_model(ctx.config, "digest_extract")
    extracts_dir = pdir / "extracts"
    extracts_dir.mkdir(exist_ok=True)

    extracted_files: list[Path] = []

    for pdf in pdfs:
        stem = pdf.stem
        extract_path = extracts_dir / f"{stem}.md"

        # Skip if extract already exists (unless --no-cache)
        if extract_path.exists() and not ctx.no_cache:
            info(f"Using cached extract: {stem}")
            extracted_files.append(extract_path)
            continue

        info(f"Extracting: {pdf.name}...")

        # Extract text from PDF
        text = extract_pdf_text(pdf)
        if text is None:
            warn(f"Skipping {pdf.name} — no text could be extracted.")
            continue

        # Send to Claude for structured extraction
        prompt = extraction_prompt(text)
        try:
            result = invoke_claude(
                prompt, pdir, verbose=ctx.verbose, model=extract_model
            )
            extract_path.write_text(result)
            extracted_files.append(extract_path)
            success(f"Extracted: {stem}")
        except Exception as exc:
            warn(f"Extraction failed for {pdf.name}: {exc}")

    if not extracted_files:
        error("No PDFs were successfully extracted.")
        return

    # Step 2: Synthesize across all extracts
    info("Synthesizing across all sources...")
    synthesis_model = get_model(ctx.config, "digest_synthesis")

    # Decide inline vs file-reading based on total size
    total_size = sum(f.stat().st_size for f in extracted_files)

    if total_size <= INLINE_THRESHOLD:
        # Inline mode — include content in prompt
        extract_contents = {}
        for f in extracted_files:
            extract_contents[f.stem] = f.read_text()

        prompt = synthesis_prompt_inline(topic, extract_contents, notes)
        synthesis_output = invoke_claude(
            prompt, pdir, verbose=ctx.verbose, model=synthesis_model
        )
    else:
        # File-reading mode — let Claude read from disk
        info("Large source set — using file-reading mode for synthesis")
        filenames = [f.name for f in extracted_files]
        prompt = synthesis_prompt_file_reading(topic, filenames, notes)
        synthesis_output = invoke_claude_with_files(
            prompt, pdir, verbose=ctx.verbose, model=synthesis_model
        )

    # Step 3: Build output
    extract_metadata = [parse_extract_frontmatter(f) for f in extracted_files]
    header = render_digest_header(topic, len(extracted_files), extract_metadata)

    output = f"{header}\n{synthesis_output}\n"
    output_path = pdir / "02-digest.md"
    output_path.write_text(output)

    state = complete_stage(pdir, state, "digest")
    success(f"Digest complete: {output_path}")
    info("Next: Run 'keel thesis' to generate thesis candidates.")

    if ctx.edit:
        editor = os.environ.get("EDITOR", "vi")
        click.edit(filename=str(output_path), editor=editor)


def _load_notes(project_dir: Path, context_file: str | None) -> str | None:
    if context_file:
        cf = Path(context_file)
        if cf.exists():
            return cf.read_text()
    notes_path = project_dir / "notes.md"
    if notes_path.exists():
        return notes_path.read_text()
    return None
