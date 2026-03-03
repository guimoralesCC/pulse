"""Periodic check-in flow — quick status update."""
import json
from datetime import date, datetime

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule

from pulse import db

console = Console()

STYLE = questionary.Style([
    ("qmark",       "fg:#0ea5e9 bold"),
    ("question",    "bold"),
    ("answer",      "fg:#16a34a bold"),
    ("pointer",     "fg:#0ea5e9 bold"),
    ("highlighted", "fg:#0ea5e9 bold"),
    ("selected",    "fg:#16a34a"),
    ("separator",   "fg:#6b7280"),
    ("instruction", "fg:#6b7280"),
])

STATUS_CHOICES = [
    questionary.Choice("✅  Done",        value="done"),
    questionary.Choice("🔄  Partial",     value="partial"),
    questionary.Choice("🚫  Blocked",     value="blocked"),
    questionary.Choice("⬜  Not started", value="not_started"),
]

ENERGY_CHOICES = [
    questionary.Choice("5 — full energy", value=5),
    questionary.Choice("4 — pretty good",  value=4),
    questionary.Choice("3 — okay",         value=3),
    questionary.Choice("2 — low",          value=2),
    questionary.Choice("1 — running on fumes", value=1),
]


def run_checkin() -> None:
    db.init_db()
    now = datetime.now()
    time_str = now.strftime("%-I:%M %p")

    console.print()
    console.print(Panel(
        Text(f"  CHECK-IN — {time_str}  ", justify="center", style="bold white"),
        style="bold cyan",
        padding=(0, 2),
    ))
    console.print()

    # show active session if any
    active = db.get_active_session()
    if active:
        elapsed = _elapsed(active["start_time"])
        console.print(f"  [dim]Active timer:[/dim] [bold]{active['project_name']}[/bold] ({elapsed})")
        console.print()

    # ── select project ─────────────────────────────────────────────────────────
    projects = db.get_projects(active_only=True)
    if not projects:
        console.print("[yellow]No active projects.[/yellow] Run [bold]pulse morning[/bold] first.")
        return

    # prefer today's morning projects at top
    review = db.get_or_create_daily_review()
    today_names: list = json.loads(review["top_projects"] or "[]")
    priority_projects = [p for p in projects if p["name"] in today_names]
    other_projects    = [p for p in projects if p["name"] not in today_names]
    ordered = priority_projects + other_projects

    project_map = {p["name"]: p["id"] for p in ordered}
    project_name = questionary.select(
        "Which project are you on?",
        choices=list(project_map.keys()),
        style=STYLE,
    ).ask()

    if not project_name:
        return

    project_id = project_map[project_name]

    # ── status ─────────────────────────────────────────────────────────────────
    status = questionary.select(
        "Status?",
        choices=STATUS_CHOICES,
        style=STYLE,
    ).ask()

    if not status:
        return

    # ── blocked reason ─────────────────────────────────────────────────────────
    blocked_reason = ""
    if status == "blocked":
        blocked_reason = questionary.text(
            "What's blocking you?",
            style=STYLE,
        ).ask() or ""

    # ── note ───────────────────────────────────────────────────────────────────
    note = questionary.text(
        "Quick note (optional):",
        style=STYLE,
    ).ask() or ""

    # ── energy ─────────────────────────────────────────────────────────────────
    energy = questionary.select(
        "Energy level?",
        choices=ENERGY_CHOICES,
        default=ENERGY_CHOICES[2],
        style=STYLE,
    ).ask()

    if energy is None:
        energy = 3

    # ── timer ──────────────────────────────────────────────────────────────────
    console.print()
    if active and active["project_id"] == project_id:
        keep = questionary.confirm(
            f"Keep timer running on {project_name}?", default=True, style=STYLE
        ).ask()
        if not keep:
            db.stop_active_session()
            console.print(f"  [dim]Timer stopped.[/dim]")
    elif active:
        switch = questionary.confirm(
            f"Switch timer from [bold]{active['project_name']}[/bold] to [bold]{project_name}[/bold]?",
            default=True,
            style=STYLE,
        ).ask()
        if switch:
            db.start_session(project_id)
    else:
        start = questionary.confirm(
            f"Start timer for {project_name}?", default=True, style=STYLE
        ).ask()
        if start:
            db.start_session(project_id)

    # ── save ───────────────────────────────────────────────────────────────────
    db.save_checkin(project_id, status, note, energy, blocked_reason)

    console.print()
    console.print(Rule(style="cyan"))
    console.print(f"  [bold cyan]Saved.[/bold cyan]  {project_name} → [bold]{status.replace('_', ' ')}[/bold]")
    if note:
        console.print(f"  [italic dim]{note}[/italic dim]")
    console.print(Rule(style="cyan"))
    console.print()


def _elapsed(start_time: str) -> str:
    try:
        start = datetime.fromisoformat(start_time)
        delta = datetime.now() - start
        total = int(delta.total_seconds())
        h, m = divmod(total // 60, 60)
        if h:
            return f"{h}h {m}m"
        return f"{m}m"
    except Exception:
        return "?"
