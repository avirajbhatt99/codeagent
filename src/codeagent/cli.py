"""
Command-line interface for CodeAgent using Typer.

Modern, type-hint based CLI with auto-completion support.
"""

import logging
import os
import sys
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

from codeagent import __version__
from codeagent.config.manager import get_config_manager, StoredConfig
from codeagent.core.agent import Agent
from codeagent.core.exceptions import (
    CodeAgentError,
    MaxIterationsError,
    ProviderConfigError,
)
from codeagent.providers.factory import create_provider
from codeagent.providers.base import LLMProvider
from codeagent.tools import create_default_registry
from codeagent.utils.console import Console as AgentConsole


# Initialize Typer app
app = typer.Typer(
    name="codeagent",
    help="AI-powered coding assistant CLI",
    add_completion=True,
    no_args_is_help=False,
)

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

RECOMMENDED_OLLAMA_MODELS = [
    ("qwen2.5:7b", "4.7GB", "Best for coding, recommended"),
    ("qwen2.5:3b", "1.9GB", "Lightweight, fast"),
    ("llama3.2:3b", "2.0GB", "Good general purpose"),
    ("codellama:7b", "3.8GB", "Code-focused"),
    ("mistral:7b", "4.1GB", "Strong reasoning"),
    ("deepseek-coder-v2:16b", "8.9GB", "Advanced coding, needs more RAM"),
]

