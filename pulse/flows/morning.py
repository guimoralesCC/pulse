"""Morning meeting flow — plan your day."""
import json
from datetime import date

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from pulse import db

console = Console()

STYLE = questionary.Style([
    ("qmark",       "fg:#7c3aed bold"),
    ("question",    "bold"),
    ("answer",      "fg:#16a34a bold"),
    ("pointer",     "fg:#7c3aed bold"),
    ("highlighted", "fg:#7c3aed bold"),
    ("selected",    "fg:#16a34a"),
    ("separator",   "fg:#6b7280"),
    ("instruction", "fg:#6b7280"),
])


def run_morning_meeting() -> None:
    db.init_db()
    today = date.today()
    day_str = today.strftime("%A, %B %-d")

    console.print()
    console.print(Panel(
        Text(f"  GOOD MORNING — {day_str}  ", justify="center", style="bold white"),
        style="bold yellow",
        padding=(0, 2),
    ))
    console.print()

    # ── check if already done today ───────────────────────────────────────────
    review = db.get_or_create_daily_review()
    if review["top_projects"]:
        redo = questionary.confirm(
            "You already ran your morning meeting today. Run it again?",
            default=False,
            style=STYLE,
        ).ask()
        if not redo:
            console.print("[dim]Skipped. Have a great day.[/dim]")
            return

    # ── select projects ───────────────────────────────────────────────────────
    projects = db.get_projects(active_only=True)

    if not projects:
        console.print("[yellow]No projects yet.[/yellow] Let's add one first.\n")
        name = questionary.text("Project name:", style=STYLE).ask()
        if name:
            db.add_project(name)
            projects = db.get_projects(active_only=True)
        if not projects:
            return

    project_choices = [p["name"] for p in projects] + ["+ Add a new project"]

    selected_names = questionary.checkbox(
        "Which projects are you focusing on today?",
        choices=project_choices,
        style=STYLE,
    ).ask()

    if not selected_names:
        console.print("[dim]No projects selected. Morning meeting skipped.[/dim]")
        return

    # handle new project creation
    if "+ Add a new project" in selected_names:
        selected_names.remove("+ Add a new project")
        new_name = questionary.text("New project name:", style=STYLE).ask()
        if new_name and new_name.strip():
            db.add_project(new_name.strip())
            selected_names.append(new_name.strip())
            projects = db.get_projects(active_only=True)

    if not selected_names:
        console.print("[dim]No projects selected. Morning meeting skipped.[/dim]")
        return

    # ── done criteria ─────────────────────────────────────────────────────────
    console.print()
    done_criteria = questionary.text(
        "What counts as \"done\" today?",
        style=STYLE,
    ).ask() or ""

    # ── time allocation ───────────────────────────────────────────────────────
    console.print()
    console.print("[dim]Time allocation (hours planned per project)[/dim]")
    time_allocation = {}
    for name in selected_names:
        hours = questionary.text(
            f"  {name} — hours planned:",
            validate=lambda v: True if v == "" or _is_number(v) else "Enter a number",
            style=STYLE,
        ).ask()
        time_allocation[name] = float(hours) if hours and _is_number(hours) else 0.0

    # ── save ──────────────────────────────────────────────────────────────────
    db.update_daily_review(
        today.isoformat(),
        top_projects=json.dumps(selected_names),
        done_criteria=done_criteria,
        time_allocation=json.dumps(time_allocation),
    )

    console.print()
    console.print(Rule(style="green"))
    console.print(f"[bold green]  Plan saved.[/bold green]  Today's focus: [bold]{', '.join(selected_names)}[/bold]")
    if done_criteria:
        console.print(f"  Done when: [italic]{done_criteria}[/italic]")
    console.print(Rule(style="green"))
    console.print()


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False
