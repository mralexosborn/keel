"""Prompts for Stage 2: Content Extraction & Synthesis."""

from __future__ import annotations


def extraction_prompt(pdf_text: str) -> str:
    """Generate the per-PDF content extraction prompt."""
    return f"""Extract and structure the content of this article. Produce a markdown file with:
- A YAML frontmatter block containing: title, author(s), publication/source, date published (best guess if not explicit), URL (if present in the document), and a one-sentence summary.
- The full article content cleaned up into readable markdown (preserve structure, headings, emphasis — but remove navigation, ads, footers, and other non-content elements).
- A "Key Claims" section at the end listing the 3-5 most important factual claims or arguments made in the piece, each as a single sentence.

Here is the extracted text:

{pdf_text}"""


def synthesis_prompt_inline(
    topic: str,
    extract_contents: dict[str, str],
    notes: str | None = None,
) -> str:
    """Generate the cross-source synthesis prompt with extract content inlined."""
    notes_block = ""
    if notes:
        notes_block = (
            f"\n\nThe author has provided these initial notes and context:\n{notes}\n"
        )

    extracts_block = ""
    for filename, content in extract_contents.items():
        extracts_block += f"\n\n--- Source: {filename} ---\n{content}"

    return f"""You have {len(extract_contents)} source articles on the topic "{topic}."{notes_block}

Here are the extracted sources:{extracts_block}

Based on these sources, produce:
1. A 2-3 paragraph summary of the current discourse — what's being said, by whom, and what framing dominates.
2. Identified gaps: 3-5 angles, questions, or framings that are NOT well-represented in these sources but would be interesting or important to explore.
3. Points of disagreement or tension between sources.

Reference sources by their filename (without extension) for traceability."""


def synthesis_prompt_file_reading(
    topic: str,
    extract_filenames: list[str],
    notes: str | None = None,
) -> str:
    """Generate the synthesis prompt that instructs Claude to read files from disk."""
    notes_block = ""
    if notes:
        notes_block = (
            f"\n\nThe author has provided these initial notes and context:\n{notes}\n"
        )

    files_list = "\n".join(f"- extracts/{f}" for f in extract_filenames)

    return f"""You have {len(extract_filenames)} source articles on the topic "{topic}."{notes_block}

Read the following extract files from the extracts/ directory:
{files_list}

Based on these sources, produce:
1. A 2-3 paragraph summary of the current discourse — what's being said, by whom, and what framing dominates.
2. Identified gaps: 3-5 angles, questions, or framings that are NOT well-represented in these sources but would be interesting or important to explore.
3. Points of disagreement or tension between sources.

Reference sources by their filename (without extension) for traceability."""