PROVIDERS_INFO = {
    "ollama": {
        "name": "Ollama (Local)",
        "description": "Run models locally. Free & private.",
        "needs_key": False,
        "default_model": None,
        "models": [],
    },
    "openrouter": {
        "name": "OpenRouter (Cloud)",
        "description": "Access many models via API.",
        "needs_key": True,
        "key_url": "https://openrouter.ai/keys",
        "default_model": "deepseek/deepseek-chat",
        "models": [
            "deepseek/deepseek-chat",
            "deepseek/deepseek-coder",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "meta-llama/llama-3.1-70b-instruct",
        ],
    },
    "huggingface": {
        "name": "HuggingFace (Cloud)",
        "description": "HuggingFace Inference API.",
        "needs_key": True,
        "key_url": "https://huggingface.co/settings/tokens",
        "default_model": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "models": [
            "Qwen/Qwen2.5-Coder-32B-Instruct",
            "meta-llama/Meta-Llama-3.1-70B-Instruct",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_ollama_models() -> list[str]:
    """Fetch available models from Ollama."""
    try:
        import ollama
        response = ollama.list()
        models = [m.get("name", m.get("model", "")) for m in response.get("models", [])]
        return [m for m in models if m]
    except Exception:
        return []


def is_ollama_running() -> bool:
    """Check if Ollama server is running."""
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


def pull_ollama_model(model_name: str) -> bool:
    """Pull/download a model from Ollama."""
    try:
        import ollama

        console.print(f"\n[cyan]Downloading {model_name}...[/cyan]")
        console.print("[dim]This may take a few minutes.[/dim]\n")

        current_status = ""
        for progress in ollama.pull(model_name, stream=True):
            status = progress.get("status", "")
            if status != current_status:
                current_status = status
                if any(x in status.lower() for x in ["pulling", "verifying", "writing"]):
                    console.print(f"  [dim]{status}[/dim]")
                elif status == "success":
                    console.print(f"\n[green]✓[/green] Downloaded {model_name}")
                    return True
        return True
    except Exception as e:
        console.print(f"\n[red]✗[/red] Failed: {e}")
        return False


def get_or_create_config() -> StoredConfig:
    """Get existing config or run setup wizard."""
    manager = get_config_manager()
    if not manager.exists() or not manager.is_configured():
        return run_setup_wizard()
    return manager.load()


def create_provider_from_config(config: StoredConfig) -> LLMProvider:
    """Create an LLM provider from config."""
    api_key = None
    if config.provider == "openrouter":
        api_key = config.openrouter_api_key
    elif config.provider == "huggingface":
        api_key = config.huggingface_api_key

    return create_provider(
        provider=config.provider,
        model=config.model,
        api_key=api_key,
        host=config.ollama_host if config.provider == "ollama" else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Setup Wizard
# ─────────────────────────────────────────────────────────────────────────────

def run_setup_wizard() -> StoredConfig:
    """Run the interactive setup wizard."""
    console.print("\n[bold cyan]Welcome to CodeAgent![/bold cyan]\n")

    # Step 1: Provider
    console.print("[bold]Step 1: Choose provider[/bold]\n")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Option", style="cyan bold")
    table.add_column("Provider")
    table.add_column("Description", style="dim")
    table.add_row("1", "Ollama (Local)", "Free, private, runs locally")
    table.add_row("2", "OpenRouter", "Cloud API, many models")
    table.add_row("3", "HuggingFace", "Cloud API, open models")
    console.print(table)
    console.print()

    choice = Prompt.ask("Select", choices=["1", "2", "3"], default="1")
    provider_map = {"1": "ollama", "2": "openrouter", "3": "huggingface"}
    provider = provider_map[choice]
    provider_info = PROVIDERS_INFO[provider]
    console.print(f"\n[green]✓[/green] {provider_info['name']}\n")

    # Step 2: API Key
    api_key = None
    if provider_info["needs_key"]:
        console.print("[bold]Step 2: API Key[/bold]\n")
        console.print(f"Get key: [link]{provider_info['key_url']}[/link]\n")

        while True:
            api_key = Prompt.ask("API Key", password=True)
            if not api_key:
                console.print("[red]API key required.[/red]")
                sys.exit(1)

            console.print("[dim]Validating...[/dim]")
            try:
                if provider == "openrouter":
                    from codeagent.providers.openrouter import OpenRouterProvider
                    OpenRouterProvider(api_key=api_key).validate_api_key()
                console.print("[green]✓[/green] Valid\n")
                break
            except ProviderConfigError as e:
                console.print(f"[red]✗ {e.reason}[/red]")
                if not Confirm.ask("Try again?", default=True):
                    sys.exit(1)
            except Exception as e:
                console.print(f"[yellow]⚠ {e}[/yellow]\n")
                break
    else:
        console.print("[bold]Step 2: Checking Ollama...[/bold]\n")
        if not is_ollama_running():
            console.print("[yellow]⚠ Ollama not running![/yellow]")
            console.print("[dim]Start: ollama serve[/dim]\n")
            if not Confirm.ask("Continue?"):
                sys.exit(0)
        else:
            console.print("[green]✓[/green] Ollama running\n")

    # Step 3: Model
    console.print("[bold]Step 3: Choose model[/bold]\n")

    if provider == "ollama":
        models = get_ollama_models()
        if models:
            for i, m in enumerate(models[:8], 1):
                console.print(f"  {i}. {m}")
            console.print(f"  d. Download new model")
            console.print(f"  0. Enter custom\n")

            choice = Prompt.ask("Select", default="1")
            if choice.lower() == "d":
                model = select_and_download_model()
            elif choice == "0":
                model = Prompt.ask("Model name")
            elif choice.isdigit() and 1 <= int(choice) <= len(models):
                model = models[int(choice) - 1]
            else:
                model = models[0]
        else:
            console.print("[yellow]No models installed.[/yellow]\n")
            model = select_and_download_model()
    else:
        models = provider_info["models"]
        for i, m in enumerate(models[:6], 1):
            marker = " [dim](recommended)[/dim]" if i == 1 else ""
            console.print(f"  {i}. {m}{marker}")
        console.print()

        choice = Prompt.ask("Select", default="1")
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            model = models[int(choice) - 1]
        else:
            model = provider_info["default_model"]

    console.print(f"\n[green]✓[/green] Model: {model}\n")

    # Save config
    config = StoredConfig(
        provider=provider,
        model=model,
        openrouter_api_key=api_key if provider == "openrouter" else None,
        huggingface_api_key=api_key if provider == "huggingface" else None,
    )
    manager = get_config_manager()
    manager.save(config)

    console.print("[bold green]Setup complete![/bold green]\n")
    return config


def select_and_download_model() -> str:
    """Select and download an Ollama model."""
    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("#", style="cyan bold", width=3)
    table.add_column("Model")
    table.add_column("Size", style="yellow")
    table.add_column("Description", style="dim")

    for i, (name, size, desc) in enumerate(RECOMMENDED_OLLAMA_MODELS, 1):
        table.add_row(str(i), name, size, desc)
    console.print(table)
    console.print()

    choice = Prompt.ask("Select", default="1")
    if choice.isdigit() and 1 <= int(choice) <= len(RECOMMENDED_OLLAMA_MODELS):
        model = RECOMMENDED_OLLAMA_MODELS[int(choice) - 1][0]
    else:
        model = RECOMMENDED_OLLAMA_MODELS[0][0]

    installed = get_ollama_models()
    if model in installed:
        console.print(f"[green]✓[/green] Already installed")
        return model

    if Confirm.ask(f"Download {model}?", default=True):
        if pull_ollama_model(model):
            return model
    return Prompt.ask("Enter model", default="qwen2.5:7b")


# ─────────────────────────────────────────────────────────────────────────────
# Welcome Screen
# ─────────────────────────────────────────────────────────────────────────────

def print_welcome(model: str, path: str) -> None:
    """Print welcome screen."""
    home = os.path.expanduser("~")
    display_path = path.replace(home, "~") if path.startswith(home) else path

    console.print()
    console.print("[bold bright_magenta]  ◆ CodeAgent[/bold bright_magenta]", end="")
    console.print(f"  [dim]v{__version__}[/dim]")
    console.print()
    console.print(f"  [dim]Model:[/dim]  [bright_cyan]{model}[/bright_cyan]")
    console.print(f"  [dim]Path:[/dim]   [white]{display_path}[/white]")
    console.print()
    console.print("  [dim]─────────────────────────────────────[/dim]")
    console.print()
    console.print("  [dim]Try:[/dim] [white]\"read my code\"[/white]  │  [white]\"fix bug\"[/white]  │  [white]\"run tests\"[/white]")
    console.print()
    console.print("  [dim]Commands:[/dim] [yellow]exit[/yellow]  [yellow]clear[/yellow]  [yellow]help[/yellow]")
    console.print()
    console.print("  [dim]─────────────────────────────────────[/dim]")
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# Main Session
# ─────────────────────────────────────────────────────────────────────────────

def start_session(verbose: bool = False) -> None:
    """Start the interactive chat session."""
    try:
        config = get_or_create_config()
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        return

    try:
        provider = create_provider_from_config(config)
    except ProviderConfigError as e:
        console.print(f"[red]Config error:[/red] {e.message}")
        console.print("[dim]Run: codeagent setup[/dim]")
        return
    except Exception as e:
        console.print(f"[red]Connection failed:[/red] {e}")
        if config.provider == "ollama":
            console.print("[dim]Is Ollama running? Try: ollama serve[/dim]")
        return

    tools = create_default_registry()
    working_dir = os.getcwd()
    agent_console = AgentConsole()

    agent = Agent(
        provider=provider,
        tools=tools,
        working_dir=working_dir,
        max_iterations=config.max_iterations,
        on_tool_start=lambda tc: agent_console.tool_start(tc.name, tc.arguments),
        on_tool_end=lambda tr: agent_console.tool_result(tr.content, tr.is_error),
    )

    print_welcome(provider.model, working_dir)

    # Main loop
    while True:
        try:
            user_input = agent_console.user_prompt()

            if not user_input.strip():
                continue

            cmd = user_input.strip().lower()
            if cmd in ("exit", "quit", "q"):
                break
            elif cmd == "clear":
                agent.reset()
                console.print("[dim]History cleared[/dim]")
                continue
            elif cmd == "help":
                console.print("[dim]exit[/dim]   quit")
                console.print("[dim]clear[/dim]  reset history")
                console.print("[dim]help[/dim]   this message")
                console.print()
                continue

            agent_console.start_thinking()

            try:
                first_chunk = True
                for chunk in agent.stream(user_input):
                    if first_chunk:
                        agent_console.assistant_start()
                        first_chunk = False
                    agent_console.assistant_stream(chunk)
                agent_console.assistant_end()
            except MaxIterationsError:
                agent_console.stop_thinking()
                agent_console.error("Max iterations reached.")
            except CodeAgentError as e:
                agent_console.stop_thinking()
                agent_console.error(f"Error: {e.message}")

        except KeyboardInterrupt:
            console.print()
            continue
        except EOFError:
            break


# ─────────────────────────────────────────────────────────────────────────────
# CLI Commands
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option("--version", "-v", help="Show version")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-V", help="Debug logging")] = False,
) -> None:
    """AI-powered coding assistant. Run without arguments to start."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(name)s: %(message)s")
        console.print("[dim]Debug logging enabled[/dim]\n")

    if version:
        console.print(f"CodeAgent v{__version__}")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        start_session(verbose=verbose)


@app.command()
def setup() -> None:
    """Run the setup wizard."""
    run_setup_wizard()


@app.command()
def pull(
    model_name: Annotated[Optional[str], typer.Argument(help="Model to download")] = None,
) -> None:
    """Download an Ollama model."""
    if not is_ollama_running():
        console.print("[red]Ollama not running![/red]")
        console.print("[dim]Start: ollama serve[/dim]")
        raise typer.Exit(1)

    if model_name:
        pull_ollama_model(model_name)
    else:
        model = select_and_download_model()
        if Confirm.ask(f"Set {model} as default?", default=True):
            manager = get_config_manager()
            if manager.exists():
                cfg = manager.load()
                cfg.model = model
                cfg.provider = "ollama"
                manager.save(cfg)
                console.print(f"[green]✓[/green] Default: {model}")


@app.command("config")
def config_cmd(
    show: Annotated[bool, typer.Option("--show", "-s", help="Show config")] = False,
    provider: Annotated[Optional[str], typer.Option("--provider", "-p", help="Set provider")] = None,
    model: Annotated[Optional[str], typer.Option("--model", "-m", help="Set model")] = None,
    api_key: Annotated[bool, typer.Option("--api-key", "-k", help="Update API key")] = False,
    reset: Annotated[bool, typer.Option("--reset", help="Reset config")] = False,
) -> None:
    """View or modify configuration."""
    manager = get_config_manager()

    if reset:
        if Confirm.ask("Reset configuration?"):
            manager.reset()
            console.print("[green]✓[/green] Reset")
        return

    if not manager.exists():
        console.print("No config. Running setup...\n")
        run_setup_wizard()
        return

    cfg = manager.load()

    if provider:
        if provider not in PROVIDERS_INFO:
            console.print(f"[red]Unknown provider: {provider}[/red]")
            raise typer.Exit(1)

        old_provider = cfg.provider
        cfg.provider = provider

        if provider == "ollama":
            models = get_ollama_models()
            cfg.model = models[0] if models else "qwen2.5:7b"
        else:
            cfg.model = PROVIDERS_INFO[provider]["default_model"]

        console.print(f"[green]✓[/green] Provider: {provider}")
        console.print(f"[green]✓[/green] Model: {cfg.model}")

        if provider in ("openrouter", "huggingface") and old_provider == "ollama":
            console.print(f"\n[yellow]API key required[/yellow]")
            new_key = Prompt.ask("API key", password=True)
            if provider == "openrouter":
                cfg.openrouter_api_key = new_key
            else:
                cfg.huggingface_api_key = new_key

    if model:
        cfg.model = model
        console.print(f"[green]✓[/green] Model: {model}")

    if api_key:
        if cfg.provider == "ollama":
            console.print("[yellow]Ollama doesn't need API key[/yellow]")
        else:
            new_key = Prompt.ask(f"API key for {cfg.provider}", password=True)
            if cfg.provider == "openrouter":
                cfg.openrouter_api_key = new_key
            else:
                cfg.huggingface_api_key = new_key
            console.print("[green]✓[/green] API key updated")

    if provider or model or api_key:
        manager.save(cfg)

    if show or not (provider or model or api_key or reset):
        console.print("\n[bold]Configuration[/bold]\n")
        table = Table(show_header=False, box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value")
        table.add_row("Provider", cfg.provider)
        table.add_row("Model", cfg.model or "(default)")
        table.add_row("Config", str(manager.config_file))

        if cfg.provider == "openrouter":
            table.add_row("API Key", "✓ Set" if cfg.openrouter_api_key else "✗ Not set")
        elif cfg.provider == "huggingface":
            table.add_row("API Key", "✓ Set" if cfg.huggingface_api_key else "✗ Not set")

        console.print(table)
        console.print()


@app.command()
def models(
    provider: Annotated[Optional[str], typer.Option("--provider", "-p", help="Provider")] = None,
) -> None:
    """List available models."""
    manager = get_config_manager()
    cfg = manager.load() if manager.exists() else StoredConfig()
    target = provider or cfg.provider

    if target == "ollama":
        console.print("\n[bold]Ollama Models:[/bold]\n")
        models_list = get_ollama_models()
        if not models_list:
            console.print("[yellow]No models installed[/yellow]")
            console.print("[dim]Download: codeagent pull[/dim]")
        else:
            for i, m in enumerate(models_list, 1):
                marker = " [cyan](current)[/cyan]" if m == cfg.model else ""
                console.print(f"  {i}. {m}{marker}")
    else:
        info = PROVIDERS_INFO.get(target)
        if not info:
            console.print(f"[red]Unknown provider: {target}[/red]")
            return
        console.print(f"\n[bold]{info['name']} Models:[/bold]\n")
        for i, m in enumerate(info["models"], 1):
            marker = " [cyan](current)[/cyan]" if m == cfg.model else ""
            console.print(f"  {i}. {m}{marker}")

    console.print(f"\n[dim]Change: codeagent config --model <name>[/dim]\n")


# Entry point
def main_entry() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main_entry()
