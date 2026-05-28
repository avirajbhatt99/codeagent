# ultracode

AI-powered coding assistant CLI. Works with local models (Ollama) or cloud providers (OpenRouter, HuggingFace).

**No environment variables needed** - everything is configured through simple CLI prompts.

## Install

### From PyPI (recommended)

```bash
pip install ultracode
```

Or with [pipx](https://pipx.pypa.io/) for an isolated install:

```bash
pipx install ultracode
```

### From source

```bash
git clone https://github.com/avirajbhatt99/code-agent.git
cd code-agent
pip install -e .
```

### Verify

```bash
ultracode --version
```

## Quick Start

### 1. Install Ollama (for local models)

**macOS:**
```bash
brew install ollama
ollama serve            # start the server
ollama pull qwen2.5:7b  # download a model
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve
ollama pull qwen2.5:7b
```

**Windows:**
Download from [ollama.ai/download](https://ollama.ai/download), then:
```powershell
ollama serve
ollama pull qwen2.5:7b
```

(Skip Ollama if you'd rather use OpenRouter or HuggingFace.)

### 2. Run ultracode

```bash
ultracode
```

First time? You'll see a setup wizard that asks you to pick a provider (Ollama / OpenRouter / HuggingFace) and a model.

### 3. Start coding

```
❯ read my code and explain it
● Glob(**/*.py)
● Read(src/main.py)
● Read(src/utils.py)

This is a Python CLI application that...

❯ write a function to calculate fibonacci
● Write(fibonacci.py)

Created fibonacci.py with the function.

❯ run the tests
● Bash(pytest)

All tests passed.
```

## Usage

### CLI commands

```bash
ultracode              # start interactive session
ultracode setup        # re-run setup wizard
ultracode config       # view/edit configuration
ultracode models       # list available models
ultracode pull         # download an Ollama model
ultracode --help       # show all commands
```

### Configuration

```bash
ultracode config                      # view current config
ultracode config --provider openrouter
ultracode config --model gpt-4o
ultracode config --api-key            # update API key
ultracode config --reset              # reset to defaults
```

### In-session slash commands

The leading `/` is optional.

| Command | Action |
|---------|--------|
| `/help` | Show help |
| `/clear` | Clear conversation and todos |
| `/tokens` | Show token usage this session |
| `/todos` | Show the current todo list |
| `/exit` | Quit (also `/quit`, `/q`, `Ctrl+D`) |
| `Esc` | Interrupt the current response |

## Tools

ultracode ships with 48+ tools. Highlights:

| Category | Tools |
|----------|-------|
| **Files** | `read_file`, `write_file`, `edit_file`, `delete`, `copy`, `move`, `mkdir`, `ls` |
| **Search** | `glob`, `grep` |
| **Shell** | `bash` |
| **Git** | `git_status`, `git_diff`, `git_log`, `git_add`, `git_commit`, `git_branch`, `git_checkout`, `git_push`, `git_pull`, `git_reset`, `git_merge`, `git_stash`, `git_clone`, `git_tag`, `git_remote`, `git_init` |
| **Web** | `web_fetch`, `http_request` |
| **Packages** | `npm_*`, `pip_*`, `cargo_*` |
| **Planning** | `todo_write` |

Mutating tools (writes, shell, destructive git, network requests) ask for permission before running. Approve once (`y`), allow for the rest of the session (`a`), or deny (`n`, default).

### Example tasks

```
"read my code and explain it"
"write a REST API for user management"
"fix the bug in auth.py"
"run the tests and fix failures"
"refactor this function to be cleaner"
"add type hints to utils.py"
```

## Providers

### Ollama (local) — default

- Free and private, runs on your machine
- Recommended: `qwen2.5-coder:7b`, `llama3.1:8b`, `mistral:7b`
- **Tool calling is model- and version-dependent on Ollama.** If the agent returns JSON as text instead of actually invoking tools, your model isn't emitting structured `tool_calls`. Try a different model or upgrade Ollama. Cloud providers (OpenRouter, HuggingFace) are more reliable for tool use.

### OpenRouter (cloud)

- Access GPT-4, Claude, Llama, DeepSeek, and more
- Some free models available
- Get an API key: <https://openrouter.ai/keys>
- Anthropic models (`anthropic/*`) use prompt caching automatically to keep long sessions cheap

### HuggingFace (cloud)

- Open-source models via the HF Inference API
- Get a token: <https://huggingface.co/settings/tokens>

## Configuration file

Settings stored in:
- **macOS / Linux:** `~/.config/codeagent/config.json`
- **Windows:** `%APPDATA%\codeagent\config.json`

```json
{
  "provider": "ollama",
  "model": "qwen2.5:7b",
  "ollama_host": "http://localhost:11434",
  "max_iterations": 25
}
```

## Troubleshooting

### Ollama not connecting

```bash
ollama list             # check it's running
ollama serve            # start it
ollama pull qwen2.5:7b  # pull a model
```

### Bad API key

```bash
ultracode config --api-key
```

### Reset everything

```bash
ultracode config --reset
ultracode setup
```

### Windows

The `Esc` key interrupt is POSIX-only — on Windows, use `Ctrl+C` to interrupt and `Ctrl+Z` to exit.

If `ultracode` isn't found after `pip install`, your Python `Scripts/` directory may not be on `PATH`. Either add it (usually `C:\Users\<you>\AppData\Local\Programs\Python\Python3x\Scripts`) or run via `python -m codeagent.cli`.

## Development

```bash
git clone https://github.com/avirajbhatt99/code-agent.git
cd code-agent
pip install -e ".[dev]"

pytest                      # tests
mypy src/codeagent          # type checking
ruff check src/codeagent    # lint
```

## License

MIT
