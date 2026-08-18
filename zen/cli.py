"""
ZEN Interactive Command Line Interface and Shell.
"""

import asyncio
import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from zen.config.settings import get_settings
from zen.core.orchestrator import ZenOrchestrator
from zen.core.session import SessionContext
from zen.voice.stt.groq_whisper import STTUnavailableError

# Reconfigure stdout/stderr for Unicode safety on legacy Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(highlight=False)


def print_banner() -> None:
    """Displays the ZEN stylized banner."""
    banner_text = (
        "[bold cyan]====== ZEN: AI COMPUTER ASSISTANT ======[/bold cyan]\n"
        "[bold white]Personal Voice-First AI Assistant for Windows[/bold white]\n"
        "[dim]Engineered with Python 3.14 Standards | Modular & Safe[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan"))


async def cli_confirmation_callback(tool_name: str, prompt_text: str, params: dict) -> bool:
    """Prompt user interactively in terminal for tool confirmation."""
    console.print(f"\n[bold yellow]⚠️  Security Confirmation Required[/bold yellow]")
    console.print(f"Tool: [bold cyan]{tool_name}[/bold cyan]")
    console.print(f"Details: {prompt_text}")
    return Confirm.ask("Do you authorize this action?", default=False)


async def voice_listen(orchestrator: ZenOrchestrator) -> str | None:
    """
    Capture one spoken utterance and return the transcribed text.

    Returns:
        Transcribed text string, or ``None`` if capture timed out silently.

    Raises:
        STTUnavailableError: Propagated to the caller so it can display a
            friendly error and optionally fall back to text input.
    """
    console.print("\n[bold green]🎤 Listening...[/bold green] (speak now)")
    text = await orchestrator.voice.listen_and_transcribe(timeout=8.0)
    if text:
        console.print(f"[dim]You said:[/dim] [italic]{text}[/italic]")
    return text or None


async def interactive_chat(orchestrator: ZenOrchestrator, voice_mode: bool = False) -> None:
    """Interactive conversational terminal session (text or push-to-talk voice)."""
    session = SessionContext(is_voice_mode=voice_mode)

    if voice_mode:
        console.print(
            Panel(
                "[bold green]🎤 Voice Mode Active[/bold green]\n"
                "[dim]Speak your message after the prompt. Say 'exit' or press Ctrl+C to quit.[/dim]",
                border_style="green",
            )
        )
    else:
        console.print("[dim]Type your message or command (type '/help' or 'exit' to quit):[/dim]\n")

    while True:
        try:
            # ── Input ──────────────────────────────────────────────────────────
            if voice_mode:
                try:
                    user_input = await voice_listen(orchestrator)
                    if user_input is None:
                        continue  # silence / timeout — keep listening
                except STTUnavailableError as exc:
                    console.print(
                        f"\n[bold red]⚠ Voice input unavailable:[/bold red] {exc}\n"
                        "[dim]Falling back to text input for this turn.[/dim]"
                    )
                    user_input = Prompt.ask("\n[bold green]You (text)[/bold green]").strip() or None
                    if user_input is None:
                        continue
            else:
                user_input = Prompt.ask("\n[bold green]You[/bold green]").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q", "/exit"):
                console.print("[bold cyan]Goodbye![/bold cyan]")
                break

            if user_input.lower() == "/help":
                table = Table(title="ZEN Commands")
                table.add_column("Command", style="cyan")
                table.add_column("Description", style="white")
                table.add_row("/diagnose", "Run instant PC performance diagnostic")
                table.add_row("/search <q>", "Search the internet via DuckDuckGo")
                table.add_row("/pref <key> <val>", "Save a persistent user preference")
                table.add_row("/corrections", "View all learned corrections")
                table.add_row("/tools", "List all registered tools")
                table.add_row("exit", "Exit ZEN")
                console.print(table)
                continue

            if user_input.lower() == "/diagnose":
                with console.status("[bold green]Running PC diagnostics...[/bold green]"):
                    res = await orchestrator.tools.execute("diagnose_pc_performance", {"top_process_count": 5})
                    console.print(Panel(res.output_message, title="PC Diagnostics", border_style="green"))
                continue

            if user_input.startswith("/search "):
                query = user_input[8:].strip()
                with console.status(f"[bold cyan]Searching web for '{query}'...[/bold cyan]"):
                    res = await orchestrator.tools.execute("web_search", {"query": query, "max_results": 5})
                    console.print(Panel(res.output_message, title=f"Web Search: {query}", border_style="cyan"))
                continue

            if user_input.startswith("/pref "):
                parts = user_input[6:].split(" ", 1)
                if len(parts) == 2:
                    orchestrator.memory.set_preference(parts[0], parts[1])
                    console.print(f"[bold green]Saved preference:[/bold green] {parts[0]} -> {parts[1]}")
                else:
                    console.print("[red]Usage: /pref <key> <value>[/red]")
                continue

            if user_input.lower() == "/corrections":
                corrs = orchestrator.memory.get_corrections()
                if not corrs:
                    console.print("[dim]No corrections recorded yet.[/dim]")
                else:
                    for c in corrs:
                        console.print(f"- [bold]{c.trigger_context}[/bold]: DON'T {c.mistake_description} -> DO {c.correct_behavior}")
                continue

            if user_input.lower() == "/tools":
                tools = orchestrator.tools.list_tools()
                table = Table(title="Registered Tools")
                table.add_column("Tool Name", style="cyan")
                table.add_column("Risk Level", style="yellow")
                table.add_column("Description", style="white")
                for t in tools:
                    table.add_row(t.name, t.risk_level, t.description)
                console.print(table)
                continue

            # Process conversational turn
            with console.status("[bold cyan]ZEN is thinking...[/bold cyan]", spinner="dots"):
                response = await orchestrator.process_user_message(
                    user_text=user_input,
                    session=session,
                    confirm_callback=cli_confirmation_callback,
                )

            console.print("\n[bold cyan]ZEN:[/bold cyan]")
            console.print(Markdown(response))

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold cyan]Session closed.[/bold cyan]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


