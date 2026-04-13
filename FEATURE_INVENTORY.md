# Hermes Agent — Comprehensive Feature Inventory

## 1. Tool Implementations (`tools/` directory)

### 1.1 Core Tools

| Tool | File | Description |
|------|------|-------------|
| **terminal** | `terminal_tool.py` | Execute shell commands across local, Docker, Modal, SSH, Singularity, and Daytona backends. Supports foreground/background execution, VM lifecycle management, auto-cleanup, disk usage warnings. |
| **process** | `process_registry.py` | Manage background processes: spawn, poll, wait, kill, log retrieval. Rolling 200KB output buffer, crash recovery via JSON checkpoint, session-scoped tracking. |
| **read_file** | `file_tools.py` | Read files with line numbers, pagination (offset/limit), 100K char guard, device path blocklist, image/binary detection, fuzzy filename suggestions on miss. |
| **write_file** | `file_tools.py` | Write/create files with automatic parent directory creation, atomic writes, deny-list for sensitive paths (.ssh, .env, .bashrc, etc.). |
| **patch** | `file_tools.py` + `patch_parser.py` | Targeted find-and-replace edits with fuzzy matching (9 strategies). V4A multi-file patch format support. Auto-runs syntax checks after editing. |
| **search_files** | `file_tools.py` | Ripgrep-backed content search and file-by-glob search. Output modes: content with line numbers, file paths only, match counts. |
| **file_operations** | `file_operations.py` | Backend-agnostic file operations layer (read/write/patch/search) that works across all terminal backends via shell command wrapping. Write-path deny list for credential files. |

### 1.2 Web & Browser Tools

| Tool | File | Description |
|------|------|-------------|
| **web_search** | `web_tools.py` | Search the web via multiple backends: Exa, Firecrawl, Parallel, Tavily. LLM-powered intelligent content extraction with Gemini Flash. |
| **web_extract** | `web_tools.py` | Extract/summarize content from specific URLs with markdown output. |
| **web_crawl** | `web_tools.py` | Crawl websites with specific instructions (Firecrawl/Tavily backends). |
| **browser_navigate** | `browser_tool.py` | Navigate to URLs in headless Chromium (local) or Browserbase (cloud). Accessibility tree snapshots (ariaSnapshot). |
| **browser_snapshot** | `browser_tool.py` | Get text-based page snapshot via accessibility tree. |
| **browser_click** | `browser_tool.py` | Click elements by ref selector (@e1, @e2). |
| **browser_type** | `browser_tool.py` | Type text into form fields. |
| **browser_scroll** | `browser_tool.py` | Scroll page up/down. |
| **browser_back** | `browser_tool.py` | Navigate back. |
| **browser_press** | `browser_tool.py` | Press keyboard keys. |
| **browser_close** | `browser_tool.py` | Close browser session. |
| **browser_get_images** | `browser_tool.py` | Extract image URLs from page. |
| **browser_vision** | `browser_tool.py` | Screenshot + vision analysis of current page. |
| **browser_console** | `browser_tool.py` | Execute JavaScript in browser console. |
| **Camofox backend** | `browser_camofox.py` | Anti-detection Firefox fork (Camoufox) with C++ fingerprint spoofing, REST API interface, VNC support. |

### 1.3 Vision, Image & Media Tools

| Tool | File | Description |
|------|------|-------------|
| **vision_analyze** | `vision_tools.py` | Analyze images from URLs/files with custom prompts. Multi-provider routing (OpenRouter, Nous, Codex, Anthropic, custom). |
| **image_generate** | `image_generation_tool.py` | Generate images via FAL.ai FLUX 2 Pro with automatic 2x Clarity Upscaler. Configurable aspect ratio, steps, guidance. |
| **text_to_speech** | `tts_tool.py` | Five TTS providers: Edge TTS (free default), ElevenLabs, OpenAI, MiniMax, NeuTTS (local). Opus for Telegram, MP3 for others. |
| **voice_mode** | `voice_mode.py` | Push-to-talk audio recording/playback. Sounddevice + numpy for capture, WAV encoding, STT dispatch, TTS playback. |
| **transcription** | `transcription_tools.py` | STT with three providers: faster-whisper (local, free), Groq Whisper API, OpenAI Whisper API. Auto-transcribes voice messages across all platforms. |
| **neutts_synth** | `neutts_synth.py` | On-device neural TTS synthesis via neutts_cli. |

### 1.4 AI & Reasoning Tools

