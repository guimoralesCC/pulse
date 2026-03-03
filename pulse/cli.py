"""Pulse PM — CLI entry point."""
from __future__ import annotations

import typer
from rich.console import Console

from pulse import db

app = typer.Typer(
    name="pulse",
    help="Your personal AI project manager — running in the terminal.",
    add_completion=False,
    no_args_is_help=False,
)
console = Console()

cfg_app = typer.Typer(help="Read and write config values.", no_args_is_help=True)
app.add_typer(cfg_app, name="config")


# ── Main commands ──────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    """Show the dashboard when no sub-command is given."""
    if ctx.invoked_subcommand is None:
        from pulse.analytics import show_dashboard
        db.init_db()
        show_dashboard()


@app.command()
def morning() -> None:
    """Start your morning meeting — plan your day."""
    from pulse.flows.morning import run_morning_meeting
    run_morning_meeting()


@app.command()
def checkin() -> None:
    """Quick check-in — what are you working on right now?"""
    from pulse.flows.checkin import run_checkin
    run_checkin()


@app.command()
def evening() -> None:
    """Evening review — close out your day."""
    from pulse.flows.evening import run_evening_meeting
    run_evening_meeting()


@app.command()
def projects() -> None:
    """Add, edit, or archive projects."""
    from pulse.flows.projects import manage_projects
    manage_projects()


@app.command()
def dashboard() -> None:
    """Show today's and this week's analytics dashboard."""
    from pulse.analytics import show_dashboard
    db.init_db()
    show_dashboard()


@app.command()
def ai() -> None:
    """Get an AI-generated summary of your week."""
    from pulse.ai import show_ai_summary
    show_ai_summary()


@app.command()
def timer(
    action: str = typer.Argument(..., help="start | stop | status"),
    project: str = typer.Option(None, "--project", "-p", help="Project name (for start)"),
) -> None:
    """Control the work timer. Actions: start, stop, status."""
    db.init_db()
    action = action.lower()

    if action == "status":
        s = db.get_active_session()
        if s:
            from pulse.flows.checkin import _elapsed
            console.print(f"\n  Timer running: [bold]{s['project_name']}[/bold] ({_elapsed(s['start_time'])})\n")
        else:
            console.print("\n  No active timer.\n")

    elif action == "stop":
        s = db.stop_active_session()
        if s:
            console.print(f"\n  [green]Timer stopped.[/green] Project: [bold]{s['project_id']}[/bold]\n")
        else:
            console.print("\n  No active timer to stop.\n")

    elif action == "start":
        projs = db.get_projects(active_only=True)
        if not projs:
            console.print("\n  [yellow]No active projects.[/yellow] Run [bold]pulse projects[/bold] first.\n")
            return
        if project:
            match = next((p for p in projs if p["name"].lower() == project.lower()), None)
            if not match:
                console.print(f"\n  [red]Project not found:[/red] {project}\n")
                return
            db.start_session(match["id"])
            console.print(f"\n  [green]Timer started:[/green] [bold]{match['name']}[/bold]\n")
        else:
            import questionary
            STYLE = questionary.Style([("pointer", "fg:#7c3aed bold"), ("highlighted", "fg:#7c3aed bold")])
            name = questionary.select(
                "Start timer for which project?",
                choices=[p["name"] for p in projs],
                style=STYLE,
            ).ask()
            if name:
                pid = next(p["id"] for p in projs if p["name"] == name)
                db.start_session(pid)
                console.print(f"\n  [green]Timer started:[/green] [bold]{name}[/bold]\n")
    else:
        console.print(f"\n  [red]Unknown action:[/red] {action}. Use start, stop, or status.\n")


@app.command()
def daemon() -> None:
    """Run the background scheduler (normally managed by launchd)."""
    from pulse.daemon import run_daemon
    run_daemon()


# ── Config sub-commands ────────────────────────────────────────────────────────

@cfg_app.command("get")
def config_get(key: str = typer.Argument(..., help="Config key to read")) -> None:
    """Print a config value."""
    db.init_db()
    val = db.get_config(key)
    if val:
        console.print(f"  {key} = {val}")
    else:
        console.print(f"  [dim](not set)[/dim]")


@cfg_app.command("set")
def config_set(
    key: str   = typer.Argument(..., help="Config key"),
    value: str = typer.Argument(..., help="Value to store"),
) -> None:
    """Set a config value."""
    db.init_db()
    db.set_config(key, value)
    console.print(f"  [green]✓[/green] {key} = {value}")


@cfg_app.command("list")
def config_list() -> None:
    """List all config values."""
    db.init_db()
    from pulse.db import get_conn
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM config ORDER BY key").fetchall()
    if not rows:
        console.print("  [dim]No config values set.[/dim]")
        return
    for row in rows:
        k = row["key"]
        v = row["value"]
        if "key" in k.lower() or "secret" in k.lower() or "token" in k.lower():
            v = v[:4] + "****"
        console.print(f"  {k} = {v}")
