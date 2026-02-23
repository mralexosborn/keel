# Keel — Research Pipeline CLI

## Product Requirements Document

### Overview

`keel` is a local Python CLI that compresses the research-to-draft pipeline for long-form analytical writing. It moves a topic through four stages — source discovery, content extraction, thesis generation, and deep research — producing structured markdown artifacts at each stage. Every stage is human-in-the-loop: the user reviews, curates, and edits output before advancing.

The tool delegates analytical heavy lifting to Claude Code (invoked as a subprocess), while orchestrating data collection, source management, and file I/O itself.

### Target User

Solo author writing long-form analytical pieces — newsletter essays, policy briefs, research reports. Pieces typically take 10-15 hours from topic selection to publishable draft; the goal is to compress this to 3-5 hours by automating source discovery, content extraction, and research synthesis.

---

## Architecture

### System Design

```
User → keel CLI (Python)
              │
              ├── Source Fetcher (RSS + Web Search)
              │     ├── RSS parser (feedparser)
              │     └── Web search API (Brave Search)
              │
              ├── PDF Extractor
              │     └── Extracts text + metadata from user-curated PDFs
              │
              ├── Claude Code (subprocess)
              │     └── Invoked via `claude` CLI for synthesis tasks
              │
              └── File System (workspace)
                    └── ~/.keel/
                          ├── config.yaml
                          ├── archive/
                          │     └── {past-project-slug}/
                          └── projects/
                                └── {project-slug}/
                                      ├── .state             # tracks completed stages
                                      ├── notes.md           # optional user seed context
                                      ├── 01-scan.md
                                      ├── sources/           # user drops PDFs here
                                      │     ├── article1.pdf
                                      │     └── article2.pdf
                                      ├── extracts/          # generated markdown per source
                                      │     ├── article1.md
                                      │     └── article2.md
                                      ├── 02-digest.md
                                      ├── 03-thesis.md
                                      └── 04-research.md
```

### Key Design Decisions

- **Claude Code as subprocess, not API.** Invoke `claude` CLI with prompts piped via stdin. This gives full reasoning capability including tool use without managing API auth, token counting, or conversation state. The tradeoff is slower execution and less programmatic control.
- **Markdown as interchange format.** Every stage produces a markdown file the user can edit in any editor. Composable and inspectable.
- **Project-based workspace.** Each research topic gets a directory with all artifacts, cached sources, and metadata. Supports resuming work across sessions.
- **Human curation at the source level.** The tool finds sources; the user decides which are worth reading. PDFs are the ingestion format because they sidestep paywall issues and give the user full control over what enters the pipeline.

---

## State Management

Each project tracks its stage progression in a `.state` file:

```yaml
topic: "Vietnamese shipyard capacity expansion"
created: "2025-06-15T10:30:00Z"
active_stage: "scan"  # scan | digest | thesis | research | complete
stages:
  scan:
    completed_at: null
    output: "01-scan.md"
  digest:
    completed_at: null
    output: "02-digest.md"
  thesis:
    completed_at: null
    output: "03-thesis.md"
  research:
    completed_at: null
    output: "04-research.md"
```

### Stage Progression Rules

- Stages must be completed in order: scan → digest → thesis → research.
- Running a stage out of order prints an error with the next required stage.
- Re-running a completed stage prompts for confirmation: "01-scan.md already exists. Overwrite? [y/N]". On overwrite, all downstream stages are marked incomplete (their output files are preserved with a `.bak` suffix, not deleted).
- `keel status` shows current state and what to do next.

---

## CLI Interface

### Commands

```bash
# Initialize a new research project
keel new "Vietnamese shipyard capacity expansion"
# Creates project directory, runs scan automatically

# Core pipeline
keel scan                  # Stage 1: Source discovery → ranked URL table
keel digest                # Stage 2: Extract PDFs → per-source markdown + synthesis
keel thesis                # Stage 3: Thesis generation from digest
keel research              # Stage 4: Deep research on selected thesis

# Utilities
keel status                # Show current project, stage, and next action
keel sources               # List/manage the curated source list
keel sources add <url>     # Add an RSS feed or trusted domain
keel sources remove <url>
keel archive               # Move current project to archive
keel list                  # List all active projects
keel set <project-slug>    # Switch active project
keel index                 # Index past articles for thesis differentiation (see Archive section)
```

### Flags (global)

```
--project, -p <slug>      # Operate on a specific project (default: active project)
--verbose, -v             # Show Claude Code invocations and raw output
--no-cache                # Force re-fetch of sources (ignore cached content)
--edit                    # Open output file in $EDITOR after stage completes
--context <file>          # Load additional seed context (alternative to notes.md)
```

