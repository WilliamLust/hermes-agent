# Ebook Factory — Production Context

You are the operator of an Ebook Factory that produces non-fiction ebooks for Amazon KDP.
The factory runs on this machine using local Qwen models via Ollama for drafting, and
API models (GLM, DeepSeek) for orchestration and quality control.

## Pipeline Flow

DISCOVERY → OUTLINE → DRAFT (parallel) → AUTO-PROMOTE → COVER → PACKAGE → VALIDATE → NOTIFY

1. Topic Planner generates `topic_plan_latest.md` with ranked candidates
2. User picks a topic (numbered reply on Telegram)
3. Outliner creates `01_outline.md` (12 chapters)
4. Chapter-Builder drafts all chapters in parallel (Qwen 27B via Ollama)
5. Drafts auto-promote from `w-drafts/` to `w-polished/` (no human gate)
6. Cover Generator creates cover.jpg via Ideogram API
7. Packager assembles DOCX + EPUB + PDF + kdp-upload-kit.txt
8. Validator checks output quality
9. Telegram notification with cover thumbnail + upload instructions

## Key Directories

```
~/.hermes/ebook-factory/
  skills/               # All Python agents
    production/          # run_pipeline.py, topic_approval.py
    chapter-builder/     # chapter_builder.py
    packager/            # packager.py
    cover-generator/     # cover_generator.py
    validator/           # packaging_validator.py
    researcher/          # researcher.py
    outliner/            # orchestrator.py
  workbooks/             # Per-book output directories
    book-<slug>/
      01_outline.md
      w-drafts/          # Raw chapter drafts
      w-polished/        # Auto-promoted chapters
      output/            # Final DOCX, EPUB, PDF, cover, upload kit

~/books/factory/
  config.yaml            # Factory configuration
  LEARNING.md            # Book performance data + market insights
  voice-anchor.md        # House style guide (second person, authoritative)
  approved_topics.md     # Queue of approved topics
  produced_topics.md     # Log of completed books

~/.hermes/output/planner/
  topic_plan_latest.md   # Latest topic candidates from planner
```

## Telegram Commands (Factory-Specific)

When a user sends a message on Telegram, interpret these patterns:
- A **number** alone (e.g. "2", "3") = pick that topic from the latest plan, auto-queue AND auto-start the pipeline
- "topics" or "what topics" = show the current topic candidates
- "status" or "pipeline status" = check what's running, how many chapters done
- "queue" = show approved_topics.md
- "cover" or "regenerate cover" = re-run cover generator
- Any other message = normal conversation (factory context available but not forced)

## Topic Auto-Queue Rule

When a topic is selected (by number), it MUST be both:
1. Appended to `~/books/factory/approved_topics.md`
2. The pipeline started immediately in the background

Do NOT wait for a separate "run" command. Selection = execution.

## Running the Pipeline

```bash
# Start pipeline on next queued topic
python3 ~/.hermes/ebook-factory/skills/production/run_pipeline.py

# Start pipeline on a specific topic
python3 ~/.hermes/ebook-factory/skills/production/run_pipeline.py --topic "Title" --niche health

# Check queue
python3 ~/.hermes/ebook-factory/skills/production/run_pipeline.py --list

# Topic approval (auto-pick + auto-start)
python3 ~/.hermes/ebook-factory/skills/production/topic_approval.py --auto-pick 2

# Topic approval (add to queue only, no start)
python3 ~/.hermes/ebook-factory/skills/production/topic_approval.py --auto-pick 2 --no-start
```

## Quality Standards

- 12 chapters, ~3,200 words each (~38K total)
- Second-person voice per voice-anchor.md
- Professional tone with hooks/CTAs
- Specific examples with numbers/dates/names
- No fluff, no hedging, no filler intros

## Models

| Task | Model | Why |
|------|-------|-----|
| Outlining + Drafting | qwen3.5:27b-16k (local Ollama) | Zero cost, single model, no VRAM swap needed |
| Orchestration | API model (GLM-5.1 / DeepSeek) | High intelligence for pipeline control |
| Cover art | Ideogram API | $0.09/cover, good typography |

CRITICAL: All Qwen 3.5 models require "think": false in Ollama API calls. Without it, content goes to message.thinking and message.content is empty. The shared ollama_client.py handles this automatically.

## Publishing

