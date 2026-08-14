"""utils/logging_utils.py — affichage console lisible de la progression."""

from rich.console import Console
from rich.panel import Panel

console = Console()


def log_step(agent_name: str, message: str) -> None:
    console.print(Panel(message, title=f"[bold cyan]{agent_name}[/bold cyan]",
                         border_style="cyan"))


def log_warning(agent_name: str, message: str) -> None:
    console.print(f"[yellow]⚠ {agent_name}: {message}[/yellow]")


def log_error(agent_name: str, message: str) -> None:
    console.print(f"[bold red]✖ {agent_name}: {message}[/bold red]")


def log_success(message: str) -> None:
    console.print(f"[bold green]✔ {message}[/bold green]")
