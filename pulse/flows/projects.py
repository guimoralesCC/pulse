"""Project management flow."""
import questionary
from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich import box

from pulse import db

console = Console()

STYLE = questionary.Style([
    ("qmark",       "fg:#8b5cf6 bold"),
    ("question",    "bold"),
    ("answer",      "fg:#16a34a bold"),
    ("pointer",     "fg:#8b5cf6 bold"),
    ("highlighted", "fg:#8b5cf6 bold"),
    ("selected",    "fg:#16a34a"),
])


def manage_projects() -> None:
    db.init_db()
    while True:
        projects = db.get_projects(active_only=False)
        _print_projects(projects)

        action = questionary.select(
            "What would you like to do?",
            choices=[
                "Add a project",
                "Edit a project",
                "Archive a project",
                "Back",
            ],
            style=STYLE,
        ).ask()

        if action is None or action == "Back":
            break
        elif action == "Add a project":
            _add_project()
        elif action == "Edit a project":
            _edit_project(projects)
        elif action == "Archive a project":
            _archive_project(projects)


def _print_projects(projects) -> None:
    console.print()
    if not projects:
        console.print("  [dim]No projects yet.[/dim]\n")
        return

    t = Table(show_header=True, header_style="bold dim", box=box.SIMPLE, padding=(0, 2))
    t.add_column("#", justify="right", style="dim")
    t.add_column("Project",  style="bold")
    t.add_column("Category")
    t.add_column("Priority", justify="center")
    t.add_column("Goal / wk", justify="right")
    t.add_column("Status")

    for p in projects:
        goal = f"{p['weekly_goal_hrs']:.0f}h" if p["weekly_goal_hrs"] else "—"
        status = "[green]active[/green]" if p["active"] else "[dim]archived[/dim]"
        t.add_row(
            str(p["id"]),
            p["name"],
            p["category"] or "—",
            str(p["priority"]),
            goal,
            status,
        )

    console.print(t)


def _add_project() -> None:
    name = questionary.text("Project name:", style=STYLE).ask()
    if not name or not name.strip():
        return
    category = questionary.text("Category (optional):", style=STYLE).ask() or ""
    goal_str  = questionary.text("Weekly goal (hours, optional):", style=STYLE).ask() or "0"
    try:
        goal = float(goal_str)
    except ValueError:
        goal = 0.0
    priority = questionary.select(
        "Priority:",
        choices=["1 — highest", "2", "3 — normal", "4", "5 — lowest"],
        default="3 — normal",
        style=STYLE,
    ).ask()
    p = int(priority[0]) if priority else 3
    db.add_project(name.strip(), category.strip(), goal, p)
    console.print(f"\n  [green]✓[/green] Added [bold]{name.strip()}[/bold]\n")


def _edit_project(projects) -> None:
    active = [p for p in projects if p["active"]]
    if not active:
        console.print("  [dim]No active projects.[/dim]")
        return
    name = questionary.select(
        "Which project?",
        choices=[p["name"] for p in active],
        style=STYLE,
    ).ask()
    if not name:
        return
    project = next(p for p in active if p["name"] == name)

    new_name = questionary.text(f"Name [{project['name']}]:", style=STYLE).ask()
    new_cat  = questionary.text(f"Category [{project['category'] or ''}]:", style=STYLE).ask()
    new_goal = questionary.text(f"Weekly goal hrs [{project['weekly_goal_hrs']}]:", style=STYLE).ask()

    updates = {}
    if new_name and new_name.strip():
        updates["name"] = new_name.strip()
    if new_cat is not None:
        updates["category"] = new_cat.strip()
    if new_goal:
        try:
            updates["weekly_goal_hrs"] = float(new_goal)
        except ValueError:
            pass

    if updates:
        db.update_project(project["id"], **updates)
        console.print(f"\n  [green]✓[/green] Updated [bold]{name}[/bold]\n")


def _archive_project(projects) -> None:
    active = [p for p in projects if p["active"]]
    if not active:
        console.print("  [dim]No active projects to archive.[/dim]")
        return
    name = questionary.select(
        "Archive which project?",
        choices=[p["name"] for p in active],
        style=STYLE,
    ).ask()
    if not name:
        return
    confirm = questionary.confirm(f"Archive {name}?", default=False, style=STYLE).ask()
    if confirm:
        project = next(p for p in active if p["name"] == name)
        db.archive_project(project["id"])
        console.print(f"\n  [green]✓[/green] Archived [bold]{name}[/bold]\n")