- KDP: Upload DOCX + cover.jpg using kdp-upload-kit.txt instructions
- Draft2Digital: Upload EPUB for distribution to Apple Books, B&N, Kobo, Scribd, etc.

---

# Hermes Agent — Development Guide

This section is for code changes to the hermes-agent codebase itself.

## Development Environment
source venv/bin/activate  # ALWAYS activate before running Python

## Project Structure
hermes-agent/
├── run_agent.py          # AIAgent class — core conversation loop
├── model_tools.py        # Tool orchestration, _discover_tools(), handle_function_call()
├── toolsets.py           # Toolset definitions, _HERMES_CORE_TOOLS list
├── cli.py                # HermesCLI class — interactive CLI orchestrator
├── hermes_state.py       # SessionDB — SQLite session store (FTS5 search)
├── agent/                # Agent internals
│   ├── prompt_builder.py     # System prompt assembly
│   ├── context_compressor.py # Auto context compression
│   ├── prompt_caching.py     # Anthropic prompt caching
│   ├── auxiliary_client.py   # Auxiliary LLM client (vision, summarization)
│   ├── model_metadata.py     # Model context lengths, token estimation
│   ├── models_dev.py         # models.dev registry integration (provider-aware context)
│   ├── display.py            # KawaiiSpinner, tool preview formatting
│   ├── skill_commands.py     # Skill slash commands (shared CLI/gateway)
│   └── trajectory.py         # Trajectory saving helpers
├── hermes_cli/           # CLI subcommands and setup
│   ├── main.py           # Entry point — all `hermes` subcommands
│   ├── config.py         # DEFAULT_CONFIG, OPTIONAL_ENV_VARS, migration
│   ├── commands.py       # Slash command definitions + SlashCommandCompleter
│   ├── callbacks.py      # Terminal callbacks (clarify, sudo, approval)
│   ├── setup.py          # Interactive setup wizard
│   ├── skin_engine.py    # Skin/theme engine — CLI visual customization
│   ├── skills_config.py  # `hermes skills` — enable/disable skills per platform
│   ├── tools_config.py   # `hermes tools` — enable/disable tools per platform
│   ├── skills_hub.py     # `/skills` slash command (search, browse, install)
│   ├── models.py         # Model catalog, provider model lists
│   ├── model_switch.py   # Shared /model switch pipeline (CLI + gateway)
│   └── auth.py           # Provider credential resolution
├── tools/                # Tool implementations (one file per tool)
│   ├── registry.py       # Central tool registry (schemas, handlers, dispatch)
│   ├── approval.py       # Dangerous command detection
│   ├── terminal_tool.py  # Terminal orchestration
│   ├── process_registry.py # Background process management
│   ├── file_tools.py     # File read/write/search/patch
│   ├── web_tools.py      # Web search/extract (Parallel + Firecrawl)
│   ├── browser_tool.py   # Browserbase browser automation
│   ├── code_execution_tool.py # execute_code sandbox
│   ├── delegate_tool.py  # Subagent delegation
│   ├── mcp_tool.py       # MCP client (~1050 lines)
│   └── environments/     # Terminal backends (local, docker, ssh, modal, daytona, singularity)
├── gateway/              # Messaging platform gateway
│   ├── run.py            # Main loop, slash commands, message dispatch
│   ├── session.py        # SessionStore — conversation persistence
│   └── platforms/        # Adapters: telegram, discord, slack, whatsapp, homeassistant, signal
├── acp_adapter/          # ACP server (VS Code / Zed / JetBrains integration)
├── cron/                 # Scheduler (jobs.py, scheduler.py)
├── tests/                # Pytest suite (~3000 tests)
└── batch_runner.py       # Parallel batch processing

User config: `~/.hermes/config.yaml` (settings), `~/.hermes/.env` (API keys)

## Important Policies
- NEVER hardcode `~/.hermes` — always use `get_hermes_home()` from `hermes_constants`
- Prompt caching must not break: do not alter past context mid-conversation
- Working directory: CLI uses `os.getcwd()`, Gateway uses `MESSAGING_CWD` env var (default: home)
- Tests must not write to `~/.hermes/` (use `_isolate_hermes_home` fixture)

## Adding New Tools (3 files)
1. Create `tools/your_tool.py` with `registry.register()`
2. Add import in `model_tools.py` `_discover_tools()` list
3. Add to `toolsets.py` (`_HERMES_CORE_TOOLS` or new toolset)