| Tool | File | Description |
|------|------|-------------|
| **mixture_of_agents** | `mixture_of_agents_tool.py` | Multi-model collaboration: parallel reference models (Claude, Gemini, GPT, DeepSeek) → aggregator synthesis. For complex reasoning, coding, math. |
| **execute_code** | `code_execution_tool.py` | Programmatic Tool Calling (PTC). LLM writes Python scripts that call Hermes tools via RPC, collapsing multi-step tool chains into single inference turns. UDS (local) or file-based RPC (remote). |
| **delegate_task** | `delegate_tool.py` | Spawn child AIAgent instances with isolated context, restricted toolsets, own terminal sessions. Single-task and batch (parallel) modes. Max 3 concurrent children, max depth 2. |
| **clarify** | `clarify_tool.py` | Present structured multiple-choice or open-ended questions to users. Arrow-key navigation in CLI, numbered list on messaging platforms. |

### 1.5 Memory & Planning Tools

| Tool | File | Description |
|------|------|-------------|
| **memory** | `memory_tool.py` | Persistent file-backed curated memory with two stores: MEMORY.md (agent notes) and USER.md (user preferences). Actions: add, replace, remove, read. Substring matching for edits. Threat pattern scanning for injection/exfiltration. Frozen snapshot in system prompt with live disk writes. |
| **todo** | `todo_tool.py` | In-memory task list for decomposing complex tasks. Items: id, content, status (pending/in_progress/completed/cancelled). Replace or merge modes. Survives context compression. |
| **session_search** | `session_search_tool.py` | Search past session transcripts via SQLite FTS5, then summarize top matching sessions with cheap/fast model. Returns focused summaries, not raw transcripts. |

### 1.6 Skills Tools

| Tool | File | Description |
|------|------|-------------|
| **skills_list** | `skills_tool.py` | List skills with metadata (progressive disclosure tier 1). YAML frontmatter parsing, platform filtering, category organization. |
| **skill_view** | `skills_tool.py` | Load full skill content (tier 2-3). Supports viewing references, templates, supporting files. |
| **skill_manage** | `skill_manager_tool.py` | Agent-managed skill CRUD: create, edit, patch, delete, write_file, remove_file. Skills are procedural memory — captured successful approaches as reusable knowledge. Security scanning via skills_guard. |
| **skills_guard** | `skills_guard.py` | Security scanner for externally-sourced skills. Regex static analysis for data exfiltration, prompt injection, destructive commands. Trust levels: builtin, trusted, community. |
| **skills_hub** | `skills_hub.py` | Unified skills marketplace: search, browse, inspect, install from registries. |
| **skills_sync** | `skills_sync.py` | Synchronize skills between local and remote sources. |

### 1.7 Messaging & Cross-Platform Tools

| Tool | File | Description |
|------|------|-------------|
| **send_message** | `send_message_tool.py` | Cross-channel messaging via platform APIs (Telegram, Discord, Slack, Feishu). Supports listing targets, resolving channel names, media attachments (images, video, audio, voice). Secret redaction in errors. |
| **cronjob** | `cronjob_tools.py` | Compressed action-oriented cron management: create, list, get, edit, pause, resume, trigger, remove. Prompt threat scanning for injection. |

### 1.8 Smart Home Tools

| Tool | File | Description |
|------|------|-------------|
| **ha_list_entities** | `homeassistant_tool.py` | List/filter Home Assistant entities by domain or area. |
| **ha_get_state** | `homeassistant_tool.py` | Get detailed state of a single HA entity. |
| **ha_list_services** | `homeassistant_tool.py` | List available HA services per domain. |
| **ha_call_service** | `homeassistant_tool.py` | Call HA service (turn_on/off, set_temperature, etc.). Blocked domains: shell_command, python_script, hassio, rest_command. |

### 1.9 RL Training Tools

| Tool | File | Description |
|------|------|-------------|
| **rl_list_environments** | `rl_training_tool.py` | AST-based scanning for BaseEnv subclasses. |
| **rl_select_environment** | `rl_training_tool.py` | Select training environment. |
| **rl_get_current_config** | `rl_training_tool.py` | Get/show training configuration. |
| **rl_edit_config** | `rl_training_tool.py` | Edit training configuration. |
| **rl_start_training** | `rl_training_tool.py` | Start RL training via Tinker-Atropos subprocess. |
| **rl_check_status** | `rl_training_tool.py` | Check training status + WandB metrics. |
| **rl_stop_training** | `rl_training_tool.py` | Stop training run. |
| **rl_get_results** | `rl_training_tool.py` | Get training results. |

### 1.10 Infrastructure & Integration Tools

