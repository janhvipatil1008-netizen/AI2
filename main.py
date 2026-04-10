"""
AI² Platform — Main Entry Point
Interactive CLI for the AI² adaptive learning platform.
"""

import os
import sys
from dotenv import load_dotenv
import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.rule import Rule
from rich.columns import Columns
from rich import print as rprint

from config import CareerTrack, TRACK_DISPLAY_NAMES, TRACK_TAGLINES, TOTAL_WEEKS
from context.session import SessionContext
from curriculum.syllabus import get_week, format_week_context
from orchestrator import Orchestrator

load_dotenv()
console = Console()


# ── Welcome Screen ────────────────────────────────────────────────────────────

def show_welcome() -> None:
    console.print()
    console.print(Panel.fit(
        "[bold cyan]AI²[/bold cyan]  [dim]·[/dim]  [white]AI for AI[/white]\n"
        "[dim]Your personalized path from learner to practitioner[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()


def show_week_summary(session: SessionContext) -> None:
    week = get_week(session.track.value, session.current_week)
    track_name = TRACK_DISPLAY_NAMES[session.track]

    task_preview = "  •  ".join(week.get("tasks", [])[:3])
    console.print(Panel(
        f"[bold]{track_name}[/bold]  ·  Week {session.current_week} of {TOTAL_WEEKS}\n\n"
        f"[cyan]{week['title']}[/cyan]\n\n"
        f"[dim]{week.get('description', '')}[/dim]\n\n"
        f"[dim]Upcoming:[/dim] {task_preview}",
        border_style="dim",
        title="[dim]Current Week[/dim]",
    ))
    console.print()


# ── Track Selection ───────────────────────────────────────────────────────────

def select_track() -> CareerTrack:
    console.print("[bold]Choose your career track:[/bold]\n")

    tracks = list(CareerTrack)
    for i, track in enumerate(tracks, 1):
        name    = TRACK_DISPLAY_NAMES[track]
        tagline = TRACK_TAGLINES[track]
        console.print(f"  [cyan]{i}[/cyan].  [bold]{name}[/bold]")
        console.print(f"       [dim]{tagline}[/dim]")
        console.print()

    while True:
        choice = Prompt.ask("Enter 1, 2, or 3", default="1")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(tracks):
                return tracks[idx]
        except ValueError:
            pass
        console.print("[red]Please enter 1, 2, or 3.[/red]")


# ── Help Text ─────────────────────────────────────────────────────────────────

def show_help() -> None:
    console.print(Panel(
        "[bold]Commands:[/bold]\n\n"
        "  [cyan]/next[/cyan]      Advance to the next week\n"
        "  [cyan]/week[/cyan]      Show current week details\n"
        "  [cyan]/progress[/cyan]  Show your progress summary\n"
        "  [cyan]/help[/cyan]      Show this help message\n"
        "  [cyan]/quit[/cyan]      Exit the platform\n\n"
        "[bold]How to interact:[/bold]\n\n"
        "  Just type naturally. The Orchestrator will route your message to:\n"
        "  • [cyan]Learning Coach[/cyan]  — questions, explanations, concepts\n"
        "  • [cyan]Practice Arena[/cyan] — exercises, quizzes, challenges\n"
        "  • [cyan]Idea Generator[/cyan] — project ideas, inspiration\n\n"
        "[dim]Examples:[/dim]\n"
        '  "What is prompt caching and why does it matter?"\n'
        '  "Quiz me on this week\'s key concepts"\n'
        '  "Give me project ideas related to RAG pipelines"',
        title="[dim]AI² Help[/dim]",
        border_style="dim",
    ))
    console.print()


# ── Command Handler ───────────────────────────────────────────────────────────

def handle_command(cmd: str, session: SessionContext) -> bool:
    """
    Handle slash commands. Returns True if a command was handled.
    """
    cmd = cmd.strip().lower()

    if cmd == "/help":
        show_help()
        return True

    if cmd == "/week":
        week = get_week(session.track.value, session.current_week)
        console.print()
        console.print(format_week_context(session.track.value, session.current_week))
        console.print()
        return True

    if cmd == "/progress":
        console.print()
        console.print(Panel(
            session.progress_summary(),
            title="[dim]Your Progress[/dim]",
            border_style="dim",
        ))
        console.print()
        return True

    if cmd == "/next":
        if session.advance_week():
            console.print()
            console.print(Rule(f"[cyan]Week {session.current_week}[/cyan]"))
            show_week_summary(session)
        else:
            console.print("[yellow]You've completed all 13 weeks. Congratulations![/yellow]")
            console.print()
        return True

    if cmd in ("/quit", "/exit", "/q"):
        console.print()
        console.print(Panel.fit(
            f"[cyan]Session complete.[/cyan]\n\n"
            f"[dim]{session.progress_summary()}[/dim]",
            border_style="dim",
        ))
        console.print()
        sys.exit(0)

    return False


# ── Main Loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY not set.[/red]")
        console.print("[dim]Copy .env.example to .env and add your key.[/dim]")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    show_welcome()
    track   = select_track()
    session = SessionContext(track=track)
    orch    = Orchestrator(client=client, session=session)

    console.print()
    console.print(Rule())
    console.print()
    track_name = TRACK_DISPLAY_NAMES[track]
    console.print(f"[bold]Welcome to the [cyan]{track_name}[/cyan] track.[/bold]")
    console.print()
    show_week_summary(session)
    show_help()

    # ── Conversation Loop ─────────────────────────────────────────────────────
    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            handle_command("/quit", session)
            break

        if not user_input:
            continue

        # Check for slash commands
        if user_input.startswith("/"):
            handle_command(user_input, session)
            continue

        # ── Process through Orchestrator ──────────────────────────────────
        console.print()
        with console.status("[dim]Thinking...[/dim]", spinner="dots"):
            try:
                response = orch.process(user_input)
            except anthropic.APIError as e:
                console.print(f"[red]API error: {e}[/red]")
                console.print("[dim]Please try again.[/dim]")
                console.print()
                continue
            except Exception as e:
                console.print(f"[red]Unexpected error: {e}[/red]")
                raise

        # Display response
        console.print(Panel(
            response,
            title=f"[dim]AI² · Week {session.current_week}[/dim]",
            border_style="cyan",
            padding=(1, 2),
        ))
        console.print()


if __name__ == "__main__":
    main()
