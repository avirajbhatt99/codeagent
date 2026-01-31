# CodeAgent

AI-powered coding assistant CLI. Works with local models (Ollama) or cloud providers (OpenRouter, HuggingFace).

**No environment variables needed** - everything is configured through simple CLI prompts.

## Quick Install

### Global Installation (Recommended)

**macOS / Linux:**
```bash
pip3 install git+https://github.com/avirajbhatt99/codeagent.git
```

**Windows:**
```powershell
pip install git+https://github.com/avirajbhatt99/codeagent.git
```

**With pipx (isolated environment):**
```bash
# Install pipx first if you don't have it
# macOS: brew install pipx
# Linux: sudo apt install pipx
# Windows: pip install pipx

pipx install git+https://github.com/avirajbhatt99/codeagent.git
```

### Local Development Install

```bash
git clone https://github.com/avirajbhatt99/codeagent.git
cd codeagent
pip3 install -e .
```

### Verify Installation

```bash
codeagent --version
```

## Quick Start

### 1. Install Ollama (for local models)

**macOS:**
```bash
brew install ollama
ollama serve  # Start the server
ollama pull qwen2.5:7b  # Download a model
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

### 2. Run CodeAgent

```bash
codeagent
```

First time? You'll see a setup wizard:

```
Welcome to CodeAgent!

Step 1: Choose provider
  1  Ollama (Local)    Free, private, runs locally
  2  OpenRouter        Cloud API, many models
  3  HuggingFace       Cloud API, open models

Select [1]: 1

✓ Ollama (Local)

Step 2: Checking Ollama...
✓ Ollama running

Step 3: Choose model
  1. qwen2.5:7b
  2. llama3.2:3b
  ...

Select [1]: 1

✓ Model: qwen2.5:7b

Setup complete!
```

### 3. Start Coding!

```
❯ read my code and explain it
Glob **/*.py
Read src/main.py
Read src/utils.py

This is a Python CLI application that...

❯ write a function to calculate fibonacci
Write fibonacci.py

Created fibonacci.py with fibonacci function.

❯ run the tests
$ pytest
...
All tests passed!
```

## Usage

### Basic Commands

```bash
codeagent              # Start interactive session
codeagent setup        # Re-run setup wizard
codeagent config       # View/edit configuration
codeagent models       # List available models
codeagent pull         # Download Ollama model
codeagent --help       # Show all commands
```

### Configuration

```bash
# View current config
codeagent config

# Change provider
codeagent config --provider openrouter

# Change model
codeagent config --model gpt-4o

# Update API key
codeagent config --api-key

# Reset to defaults
codeagent config --reset
```

### In-Session Commands

| Command | Action |
|---------|--------|
| `exit` | Quit session |
| `clear` | Clear history |
| `help` | Show help |
| `Ctrl+C` | Cancel current |

## Tools

CodeAgent can:

| Tool | Description |
|------|-------------|
| `read_file` | Read any file |
| `write_file` | Create new files |
| `edit_file` | Modify existing files |
| `delete` | Delete files/directories |
| `copy` | Copy files/directories |
| `move` | Move/rename files |
| `mkdir` | Create directories |
| `ls` | List directory contents |
| `glob` | Find files by pattern |
| `grep` | Search in files |
| `bash` | Run shell commands |
| `git_*` | Git operations (status, diff, commit, etc.) |

### Example Tasks

```
"read my code and explain it"
"write a REST API for user management"
"fix the bug in auth.py"
"run the tests and fix failures"
"refactor this function to be cleaner"
"add type hints to utils.py"
"create a new feature branch and commit"
```

## Providers

### Ollama (Local) - Default

- **Free** and **private**
- Runs on your machine
- No internet needed (after model download)
- Models: `qwen2.5:7b`, `llama3.2:3b`, `codellama:7b`

### OpenRouter (Cloud)

- Access GPT-4, Claude, Llama, and more
- Some **free models** (DeepSeek)
- Get API key: https://openrouter.ai/keys

### HuggingFace (Cloud)

- Open-source models
- Get token: https://huggingface.co/settings/tokens

## Configuration File

Settings stored in:
- **macOS/Linux:** `~/.config/codeagent/config.json`
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
# Check if Ollama is running
ollama list

# Start Ollama
ollama serve

# Pull a model
ollama pull qwen2.5:7b
```

### API key issues

```bash
codeagent config --api-key
```

### Reset everything

```bash
codeagent config --reset
codeagent setup
```

### Windows PATH issues

If `codeagent` command not found after pip install:

```powershell
# Add Python Scripts to PATH
# Usually: C:\Users\<username>\AppData\Local\Programs\Python\Python3x\Scripts

# Or use:
python -m codeagent
```

## Development

```bash
git clone https://github.com/avirajbhatt99/codeagent.git
cd codeagent
pip3 install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/codeagent

# Linting
ruff check src/codeagent
```

## License

MIT License
