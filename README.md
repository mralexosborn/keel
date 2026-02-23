# Keel

Compress the research-to-draft pipeline for long-form analytical writing. Keel uses Claude to discover sources, extract insights from PDFs, and synthesize findings — organized as a sequential stage pipeline you control.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- [Brave Search API key](https://brave.com/search/api/)

## Setup

```bash
# Install dependencies
uv sync

# Set your Brave Search API key
export BRAVE_SEARCH_API_KEY="your-key-here"

# Verify installation
uv run keel --help
```

## Quick Start

```bash
# 1. Create a new project (auto-runs scan)
uv run keel new "Vietnamese shipyard capacity expansion"

# 2. Review scan-1.md, save relevant articles as PDFs into sources/
#    ~/.keel/projects/vietnamese-shipyard-capacity-expansion/sources/

# 3. Extract and synthesize your sources
uv run keel digest
```

## Commands

### Project Lifecycle

```bash
keel new "topic"          # Create project + auto-run scan
keel status               # Show current stage and next action
keel list                 # List all projects (* = active)
keel set <slug>           # Switch active project
keel archive              # Move active project to ~/.keel/archive/
```

### Pipeline Stages

```bash
keel scan                 # Stage 1: Discover sources → scan-N.md
keel digest               # Stage 2: Extract PDFs + synthesize → 02-digest.md
```

Stages run in order. Re-running `keel scan` creates a new numbered version (`scan-1.md`, `scan-2.md`, ...) so you can compare results across runs.

### Source Management

```bash
keel sources                                    # List configured feeds and domains
keel sources add "https://example.com/feed/"    # Add RSS feed (default tier 2)
keel sources add example.com --type domain --tier 1   # Add trusted domain
keel sources remove "https://example.com/feed/" # Remove a source
```

## Global Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--project <slug>` | `-p` | Operate on a specific project instead of the active one |
| `--verbose` | `-v` | Show Claude Code invocations and raw output |
| `--no-cache` | | Force re-fetch/re-extract (ignore cached results) |
| `--edit` | | Open output file in `$EDITOR` after stage completes |
| `--context <file>` | | Load a one-off seed context file for this invocation |

## Workflow

```
keel new "topic"
    │
    ▼
 scan-1.md ← ranked source table
    │
    │  (you review, save PDFs to sources/)
    ▼
keel digest
    │
    ▼
 extracts/*.md ← structured markdown per PDF
 02-digest.md  ← synthesis across all sources
```

## Providing Seed Context

If you already have notes, a paper, or a thread you want to start from:

- **Persistent:** Drop a `notes.md` into the project directory — it's included in every Claude invocation.
- **One-off:** Use `--context path/to/file.md` for a single stage run.

## Trust Tiers

Sources are ranked by trust tier during scan:

| Tier | Boost | Description |
|------|-------|-------------|
| Tier 1 | 3x | Primary/expert sources |
| Tier 2 | 1.5x | Quality journalism |
| Tier 3 | 1x | General news, no boost |
| Untiered | 0.5x | Unknown domains, penalized |
| Blocked | Excluded | Filtered out entirely |

Configure in `~/.keel/config.yaml` under `sources.trusted_domains` and `sources.blocked_domains`.

## File Layout

```
~/.keel/
  config.yaml              # Sources, search config, model overrides
  .active                  # Tracks active project slug
  projects/
    <slug>/
      .state               # Stage progression tracker
      notes.md             # Optional seed context
      scan-1.md            # Scan output (numbered versions)
      scan-2.md            # Re-run creates next version
      sources/             # Drop PDFs here
      extracts/            # Per-source markdown
      02-digest.md         # Digest output
  archive/                 # Archived projects
```

## Configuration

Edit `~/.keel/config.yaml` to customize:

```yaml
sources:
  rss_feeds:
    - url: "https://gcaptain.com/feed/"
      name: "gCaptain"
      trust_tier: 1
  trusted_domains:
    tier_1: ["ft.com", "reuters.com"]
    tier_2: ["economist.com", "wsj.com"]
  blocked_domains: ["medium.com"]

search:
  api_key_env: "BRAVE_SEARCH_API_KEY"

claude:
  default_model: "opus"
  model_overrides:
    scan: "sonnet"            # Fast query generation
    digest_extract: "sonnet"  # Per-PDF extraction
    # digest_synthesis uses default (opus)
```

## License

AGPL-3.0 — see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome. Please open an issue to discuss your idea before submitting a pull request.
