# Claw CLI Usage

This guide covers the Rust workspace under `rust/` and the `claw` CLI binary. If you want the offline bundled launcher instead, start with [`README.md`](./README.md) or [`local_ai/README.md`](./local_ai/README.md).

## Quick start

```bash
cd rust
cargo build --workspace
./target/debug/claw
```

Recommended first check after build:

```text
/doctor
```

For a saved session:

```bash
./target/debug/claw --resume latest /doctor
```

## Prerequisites

- Rust toolchain with `cargo`
- One of:
  - `ANTHROPIC_API_KEY`
  - `ANTHROPIC_AUTH_TOKEN`
  - `claw login`
- Optional provider endpoint override such as `ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`, or `XAI_BASE_URL`

## Build

```bash
cd rust
cargo build --workspace
```

Release build:

```bash
cd rust
cargo build --workspace --release
```

The binary is written to `rust/target/debug/claw` or `rust/target/release/claw`.

## Invocation modes

### Interactive REPL

```bash
cd rust
./target/debug/claw
```

### One-shot prompt

```bash
cd rust
./target/debug/claw prompt "summarize this repository"
```

### Shorthand one-shot prompt

```bash
cd rust
./target/debug/claw "explain rust/crates/runtime/src/lib.rs"
```

### Compact text output

```bash
cd rust
./target/debug/claw --compact "summarize Cargo.toml"
```

### JSON output

```bash
cd rust
./target/debug/claw --output-format json prompt "status"
```

## Common flags

```bash
cd rust
./target/debug/claw --model sonnet prompt "review this diff"
./target/debug/claw --permission-mode read-only prompt "summarize Cargo.toml"
./target/debug/claw --permission-mode workspace-write prompt "update README.md"
./target/debug/claw --allowedTools read,glob "inspect the runtime crate"
./target/debug/claw --resume latest
./target/debug/claw --resume latest /status /diff
```

### Permission modes

| Mode | Effect |
|------|--------|
| `read-only` | Read/search tools only; writes denied |
| `workspace-write` | Writes allowed within workspace boundary |
| `danger-full-access` | No sandbox restrictions |

### Model aliases

| Alias | Resolves to |
|-------|-------------|
| `opus` | `claude-opus-4-6` |
| `sonnet` | `claude-sonnet-4-6` |
| `haiku` | `claude-haiku-4-5-20251213` |

Unrecognized model names are passed through verbatim, which is useful for Ollama tags, OpenRouter model slugs, and full provider-specific IDs.

## Top-level commands

```text
claw [--model MODEL] [--allowedTools TOOL[,TOOL...]]
claw [--model MODEL] [--output-format text|json] prompt TEXT
claw [--model MODEL] [--output-format text|json] TEXT
claw --resume [SESSION.jsonl|session-id|latest] [/status] [/compact] [...]
claw help
claw version
claw status
claw sandbox
claw doctor
claw dump-manifests
claw bootstrap-plan
claw agents
claw mcp
claw skills
claw system-prompt [--cwd PATH] [--date YYYY-MM-DD]
claw login
claw logout
claw init
claw export [PATH] [--session SESSION] [--output PATH]
```

Useful examples:

```bash
claw --model opus "summarize this repo"
claw --output-format json prompt "explain src/main.rs"
claw --compact "summarize Cargo.toml"
claw --allowedTools read,glob "summarize Cargo.toml"
claw --resume latest
claw --resume latest /status /diff /export notes.md
claw doctor
claw login
claw export
```

## Authentication

### API key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### OAuth

```bash
cd rust
./target/debug/claw login
./target/debug/claw logout
```

## Provider configuration

`claw` supports Anthropic-native and OpenAI-compatible endpoints through environment variables.

### Anthropic-compatible endpoint

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8080"
export ANTHROPIC_AUTH_TOKEN="local-dev-token"

cd rust
./target/debug/claw --model "claude-sonnet-4-6" prompt "reply with ready"
```

### OpenAI-compatible endpoint

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8000/v1"
export OPENAI_API_KEY="local-dev-token"

cd rust
./target/debug/claw --model "qwen2.5-coder" prompt "reply with ready"
```

### Ollama

```bash
export OPENAI_BASE_URL="http://127.0.0.1:11434/v1"
unset OPENAI_API_KEY

cd rust
./target/debug/claw --model "llama3.2" prompt "summarize this repository in one sentence"
```

### OpenRouter

```bash
export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
export OPENAI_API_KEY="sk-or-v1-..."

cd rust
./target/debug/claw --model "openai/gpt-4.1-mini" prompt "summarize this repository in one sentence"
```

### Provider matrix

| Provider | Protocol | Auth env var(s) | Base URL env var | Default base URL |
|----------|----------|-----------------|------------------|------------------|
| Anthropic | Messages API | `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` or OAuth | `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` |
| xAI | OpenAI-compatible | `XAI_API_KEY` | `XAI_BASE_URL` | `https://api.x.ai/v1` |
| OpenAI-compatible | Chat Completions | `OPENAI_API_KEY` | `OPENAI_BASE_URL` | `https://api.openai.com/v1` |

## Sessions and resume

- REPL sessions auto-save to `.claw/sessions/`
- `latest` can be used with `--resume`, `/resume`, or `/session switch`
- Resume-safe commands include inspection and export flows such as `/status`, `/diff`, and `/export`

Examples:

```bash
claw --resume latest
claw --resume latest /status
claw --resume latest /status /diff /export notes.md
```

## REPL tips

- `Tab` expands slash commands, model aliases, permission modes, and recent session IDs
- `Shift+Enter` or `Ctrl+J` inserts a newline
- `/multiline` is the most reliable multi-line input mode
- `/submit` sends a multiline draft
- `/cancel` aborts a multiline draft

Common slash commands:

- Session and status: `/help`, `/status`, `/sandbox`, `/cost`, `/resume`, `/session`, `/version`, `/usage`, `/stats`
- Workspace and git: `/compact`, `/clear`, `/config`, `/memory`, `/init`, `/diff`, `/commit`, `/pr`, `/issue`, `/export`, `/hooks`, `/files`, `/branch`
- Discovery: `/mcp`, `/agents`, `/skills`, `/doctor`, `/tasks`, `/context`, `/desktop`, `/ide`
- Automation: `/review`, `/advisor`, `/insights`, `/security-review`, `/subagent`, `/team`, `/telemetry`, `/providers`, `/cron`
- Plugins: `/plugin`, `/plugins`, `/marketplace`

## User-defined aliases

`claw` reads settings from `~/.claw/settings.json`, `.claw/settings.json`, and `.claw/settings.local.json`, with project-local settings taking precedence.

Example:

```json
{
  "aliases": {
    "fast": "claude-haiku-4-5-20251213",
    "smart": "claude-opus-4-6",
    "cheap": "grok-3-mini"
  }
}
```

## HTTP proxy

`claw` respects `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY`.

```bash
export HTTPS_PROXY="http://proxy.corp.example:3128"
export HTTP_PROXY="http://proxy.corp.example:3128"
export NO_PROXY="localhost,127.0.0.1,.corp.example"
```

## Workspace layout

```text
rust/
├── Cargo.toml
├── Cargo.lock
└── crates/
    ├── api/
    ├── commands/
    ├── compat-harness/
    ├── mock-anthropic-service/
    ├── plugins/
    ├── runtime/
    ├── rusty-claude-cli/
    ├── telemetry/
    └── tools/
```

See [`rust/README.md`](./rust/README.md) for crate-level details and implementation notes.