| Tool | File | Description |
|------|------|-------------|
| **MCP Client** | `mcp_tool.py` | Model Context Protocol client. Stdio and HTTP/StreamableHTTP transport. Auto-reconnect with exponential backoff. Sampling support (servers request LLM completions). Environment variable filtering. Thread-safe dedicated background event loop. OAuth support (`mcp_oauth.py`). |
| **MCP OAuth** | `mcp_oauth.py` | OAuth authentication flows for MCP servers. |

### 1.11 Execution Environments (`tools/environments/`)

| Environment | File | Description |
|-------------|------|-------------|
| **Local** | `local.py` | Direct host execution (default, fastest). Sanitized subprocess env. |
| **Docker** | `docker.py` | Docker container execution. Isolated. |
| **Modal** | `modal.py` | Modal cloud sandboxes. Direct credentials or managed gateway. |
| **Managed Modal** | `managed_modal.py` | Nous-hosted managed Modal for subscribers. |
| **SSH** | `ssh.py` | Remote execution via SSH. |
| **Singularity** | `singularity.py` | Singularity/Apptainer container execution. SIF cache, scratch dir management. |
| **Daytona** | `daytona.py` | Daytona cloud workspace execution. |
| **Persistent Shell** | `persistent_shell.py` | Long-lived shell sessions for stateful command sequences. |

### 1.12 Security & Safety

| Component | File | Description |
|-----------|------|-------------|
| **Dangerous Command Approval** | `approval.py` | Pattern detection (DANGEROUS_PATTERNS), per-session approval state, CLI interactive + gateway async prompting, smart approval via auxiliary LLM (auto-approve low-risk), permanent allowlist persistence. YOLO mode toggle. |
| **Tirith Pre-exec Scanner** | `tirith_security.py` | External binary scanner for homograph URLs, pipe-to-interpreter, terminal injection. Exit-code verdicts (allow/block/warn). Auto-install from GitHub with SHA-256 + optional cosign verification. |
| **OSV Malware Check** | `osv_check.py` | Queries OSV API for known malware (MAL-* IDs) in MCP extension packages before launch. Fail-open on network errors. |
| **URL Safety** | `url_safety.py` | URL validation and safety checking. |
| **Website Policy** | `website_policy.py` | User-managed website blocklist from config.yaml. Domain pattern matching with fnmatch. Cached with short TTL. |
| **Secret Redaction** | `agent/redact.py` | Regex-based redaction of API keys, tokens, credentials in logs/output. 40+ known API key prefix patterns. |
| **Write Path Deny List** | `file_operations.py` | Blocks writes to sensitive system/credential files (.ssh, .env, .bashrc, /etc/sudoers, etc.). |
| **Env Passthrough** | `env_passthrough.py` | Session-scoped allowlist for environment variables in sandboxed execution. Skills declare required vars, config supports explicit overrides. |
| **Credential Files** | `credential_files.py` | File passthrough registry for remote backends. Mounts credentials, skills, cache dirs into Docker/Modal/SSH sandboxes. |
| **Memory Threat Scanning** | `memory_tool.py` | Scans memory content for prompt injection, exfiltration via curl/wget, SSH backdoors, invisible unicode chars. |

---

## 2. Slash Commands (`hermes_cli/commands.py`)