### User Seed Context

Sometimes the user already has a half-formed idea, a specific paper, or a Twitter thread they want to start from. Two mechanisms:

1. **`notes.md`** — If present in the project directory, its contents are loaded into every Claude Code invocation as additional context.
2. **`--context <file>`** — One-off context file passed to a specific stage invocation.

Both are optional. When present, they're prepended to the Claude Code prompt with the framing: "The author has provided these initial notes and context for this project."

---

## Stage 1: Source Discovery (`keel scan`)

### Purpose

Given a topic, find what's been published recently and return a ranked table of sources. No synthesis — just discovery. The user manually reviews and curates from here.

### Process

1. **Parse topic** from project metadata.
2. **Generate search queries.** Use Claude Code to expand the topic into 5-8 specific search queries optimized for different angles (trade press, policy analysis, financial data, technical detail, contrarian takes).
   - Claude Code invocation is lightweight here — just query generation, no large context.
3. **Fetch from curated RSS feeds.** Pull recent items (last 90 days) from the source list. First-pass keyword filter against the topic and generated queries to reduce to relevant candidates.
4. **Fetch from web search.** Run generated queries against Brave Search API. Top 10 results per query.
5. **Deduplicate and rank.** Merge RSS and search results, deduplicate by URL. Rank by: source trust tier × recency. No semantic scoring — keep this stage fast and cheap.
6. **Output** to `01-scan.md`.

### Output Format (`01-scan.md`)

```markdown
# Source Discovery: {topic}
Generated: {timestamp}
Queries used: {list of generated search queries}

| # | Title | Source | Date | URL | Trust |
|---|-------|--------|------|-----|-------|
| 1 | {title} | {domain} | {date} | {url} | Tier 1 |
| 2 | {title} | {domain} | {date} | {url} | Tier 2 |
| ... | | | | | |

Sources found: {count}
```

### User Action After Scan

1. Review the table. Open articles that look relevant.
2. Save relevant articles as PDFs into the project's `sources/` directory.
3. Optionally add PDFs from other sources not found by the scan (emailed reports, papers, etc.).
4. Run `keel digest`.

---

## Stage 2: Content Extraction & Synthesis (`keel digest`)

### Purpose

Extract content from user-curated PDFs into structured, citable markdown files. Then synthesize the full collection into a landscape overview.

### Process

1. **Scan `sources/` directory** for PDF files. Error if empty — prompt user to add PDFs first.
2. **Extract content from each PDF.** For each PDF:
   a. Extract raw text using `pymupdf` (PyMuPDF/fitz).
   b. Send extracted text to Claude Code with the prompt:

      > Extract and structure the content of this article. Produce a markdown file with:
      > - A YAML frontmatter block containing: title, author(s), publication/source, date published (best guess if not explicit), URL (if present in the document), and a one-sentence summary.
      > - The full article content cleaned up into readable markdown (preserve structure, headings, emphasis — but remove navigation, ads, footers, and other non-content elements).
      > - A "Key Claims" section at the end listing the 3-5 most important factual claims or arguments made in the piece, each as a single sentence.

   c. Write output to `extracts/{filename-without-extension}.md`.

3. **Synthesize across all extracts.** Load all extract markdown files and send to Claude Code with the prompt:

   > You have {n} source articles on the topic "{topic}."
   >
   > {If notes.md exists: The author has provided these initial notes and context: {notes.md content}}
   >
   > Based on these sources, produce:
   > 1. A 2-3 paragraph summary of the current discourse — what's being said, by whom, and what framing dominates.
   > 2. Identified gaps: 3-5 angles, questions, or framings that are NOT well-represented in these sources but would be interesting or important to explore.
   > 3. Points of disagreement or tension between sources.
   >
   > Reference sources by their filename (without extension) for traceability.

4. **Output** synthesis to `02-digest.md`.

### Extract Output Format (`extracts/{source}.md`)

```markdown
---
title: "The Rise of Vietnamese Shipbuilding"
author: "Jane Smith"
publication: "Lloyd's List"
date: "2025-05-20"
url: "https://lloydslist.com/article/12345"
summary: "Vietnam's shipbuilding capacity has tripled since 2020, driven by state subsidies and overflow demand from congested Korean and Chinese yards."
---

# The Rise of Vietnamese Shipbuilding

{cleaned article content in markdown}

## Key Claims

1. Vietnamese shipyard capacity has tripled since 2020.
2. State subsidies account for roughly 40% of the cost advantage over Korean competitors.
3. Quality control remains a significant concern for complex vessel types.
4. Overflow demand from Korean and Chinese yards is the primary growth driver.
```

