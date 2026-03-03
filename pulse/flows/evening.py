"""Evening review flow — close out the day."""
import json
from datetime import date

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.table import Table

from pulse import db

console = Console()

STYLE = questionary.Style([
    ("qmark",       "fg:#f59e0b bold"),
    ("question",    "bold"),
    ("answer",      "fg:#16a34a bold"),
    ("pointer",     "fg:#f59e0b bold"),
    ("highlighted", "fg:#f59e0b bold"),
    ("selected",    "fg:#16a34a"),
    ("separator",   "fg:#6b7280"),
    ("instruction", "fg:#6b7280"),
])

STATUS_ICON = {
    "done":        "✅",
    "partial":     "🔄",
    "blocked":     "🚫",
    "not_started": "⬜",
}


def run_evening_meeting() -> None:
    db.init_db()
    today = date.today()
    day_str = today.strftime("%A, %B %-d")

    # stop any running timer
    session = db.stop_active_session()
    if session:
        console.print(f"\n  [dim]Timer stopped automatically.[/dim]")

    console.print()
    console.print(Panel(
        Text(f"  EVENING REVIEW — {day_str}  ", justify="center", style="bold white"),
        style="bold yellow",
        padding=(0, 2),
    ))
    console.print()

    # ── show today's check-ins ────────────────────────────────────────────────
    checkins = db.get_today_checkins()
    hours    = db.get_hours_today()
    projects = {p["id"]: p for p in db.get_projects(active_only=False)}

    if checkins:
        t = Table(show_header=True, header_style="bold dim", box=None, padding=(0, 2))
        t.add_column("Project",    style="bold")
        t.add_column("Last status")
        t.add_column("Check-ins",  justify="right")
        t.add_column("Hours",      justify="right")

        # aggregate per project
        by_project: dict = {}
        for c in checkins:
            pid = c["project_id"]
            if pid not in by_project:
                by_project[pid] = {"name": c["project_name"], "count": 0, "last_status": "", "last_note": ""}
            by_project[pid]["count"] += 1
            by_project[pid]["last_status"] = c["status"]
            by_project[pid]["last_note"]   = c["note"] or ""

        for pid, info in by_project.items():
            icon = STATUS_ICON.get(info["last_status"], "")
            hrs  = hours.get(pid, 0.0)
            hrs_str = f"{hrs:.1f}h" if hrs else "—"
            t.add_row(info["name"], f"{icon} {info['last_status'].replace('_',' ')}", str(info["count"]), hrs_str)

        console.print("  [bold]Today's activity:[/bold]")
        console.print(t)
        console.print()
    else:
        console.print("  [dim]No check-ins recorded today.[/dim]\n")

    # ── questions ─────────────────────────────────────────────────────────────
    what_moved = questionary.text(
        "What moved today?",
        style=STYLE,
    ).ask() or ""

    what_blocked = questionary.text(
        "What got blocked or unfinished?",
        style=STYLE,
    ).ask() or ""

    tomorrow_first = questionary.text(
        "What is tomorrow's first task?",
        style=STYLE,
    ).ask() or ""

    # ── save ──────────────────────────────────────────────────────────────────
    db.update_daily_review(
        today.isoformat(),
        what_moved=what_moved,
        what_blocked=what_blocked,
        tomorrow_first=tomorrow_first,
    )

    # ── AI summary (optional) ─────────────────────────────────────────────────
    try:
        from pulse.ai import generate_daily_summary
        console.print("\n  [dim]Generating AI summary…[/dim]")
        summary = generate_daily_summary(today.isoformat(), checkins, hours, projects)
        if summary:
            db.update_daily_review(today.isoformat(), ai_summary=summary)
            console.print()
            console.print(Panel(summary, title="AI Summary", style="dim", padding=(1, 2)))
    except Exception:
        pass  # AI is optional

    console.print()
    console.print(Rule(style="yellow"))
    console.print("  [bold yellow]Day closed.[/bold yellow]  See you tomorrow.")
    if tomorrow_first:
        console.print(f"  Tomorrow starts with: [italic]{tomorrow_first}[/italic]")
    console.print(Rule(style="yellow"))
    console.print()