### 2.1 Session Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `/new` | `/reset` | Start a new session (fresh session ID + history) |
| `/clear` | — | Clear screen and start a new session (CLI only) |
| `/history` | — | Show conversation history (CLI only) |
| `/save` | — | Save the current conversation (CLI only) |
| `/retry` | — | Retry the last message (resend to agent) |
| `/undo` | — | Remove the last user/assistant exchange |
| `/title [name]` | — | Set a title for the current session |
| `/branch [name]` | `/fork` | Branch the current session (explore a different path) |
| `/compress` | — | Manually compress conversation context |
| `/rollback [number]` | — | List or restore filesystem checkpoints |
| `/stop` | — | Kill all running background processes |
| `/approve [session\|always]` | — | Approve a pending dangerous command (gateway only) |
| `/deny` | — | Deny a pending dangerous command (gateway only) |
| `/background <prompt>` | `/bg` | Run a prompt in the background |
| `/btw <question>` | — | Ephemeral side question using session context (no tools, not persisted) |
| `/queue <prompt>` | `/q` | Queue a prompt for the next turn (doesn't interrupt) |
| `/status` | — | Show session info (gateway only) |
| `/profile` | — | Show active profile name and home directory |
| `/sethome` | `/set-home` | Set this chat as the home channel (gateway only) |
| `/resume [name]` | — | Resume a previously-named session |

### 2.2 Configuration Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `/config` | — | Show current configuration (CLI only) |
| `/model [model] [--global]` | — | Switch model for this session |
| `/provider` | — | Show available providers and current provider |
| `/prompt [text]` | — | View/set custom system prompt (CLI only). Subcommand: `clear` |
| `/personality [name]` | — | Set a predefined personality |
| `/statusbar` | `/sb` | Toggle the context/model status bar (CLI only) |
| `/verbose` | — | Cycle tool progress display: off → new → all → verbose |
| `/yolo` | — | Toggle YOLO mode (skip all dangerous command approvals) |
| `/reasoning [level]` | — | Manage reasoning effort/display. Subcommands: none, low, minimal, medium, high, xhigh, show, hide, on, off |
| `/skin [name]` | — | Show or change the display skin/theme (CLI only) |
| `/voice [on\|off\|tts\|status]` | — | Toggle voice mode |

### 2.3 Tools & Skills Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `/tools [list\|disable\|enable] [name...]` | — | Manage tools (CLI only) |
| `/toolsets` | — | List available toolsets (CLI only) |
| `/skills [search\|browse\|inspect\|install]` | — | Search, install, inspect, or manage skills (CLI only) |
| `/cron [subcommand]` | — | Manage scheduled tasks. Subcommands: list, add, create, edit, pause, resume, run, remove (CLI only) |
| `/reload-mcp` | `/reload_mcp` | Reload MCP servers from config |
| `/browser [connect\|disconnect\|status]` | — | Connect browser tools to live Chrome via CDP (CLI only) |
| `/plugins` | — | List installed plugins and their status (CLI only) |

### 2.4 Info Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `/commands [page]` | — | Browse all commands and skills, paginated (gateway only) |
| `/help` | — | Show available commands |
| `/usage` | — | Show token usage for the current session |
| `/insights [days]` | — | Show usage insights and analytics |
| `/platforms` | `/gateway` | Show gateway/messaging platform status (CLI only) |
| `/paste` | — | Check clipboard for an image and attach it (CLI only) |
| `/update` | — | Update Hermes Agent to the latest version (gateway only) |

### 2.5 Exit Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `/quit` | `/exit`, `/q` | Exit the CLI (CLI only) |

---

## 3. Gateway / Messaging Platform Support

### 3.1 Supported Platforms (`gateway/platforms/`)

| Platform | File | Key Features |
|----------|------|-------------|
| **Telegram** | `telegram.py`, `telegram_network.py` | Bot API, voice messages, stickers, topics/threads, photo/video/document support, BotCommands menu integration |
| **Discord** | `discord.py` | Bot with slash commands, threads, voice channels, file attachments, reactions |
| **Slack** | `slack.py` | Slack app integration, threads, file uploads, slash command mapping |
| **WhatsApp** | `whatsapp.py` | WhatsApp Business API integration |
| **Signal** | `signal.py` | Signal messenger via signal-cli HTTP API, group chats |
| **Email** | `email.py` | Email-based interaction |
| **SMS** | `sms.py` | SMS messaging integration |
| **Matrix** | `matrix.py` | Matrix/Element with optional encryption, room-based, mention/free-response modes, auto-threading |
| **Mattermost** | `mattermost.py` | Mattermost integration with home channel and reply modes |
| **DingTalk** | `dingtalk.py` | DingTalk corporate messaging |
| **Feishu/Lark** | `feishu.py` | Feishu/Lark enterprise messaging |
| **WeCom** | `wecom.py` | WeCom (WeChat Work) enterprise messaging |
| **Home Assistant** | `homeassistant.py` | HA conversation integration |
| **Webhook** | `webhook.py` | Dynamic webhook subscriptions, hot-reloadable without gateway restart |
| **API Server** | `api_server.py` | HTTP REST API endpoint for programmatic access |

### 3.2 Gateway Infrastructure

| Component | File | Description |
|-----------|------|-------------|
| **GatewayRunner** | `gateway/run.py` | Main lifecycle manager. Starts all configured platform adapters. SSL cert auto-detection for NixOS. |
| **Session Management** | `gateway/session.py` | Context tracking, conversation persistence, reset policy, dynamic system prompt injection, PII redaction (hashed sender/chat IDs). |
| **Delivery Routing** | `gateway/delivery.py` | Routes cron outputs and agent responses to appropriate targets: explicit targets, home channels, origin platform, local files. |
| **Session Mirroring** | `gateway/mirror.py` | Cross-platform message mirroring so receiving-side agents have context about what was sent. |
| **Event Hooks** | `gateway/hooks.py` | Lifecycle event system: gateway:startup, session:start/end/reset, agent:start/step/end, command:*. Hooks in ~/.hermes/hooks/. |
| **Sticker Cache** | `gateway/sticker_cache.py` | Cache for platform stickers/emojis. |
| **Channel Directory** | `gateway/channel_directory.py` | Registry of known channels across platforms. |
| **Stream Consumer** | `gateway/stream_consumer.py` | Handles streaming responses from the agent. |
| **Gateway Config** | `gateway/config.py` | Platform-specific configuration management. |
| **Pairing System** | `gateway/pairing.py` | DM pairing: request codes, approve/revoke user access, clear expired codes. |
| **Status** | `gateway/status.py` | Gateway health and status reporting. |
| **Built-in Hooks** | `gateway/builtin_hooks/boot_md.py` | System boot message hook. |

### 3.3 Gateway CLI Management (`hermes_cli/gateway.py`)

- `hermes gateway run` — Foreground execution
- `hermes gateway start` — Start as systemd/launchd service
- `hermes gateway stop` — Stop service
- `hermes gateway restart` — Restart service
- `hermes gateway status` — Show status
- `hermes gateway install` — Install as system service
- `hermes gateway uninstall` — Remove system service
- `hermes gateway setup` — Interactive setup wizard

---

## 4. Agent Core Features

### 4.1 Agent Loop (`run_agent.py` → `AIAgent`)

- **Automatic tool calling loop** until completion or iteration limit
- **Multi-provider support**: OpenRouter, Nous, Anthropic, OpenAI, GitHub Copilot, Codex, ZAI, custom OpenAI-compatible endpoints
- **Configurable model parameters**: temperature, max_tokens, reasoning effort
- **Message history management** with SQLite persistence
- **Error handling and recovery** with automatic retries

### 4.2 Context Management

| Feature | File | Description |
|---------|------|-------------|
| **Context Compression** | `agent/context_compressor.py` | Automatic LLM-powered summarization when context window fills. Structured template (Goal, Progress, Decisions, Files, Next Steps). Iterative updates, token-budget tail protection, tool output pruning. |
| **Prompt Caching** | `agent/prompt_caching.py` | Anthropic system_and_3 strategy. 4 cache breakpoints: system prompt + last 3 messages. ~75% input token cost reduction. |
| **Subdirectory Hints** | `agent/subdirectory_hints.py` | Progressive discovery of AGENTS.md, CLAUDE.md, .cursorrules as agent navigates directories. Injected into tool results. |
| **Context References** | `agent/context_references.py` | @-reference syntax: @diff, @staged, @file:path, @folder:path, @git:ref, @url:link. Security checks for sensitive paths. |
| **Checkpoint Manager** | `tools/checkpoint_manager.py` | Transparent filesystem snapshots via shadow git repos. Auto-snapshots before file mutations. Rollback to any checkpoint. |

### 4.3 Memory System

| Feature | File | Description |
|---------|------|-------------|
| **Built-in Memory** | `tools/memory_tool.py` + `agent/builtin_memory_provider.py` | MEMORY.md + USER.md file-backed stores. Frozen snapshot in system prompt, live writes to disk. Entry delimiter: § (section sign). |
| **Memory Provider API** | `agent/memory_provider.py` | Abstract base class for pluggable memory. Lifecycle hooks: initialize, system_prompt_block, prefetch, sync_turn, get_tool_schemas, handle_tool_call, shutdown. Optional: on_turn_start, on_session_end, on_pre_compress, on_memory_write, on_delegation. |
| **Memory Manager** | `agent/memory_manager.py` | Orchestrates built-in + one external provider. Builds memory context blocks for system prompt. |

### 4.4 Memory Plugins (`plugins/memory/`)

| Plugin | Description |
|--------|-------------|
| **Honcho** | Full dialectic memory with client, session management, peer names, identity seeding, session mapping, token budgets |
| **Hindsight** | External memory backend |
| **Mem0** | Mem0-powered memory |
| **Holographic** | Holographic memory with custom store and retrieval |
| **RetainDB** | RetainDB memory backend |
| **OpenViking** | OpenViking memory backend |
| **ByteRover** | ByteRover memory backend |

### 4.5 Session Management

- **SQLite-backed session persistence** with FTS5 full-text search
- **Named sessions** with title auto-generation via auxiliary LLM
- **Session branching/forking** — explore alternate conversation paths
- **Session resume** by name
- **Session search** across historical transcripts
- **Session mirroring** for cross-platform message context

### 4.6 Model Routing & Metadata

| Feature | File | Description |
|---------|------|-------------|
| **Smart Model Routing** | `agent/smart_model_routing.py` | Optional cheap-vs-strong model routing based on query complexity keywords. |
| **Model Metadata** | `agent/model_metadata.py` | Context length detection, token estimation, pricing data. Probing tiers for unknown models. |
| **Usage Pricing** | `agent/usage_pricing.py` | Cost estimation, usage normalization, compact duration formatting. |
| **Insights Engine** | `agent/insights.py` | Historical analytics: token consumption, cost estimates, tool usage patterns, activity trends, model/platform breakdowns. |
| **models.dev Catalog** | `agent/models_dev.py` | 109+ providers with base URLs, env vars, model metadata. |

### 4.7 Prompt System

| Feature | File | Description |
|---------|------|-------------|
| **SOUL.md** | `hermes_cli/default_soul.py` | Customizable agent identity/personality template. |
| **Prompt Builder** | `agent/prompt_builder.py` | Constructs system prompts with agent identity, platform hints, memory guidance, skills guidance, tool enforcement, context files. |
| **Personality Presets** | via `/personality` | Predefined personality configurations. |

---

## 5. UI / UX Features

### 5.1 Skin/Theme Engine (`hermes_cli/skin_engine.py`)

- **Data-driven YAML skins** in `~/.hermes/skins/`
- **Customizable elements**: colors (banner, UI, prompt, response), spinner faces/verbs/wings, branding (agent name, welcome/goodbye messages, prompt symbol, help header), tool prefixes, tool emojis
- **Built-in presets** (e.g., "ares") + user-defined skins
- **Hot-switching** via `/skin [name]`

### 5.2 Spinner & Display (`agent/display.py`)

- **KawaiiSpinner** — Animated spinner with customizable faces, thinking verbs, wing decorations
- **Tool preview formatting** — Configurable max length, inline diffs for file edits
- **Local edit snapshots** — Pre/post file comparison with colored unified diffs
- **Tool failure detection** — Red indicators for errors
- **Skin-aware coloring** throughout

### 5.3 Banner (`hermes_cli/banner.py`)

- **Welcome banner** with ASCII art
- **Skills summary** display
- **Update check** notification
- **Skin-aware color helpers** for all banner elements

### 5.4 Interactive CLI (`hermes_cli/curses_ui.py`)

- **Curses multi-select checklist** with keyboard navigation (used for `hermes tools`, `hermes skills`)
- **Text-based numbered fallback** for terminals without curses
- **Non-TTY safety** — returns defaults when stdin is not a terminal

### 5.5 Clipboard Integration (`hermes_cli/clipboard.py`)

- **Image extraction** from system clipboard
- **Cross-platform**: macOS (osascript/pngpaste), WSL2 (PowerShell), Linux (wl-paste/xclip)
- Triggered via `/paste` command

### 5.6 Status Bar

- **Context/model status bar** toggled via `/statusbar`
- Shows current model, token usage, context window utilization

### 5.7 Context References

- `@file:path` — Inline file content
- `@folder:path` — Directory listing
- `@diff` — Git diff of working tree
- `@staged` — Git staged changes
- `@git:ref` — Git object content
- `@url:link` — Fetch URL content

---

## 6. Configuration System

### 6.1 Config Files (`hermes_cli/config.py`)

- **`~/.hermes/config.yaml`** — All settings (model, toolsets, terminal, web, browser, display, memory, etc.)
- **`~/.hermes/.env`** — API keys and secrets (chmod 600)
- **`hermes config`** — Show current configuration
- **`hermes config edit`** — Open in editor
- **`hermes config set`** — Set specific values
- **`hermes config wizard`** — Re-run setup wizard

### 6.2 Profile System (`hermes_cli/profiles.py`)

- **Multiple isolated profiles** under `~/.hermes/profiles/<name>/`
- Each profile is a fully independent HERMES_HOME with own: config.yaml, .env, memory, sessions, skills, gateway, cron, logs
- `hermes profile create <name>` — Fresh or `--clone` / `--clone-all`
- `hermes profile use <name>` — Set as sticky default
- `hermes profile delete <name>` — Remove profile + alias + service
- `hermes -p <name>` — Per-command profile override
- Wrapper alias generation for quick access

### 6.3 Provider System (`hermes_cli/providers.py`)

- **models.dev catalog** — 109+ providers with auto-discovery
- **Hermes overlays** — Transport type, auth patterns, aggregator flags
- **User-defined providers** — `providers:` section in config.yaml
- Transport types: `openai_chat`, `anthropic_messages`, `codex_responses`
- Auth types: `api_key`, `oauth_device_code`, `oauth_external`, `external_process`

### 6.4 Authentication (`hermes_cli/auth.py`)

- **Multi-provider OAuth** device code flows (Nous Portal, OpenAI Codex)
- **API key providers** (OpenRouter, custom endpoints)
- **Credential pool** (`agent/credential_pool.py`) — Multi-credential failover for same provider
- **GitHub Copilot auth** (`hermes_cli/copilot_auth.py`) — OAuth device code flow, gho_/github_pat_/ghu_ token support
- **Auth store** — `~/.hermes/auth.json` with cross-process file locking
- JWT token refresh, agent key minting

### 6.5 Managed Mode

- **NixOS** — Declarative config via `HERMES_MANAGED` env var or `.managed` marker
- **Homebrew** — `brew upgrade hermes-agent`
- Read-only config protection in managed mode

### 6.6 Nous Subscription (`hermes_cli/nous_subscription.py`)

- Feature state tracking for Nous-hosted managed tools
- Modal sandbox gateway, browser cloud, audio API passthrough
- Tool gateway domain resolution

---

## 7. Plugin System (`hermes_cli/plugins.py`)

### 7.1 Plugin Sources

1. **User plugins** — `~/.hermes/plugins/<name>/`
2. **Project plugins** — `./.hermes/plugins/<name>/` (opt-in via `HERMES_ENABLE_PROJECT_PLUGINS`)
3. **Pip plugins** — packages exposing `hermes_agent.plugins` entry-point group

### 7.2 Plugin Lifecycle Hooks

- `pre_tool_call` / `post_tool_call`
- `pre_llm_call` / `post_llm_call`
- `pre_api_request` / `post_api_request`

### 7.3 Plugin Capabilities

- Tool registration via `PluginContext.register_tool()`
- Slash command registration via `register_plugin_command()`
- `plugin.yaml` manifest with metadata
- `register(ctx)` function in `__init__.py`

---

## 8. CLI Subcommands (`hermes_cli/main.py`)

| Command | Description |
|---------|-------------|
| `hermes` / `hermes chat` | Interactive chat (default) |
| `hermes gateway [run\|start\|stop\|restart\|status\|install\|uninstall\|setup]` | Gateway management |
| `hermes setup` | Interactive setup wizard |
| `hermes logout` | Clear stored authentication |
| `hermes status` | Show status of all components |
| `hermes cron [list\|create\|edit\|pause\|resume\|run\|remove\|status\|tick]` | Cron job management |
| `hermes doctor` | Check configuration and dependencies |
| `hermes honcho [setup\|status\|sessions\|map\|peer\|mode\|tokens\|identity\|migrate]` | Honcho AI memory integration management |
| `hermes version` | Show version |
| `hermes update` | Update to latest version |
| `hermes uninstall` | Uninstall Hermes Agent |
| `hermes acp` | Run as ACP server for editor integration |
| `hermes sessions browse` | Interactive session picker with search |
| `hermes pairing [list\|approve\|revoke\|clear-pending]` | DM pairing management |
| `hermes webhook [subscribe\|list\|remove\|test]` | Webhook subscription management |
| `hermes profile [create\|use\|delete\|list]` | Profile management |
| `hermes tools` | Interactive tool configuration (curses TUI) |
| `hermes skills [search\|browse\|inspect\|install]` | Skills hub CLI |
| `hermes model` | Model selection TUI |

---

## 9. Toolset System (`toolsets.py`)

### 9.1 Core Toolset (`_HERMES_CORE_TOOLS`)

Web (search, extract), terminal + process, file manipulation (read/write/patch/search), vision + image generation, MoA, skills, browser automation (11 tools), TTS, planning & memory (todo, memory), session search, clarify, code execution + delegation, cronjob, Home Assistant (4 tools), RL training (8 tools).

### 9.2 Toolset Distributions (`toolset_distributions.py`)

Probabilistic toolset distributions for batch data generation:
- **default** — All tools at 100%
- **image_gen** — Heavy image generation focus
- **research** — Web research + browser + vision
- **science** — Scientific computing with web/terminal/file/browser

---

## 10. Batch Processing (`batch_runner.py`)

- **Parallel batch processing** with multiprocessing
- **Dataset loading** from JSONL files
- **Checkpointing** for fault tolerance and resumption
- **Trajectory saving** in ShareGPT format (from/value pairs)
- **Tool usage statistics** aggregation across all batches
- **Configurable toolset distributions**
- Rich progress bars with spinner, ETA, completion counts

---

## 11. RL Training (`rl_cli.py`)

- **Dedicated CLI runner** for RL training workflows
- Extended timeouts for long-running training
- RL-focused system prompts
- Full toolset including RL training tools
- 30-minute check interval handling
- Environment discovery and management

---

## 12. Environments / Benchmark Support (`environments/`)

### 12.1 Agent Environments

| Environment | File | Description |
|-------------|------|-------------|
| **Agent Loop** | `agent_loop.py` | Core agent execution loop |
| **Tool Context** | `tool_context.py` | Tool execution context management |
| **Hermes Base Env** | `hermes_base_env.py` | Base environment for agent execution |
| **Terminal Test Env** | `terminal_test_env/` | Testing environment for terminal tools |
| **Hermes SWE Env** | `hermes_swe_env/` | Software engineering benchmark environment |
| **Web Research Env** | `web_research_env.py` | Web research task environment |
| **Agentic OPD Env** | `agentic_opd_env.py` | Agentic open-problem dataset environment |

### 12.2 Tool Call Parsers

Parsers for non-standard model tool calling formats:
- **Hermes** (native), **DeepSeek v3/v3.1**, **Qwen/Qwen3 Coder**, **Llama**, **Mistral**, **GLM 4.5/4.7**, **Kimi K2**, **Longcat**

### 12.3 Benchmarks

- **YC Bench** — Y Combinator benchmark
- **TBLite** — Terminal-based lite benchmark
- **TerminalBench 2** — Terminal benchmark v2

---

## 13. Optional Skills (`optional-skills/`)

Categorized skill packs:
- **Research**: Parallel CLI, GitNexus Explorer, QMD, DuckDuckGo Search, Scrapling, Bioinformatics, Domain Intel
- **DevOps**: Docker Management, CLI
- **Security**: Sherlock, OSS Forensics, 1Password
- **Health**: NeuroSkill BCI
- **MLOps**: NeMo Curator, Accelerate, Chroma, SimPO, SLIME, Lambda Labs, HuggingFace Tokenizers, Pinecone, TensorRT-LLM, Qdrant, FAISS, PyTorch Lightning, Flash Attention, LLaVA, Instructor, SAELens, TorchTitan, Hermes Atropos Environments
- **MCP**: FastMCP scaffolding with templates
- **Blockchain**: Solana, Base
- **Creative**: Blender MCP, Meme Generation
- **Communication**: 1-3-1 Rule
- **Migration**: OpenClaw → Hermes migration
- **Email**: AgentMail
- **Autonomous AI Agents**: Blackbox, Honcho
- **Productivity**: Memento Flashcards, Canvas, Telephony, SiYuan

---

## 14. Unique / Notable Capabilities

1. **Programmatic Tool Calling (PTC)** — LLM writes Python that calls tools via RPC, collapsing multi-step chains into single inference turns
2. **Mixture-of-Agents (MoA)** — Parallel multi-model collaboration for complex reasoning
3. **Camofox Anti-Detection Browser** — Firefox fork with C++ fingerprint spoofing
4. **7 Memory Provider Plugins** — Honcho, Hindsight, Mem0, Holographic, RetainDB, OpenViking, ByteRover
5. **15 Messaging Platforms** — Telegram, Discord, Slack, WhatsApp, Signal, Email, SMS, Matrix, Mattermost, DingTalk, Feishu, WeCom, Home Assistant, Webhook, REST API
6. **6 Execution Environments** — Local, Docker, Modal, SSH, Singularity, Daytona
7. **Tirith Security Scanner** — Binary pre-exec scanning with supply chain verification (cosign)
8. **Skills Guard** — Static analysis security scanner for community skills
9. **Filesystem Checkpoints** — Shadow git repos for transparent rollback
10. **Session Branching/Forking** — Explore alternate conversation paths
11. **Context References (@-syntax)** — @file, @folder, @diff, @staged, @git, @url
12. **Progressive Subdirectory Hints** — Auto-discovers AGENTS.md/CLAUDE.md as agent navigates
13. **Anthropic Prompt Caching** — ~75% input token cost reduction
14. **Smart Model Routing** — Automatic cheap-vs-strong model selection
15. **Profile System** — Fully isolated multi-instance support
16. **Credential Pool** — Multi-credential failover for same provider
17. **Data-driven Skin System** — Full visual customization via YAML
18. **Home Assistant Integration** — 4-tool smart home control suite
19. **RL Training Pipeline** — Full Tinker-Atropos training lifecycle management
20. **ACP Server Mode** — Editor integration protocol support
21. **Webhook Subscriptions** — Hot-reloadable dynamic webhook endpoints
22. **DM Pairing System** — Secure user authentication for messaging platforms
23. **Session Search via FTS5** — Full-text search across historical transcripts with LLM summarization
24. **MCP Sampling** — MCP servers can request LLM completions (bidirectional)
25. **OSV Malware Check** — Queries Google's OSV API before launching MCP extensions
26. **NixOS/Homebrew Managed Mode** — Declarative configuration support
27. **Batch Runner** — Parallel multi-process data generation with toolset distributions
28. **10+ Tool Call Parsers** — Support for non-standard model tool formats (DeepSeek, Qwen, Llama, Mistral, GLM, Kimi, etc.)