def main() -> None:
    """Main CLI entrypoint."""
    print_banner()
    settings = get_settings()
    orchestrator = ZenOrchestrator(settings)

    args = sys.argv[1:]

    # Strip --voice flag before command dispatch
    voice_mode = "--voice" in args
    args = [a for a in args if a != "--voice"]

    command = args[0].lower() if args else "chat"

    if command == "chat":
        asyncio.run(interactive_chat(orchestrator, voice_mode=voice_mode))
    elif command == "voice":
        console.print("[bold green]Starting Hands-Free Voice Mode...[/bold green]")
        console.print(f"Wake phrase: [bold cyan]'{settings.wake_phrase}'[/bold cyan]")
        try:
            asyncio.run(orchestrator.run_voice_mode())
        except KeyboardInterrupt:
            console.print("\n[dim]Voice mode stopped.[/dim]")
    elif command == "diagnose":
        res = asyncio.run(orchestrator.tools.execute("diagnose_pc_performance", {"top_process_count": 5}))
        console.print(Panel(res.output_message, title="PC Diagnostics", border_style="green"))
    elif command == "info":
        table = Table(title="ZEN Configuration & Health")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("AI Provider", settings.ai_provider)
        table.add_row("AI Model", settings.ai_model)
        table.add_row("Voice Engine", settings.voice_engine)
        table.add_row("Voice Name", settings.voice_name)
        table.add_row("Workspace", str(settings.workspace_path))
        table.add_row("Data Directory", str(settings.data_path))
        console.print(table)
    else:
        # Treat as one-off direct prompt
        query = " ".join(args)
        console.print(f"[bold green]User:[/bold green] {query}")
        response = asyncio.run(orchestrator.process_user_message(query, confirm_callback=cli_confirmation_callback))
        console.print("\n[bold cyan]ZEN:[/bold cyan]")
        console.print(Markdown(response))


if __name__ == "__main__":
    main()