### Digest Output Format (`02-digest.md`)

```markdown
# Source Digest: {topic}
Generated: {timestamp}
Sources processed: {count}

## Sources Extracted
| # | File | Title | Author | Publication | Date |
|---|------|-------|--------|-------------|------|
| 1 | article1 | {title} | {author} | {pub} | {date} |
| 2 | article2 | {title} | {author} | {pub} | {date} |

## Discourse Summary
{2-3 paragraph synthesis referencing sources by filename}

## Coverage Gaps
1. **{gap title}** — {explanation}
2. ...

## Points of Tension
1. **{tension}** — {source_a} argues X while {source_b} argues Y.
2. ...
```

### Handling Large Source Sets

If the combined extract content exceeds what can fit in a single Claude Code invocation:
1. Write all extracts to the `extracts/` directory.
2. Invoke Claude Code with `cwd` set to the project directory, instructing it to read the extract files directly from disk (Claude Code can use its file reading capabilities).
3. The prompt should reference the `extracts/` directory rather than inlining all content.

---

## Stage 3: Thesis Generation (`keel thesis`)

### Purpose

Given the digest (and optionally the user's past writing), propose specific thesis candidates.

### Process

1. **Load** `02-digest.md`, all files in `extracts/`, and (if indexed) past article summaries from the archive.
2. **Send to Claude Code** with the prompt:

   > You are helping develop a thesis for a long-form analytical piece on "{topic}."
   >
   > Here is the source digest: {02-digest.md content}
   > The full extracted sources are available in the extracts/ directory.
   >
   > {If notes.md exists: The author's initial notes: {notes.md content}}
   >
   > {If archive index exists: Here are summaries of the author's past pieces: {index content}. Avoid retreading previous arguments. Build on or challenge them where relevant.}
   >
   > Propose 3-5 thesis candidates. For each:
   > - **One-sentence thesis** — a clear, arguable claim (not a topic description)
   > - **Angle** — what makes this non-obvious or contrarian
   > - **Supporting evidence** — 2-3 specific data points or arguments from the sources, cited by source filename
   > - **Strongest counterargument** — the best case against this thesis
   > - **Research needed** — what additional information would be required to write this piece convincingly
   >
   > Rank by: (1) originality relative to existing coverage, (2) strength of available evidence, (3) analytical depth potential.

3. **Output** to `03-thesis.md`.
4. **User action:** Read candidates, mark chosen thesis with `[SELECTED]`, optionally add refinements.

### Output Format (`03-thesis.md`)

```markdown
# Thesis Candidates: {topic}
Generated: {timestamp}
Based on: 02-digest.md

## Thesis 1: {one-sentence thesis}
**Angle:** {what makes this non-obvious}
**Supporting evidence:**
- {evidence 1, citing source filename}
- {evidence 2}
- {evidence 3}
**Strongest counterargument:** {best case against}
**Research needed:** {what you'd need to find or verify}

## Thesis 2: {one-sentence thesis}
...

---
## Selection
Mark your chosen thesis by adding [SELECTED] to its heading.
Add any refinements or notes below:

```

---

## Stage 4: Deep Research (`keel research`)

### Purpose

Given a selected thesis, build a comprehensive research brief with primary sources, data, and structured evidence.

### Process

1. **Load** `03-thesis.md`, extract the `[SELECTED]` thesis and any user notes. Error if no thesis is selected.
2. **Load** all extract files from `extracts/` as existing evidence base.
3. **Generate research plan.** Use Claude Code to decompose the thesis into 4-6 specific research questions.
4. **Execute research.** For each research question, invoke Claude Code with web search enabled to:
   - Find primary sources: government filings, company reports, academic papers, industry data
   - Extract specific data points and statistics
   - Identify expert voices and positions
   - Note contradictory evidence
   - Cross-reference against existing extracts to avoid redundant sourcing
5. **Organize findings** by research question with sources cited inline.
6. **Identify gaps.** Flag 2-3 things the author needs to find independently (interviews, datasets, FOIA-able documents).
7. **Generate outline suggestion.** Section-by-section structure noting which evidence supports each section, referencing both extracts and newly found sources.
8. **Output** to `04-research.md`.

### Output Format (`04-research.md`)

```markdown
# Research Brief: {thesis one-sentence}
Generated: {timestamp}
Based on: 03-thesis.md

## Selected Thesis
{thesis statement with any user refinements}

## Research Questions & Findings

### RQ1: {research question}
{3-5 paragraph synthesis of findings}
**Key sources:**
- [{source title}]({url}) — {what it contributes}
- From extracts: {extract filename} — {relevant finding}
**Key data points:**
- {specific statistic or fact with attribution}
**Contradictory evidence:**
- {anything that challenges the thesis on this point}

### RQ2: {research question}
...

## Gaps & Manual Research Needed
1. **{gap}** — {why this matters and suggested approach}
2. ...

## Suggested Outline
1. **{section title}** — {what this section argues, which RQs and sources it draws from}
2. ...

## Source Bibliography
| # | Title | Author/Org | Date | URL | Type | Used In |
|---|-------|-----------|------|-----|------|---------|
| 1 | ... | ... | ... | ... | Extract / New | RQ1, RQ3 |
```

---

## Archive & Past Article Indexing

### Purpose

Enable thesis differentiation by giving Claude Code awareness of what the author has previously written.

### Indexing (`keel index`)

1. **Scan** the configured `past_articles` directories for markdown files.
2. **For each article,** use Claude Code to generate a structured summary:
   - Title, date, primary topic
   - One-sentence thesis
   - Key arguments made
   - Sources/data cited
3. **Store** summaries in `~/.keel/archive/index.json`.
4. **Incremental:** Only re-index files modified since last index run (tracked by mtime).

### Index Format (`index.json`)

```json
[
  {
    "file": "~/writing/published/korean-shipbuilding.md",
    "title": "Why Korea Still Builds the World's Ships",
    "date": "2025-03-15",
    "topic": "maritime, shipbuilding, industrial policy",
    "thesis": "Korean shipbuilding dominance is a function of state-directed capital allocation, not labor cost advantages.",
    "key_arguments": [
      "KEXIM financing accounts for 60% of newbuild orders",
      "Labor costs are higher than Chinese competitors",
      "Technology moat in LNG carriers is widening"
    ],
    "indexed_at": "2025-06-15T10:00:00Z"
  }
]
```

### Usage in Pipeline

When `index.json` exists and contains entries, the thesis stage includes a condensed version (titles + theses only, to stay within context limits) in its prompt. If the index exceeds ~50 entries, only the 20 most recent + any topically relevant entries (matched by keyword overlap with current topic) are included.

---

## Claude Code Invocation

### Subprocess Pattern

All prompts are piped via stdin to avoid shell argument length limits. Large context (extract files) is read from disk by Claude Code rather than inlined in the prompt.

```python
import subprocess
from pathlib import Path

def invoke_claude(
    prompt: str,
    project_dir: str | Path,
    verbose: bool = False,
    model: str = "opus",
) -> str:
    """Invoke Claude Code with a prompt piped via stdin."""
    cmd = [
        "claude",
        "--print",
        "--model", model,
    ]

    if verbose:
        print(f"[keel] Invoking Claude Code ({model})...")
        print(f"[keel] Prompt length: {len(prompt)} chars")

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        cwd=str(project_dir),
        timeout=600,  # 10 minute timeout per invocation
    )

    if verbose:
        if result.stderr:
            print(f"[keel] stderr: {result.stderr}")

    if result.returncode != 0:
        raise RuntimeError(
            f"Claude Code exited with code {result.returncode}.\n"
            f"stderr: {result.stderr}\n"
            f"stdout (partial): {result.stdout[:500]}"
        )

    return result.stdout


def invoke_claude_with_files(
    prompt: str,
    project_dir: str | Path,
    verbose: bool = False,
    model: str = "opus",
) -> str:
    """Invoke Claude Code, instructing it to read files from the project directory.

    Use this when context is too large to inline in the prompt.
    The prompt should reference relative file paths that Claude Code
    can read using its file reading capabilities.
    """
    file_aware_prompt = (
        f"Your working directory is the project folder. "
        f"You can read any files referenced below using their relative paths.\n\n"
        f"{prompt}"
    )
    return invoke_claude(file_aware_prompt, project_dir, verbose, model)
```

### Model Selection Guidance

| Stage | Recommended Model | Rationale |
|-------|------------------|-----------|
| Scan (query generation) | sonnet | Simple task, speed matters |
| Digest (per-PDF extraction) | sonnet | Structured extraction, high volume |
| Digest (synthesis) | opus | Analytical reasoning across sources |
| Thesis | opus | Creative + analytical reasoning |
| Research | opus | Complex multi-step research |

Configure in `config.yaml` under `claude.model_overrides` or default to opus for everything.

---

## Source Management

### Curated Source List (`config.yaml`)

```yaml
sources:
  rss_feeds:
    - url: "https://gcaptain.com/feed/"
      name: "gCaptain"
      trust_tier: 1
      domains: ["maritime", "shipping"]
    - url: "https://www.semianalysis.com/feed"
      name: "SemiAnalysis"
      trust_tier: 1
      domains: ["semiconductors"]

  trusted_domains:
    tier_1:
      - "lloydlist.com"
      - "semianalysis.com"
      - "chinatalk.substack.com"
      - "brookings.edu"
      - "csis.org"
      - "ft.com"
      - "reuters.com"
    tier_2:
      - "economist.com"
      - "wsj.com"
      - "nytimes.com"
      - "bloomberg.com"
      - "foreignaffairs.com"
    tier_3:
      - "bbc.com"
      - "apnews.com"

  blocked_domains:
    - "medium.com"
    - "seekingalpha.com"

search:
  provider: "brave"
  api_key_env: "BRAVE_SEARCH_API_KEY"

claude:
  command: "claude"
  default_model: "opus"
  model_overrides:
    scan: "sonnet"
    digest_extract: "sonnet"

archive:
  past_articles:
    - path: "~/writing/published/"
      format: "markdown"
```

### Trust Tier Behavior

| Tier | Search Rank Boost | RSS Included | Notes |
|------|------------------|--------------|-------|
| Tier 1 | 3x | Yes | Primary/expert sources |
| Tier 2 | 1.5x | Optional | Quality journalism |
| Tier 3 | 1x | No | No boost, included if relevant |
| Untiered | 0.5x | No | Unknown domains, penalized not excluded |
| Blocked | Excluded | No | Filtered out entirely |

---

## Technical Requirements

### Dependencies

- **Python 3.11+**
- **feedparser** — RSS parsing
- **httpx** — HTTP client for search API
- **pymupdf** (PyMuPDF/fitz) — PDF text extraction
- **click** — CLI framework
- **pyyaml** — Config parsing
- **rich** — Terminal output formatting (progress bars, tables)
- **Claude Code CLI** — Must be installed and authenticated (`claude` on PATH)

### Error Handling

- **Network failures:** Retry with exponential backoff (3 attempts). Cache successful fetches. Skip failures and note them in output.
- **Claude Code failures:** Log full stderr. Preserve partial output. Allow re-running the stage.
- **PDF extraction failures:** If a PDF can't be extracted (scanned image, corrupted), log a warning and skip it. Suggest OCR tools in the warning message.
- **Rate limits:** Respect search API rate limits. Default 1 request/second for web fetches.
- **Empty sources directory:** `keel digest` errors with a clear message: "No PDFs found in sources/. Add PDFs from your scan results, then run again."
- **No thesis selected:** `keel research` errors with: "No [SELECTED] thesis found in 03-thesis.md. Mark your chosen thesis and run again."

### Performance Targets

| Stage | Target Duration | Primary Bottleneck |
|-------|----------------|-------------------|
| Scan | 1-2 minutes | Web fetches |
| Digest (extract) | 1-2 min per PDF | Claude Code per-file extraction |
| Digest (synthesis) | 2-3 minutes | Claude Code reasoning |
| Thesis | 1-2 minutes | Claude Code reasoning |
| Research | 5-15 minutes | Claude Code web search + synthesis |

---

## Future Considerations (Out of Scope for V1)

- **Stage 5: Draft assistance.** Scaffolding, section-by-section writing support, argument pressure-testing. Likely better as a Claude Project with loaded context than a CLI command.
- **Multi-platform formatting.** Generate platform-specific versions from a finished draft.
- **Source quality learning.** Track which sources get cited in published pieces to adjust trust scores.
- **PDF auto-download.** Attempt to fetch and save PDFs from scan URLs automatically (with paywall detection and graceful fallback).
- **Collaborative research.** Multiple authors on the same project.

---

## Success Criteria

1. `keel scan` returns a usable source table within 2 minutes.
2. `keel digest` produces accurate, well-structured markdown extracts with correct metadata for >90% of PDFs.
3. `keel thesis` generates at least 2 thesis candidates the author would seriously consider writing.
4. `keel research` surfaces at least 3 primary sources the author didn't already know about.
5. End-to-end time from topic to "ready to write" is under 1 hour (vs. current 4-6 hours).
6. The tool feels like a research assistant, not a content generator. The author's voice and analytical lens remain central.
