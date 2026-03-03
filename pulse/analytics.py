"""Analytics dashboard — hours, check-ins, insights."""
import json
from collections import defaultdict
from datetime import date, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich.columns import Columns
from rich import box

from pulse import db

console = Console()

STATUS_ICON = {
    "done":        "✅",
    "partial":     "🔄",
    "blocked":     "🚫",
    "not_started": "⬜",
}


def show_dashboard() -> None:
    db.init_db()
    today = date.today()

    console.print()
    console.print(Panel(
        Text(f"  PULSE DASHBOARD — {today.strftime('%A, %B %-d, %Y')}  ", justify="center", style="bold white"),
        style="bold magenta",
        padding=(0, 2),
    ))

    _show_today(today)
    _show_week(today)
    _show_insights(today)
    console.print()


def _show_today(today: date) -> None:
    console.print(f"\n  [bold]TODAY[/bold]")
    console.print(Rule(style="dim"))

    checkins = db.get_today_checkins()
    hours    = db.get_hours_today()
    projects = {p["id"]: p for p in db.get_projects(active_only=False)}
    active   = db.get_active_session()

    if active:
        from pulse.flows.checkin import _elapsed
        console.print(
            f"  [dim]Timer running:[/dim] [bold]{active['project_name']}[/bold] ({_elapsed(active['start_time'])})\n"
        )

    if not checkins and not hours:
        console.print("  [dim]No activity yet today.[/dim]")

        review = db.get_or_create_daily_review()
        if review["top_projects"]:
            names = json.loads(review["top_projects"])
            console.print(f"  Planned: [bold]{', '.join(names)}[/bold]")
            if review["done_criteria"]:
                console.print(f"  Done when: [italic]{review['done_criteria']}[/italic]")
        return

    # aggregate per project
    by_project: dict = {}
    for c in checkins:
        pid = c["project_id"]
        if pid not in by_project:
            by_project[pid] = {
                "name": c["project_name"],
                "count": 0,
                "last_status": "",
                "notes": [],
                "blocked": 0,
            }
        by_project[pid]["count"] += 1
        by_project[pid]["last_status"] = c["status"]
        if c["note"]:
            by_project[pid]["notes"].append(c["note"])
        if c["status"] == "blocked":
            by_project[pid]["blocked"] += 1

    t = Table(show_header=True, header_style="bold dim", box=box.SIMPLE, padding=(0, 2))
    t.add_column("Project",    style="bold")
    t.add_column("Status")
    t.add_column("Check-ins",  justify="right")
    t.add_column("Hours",      justify="right", style="cyan")

    for pid, info in by_project.items():
        icon    = STATUS_ICON.get(info["last_status"], "")
        hrs     = hours.get(pid, 0.0)
        hrs_str = _fmt_hours(hrs)
        t.add_row(
            info["name"],
            f"{icon} {info['last_status'].replace('_', ' ')}",
            str(info["count"]),
            hrs_str,
        )

    # projects in plan but no check-in
    review = db.get_or_create_daily_review()
    today_plan = json.loads(review["top_projects"] or "[]")
    checked_in = {info["name"] for info in by_project.values()}
    for name in today_plan:
        if name not in checked_in:
            t.add_row(name, "[dim]⬜ no check-in[/dim]", "0", "—")

    console.print(t)

    # today's notes
    all_notes = []
    for info in by_project.values():
        for note in info["notes"]:
            all_notes.append(f"[dim]•[/dim] {note}")
    if all_notes:
        console.print("  [bold dim]Notes:[/bold dim]")
        for n in all_notes[-5:]:  # last 5
            console.print(f"    {n}")


def _show_week(today: date) -> None:
    console.print(f"\n  [bold]THIS WEEK[/bold]")
    console.print(Rule(style="dim"))

    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    hours_week = db.get_hours_week()
    checkins   = db.get_checkins_range(week_start.isoformat(), week_end.isoformat())
    projects   = {p["id"]: p for p in db.get_projects(active_only=True)}

    if not hours_week and not checkins:
        console.print("  [dim]No activity this week yet.[/dim]")
        return

    # check-ins per project this week
    checkin_count: dict = defaultdict(int)
    blocked_count: dict = defaultdict(int)
    for c in checkins:
        checkin_count[c["project_id"]] += 1
        if c["status"] == "blocked":
            blocked_count[c["project_id"]] += 1

    t = Table(show_header=True, header_style="bold dim", box=box.SIMPLE, padding=(0, 2))
    t.add_column("Project", style="bold")
    t.add_column("Hours",   justify="right", style="cyan")
    t.add_column("Goal",    justify="right", style="dim")
    t.add_column("Progress")
    t.add_column("Check-ins", justify="right")

    all_pids = set(hours_week.keys()) | set(checkin_count.keys())
    for pid in all_pids:
        p      = projects.get(pid)
        name   = p["name"] if p else f"Project {pid}"
        hrs    = hours_week.get(pid, 0.0)
        goal   = p["weekly_goal_hrs"] if p else 0.0
        bar    = _progress_bar(hrs, goal)
        goal_s = f"{goal:.0f}h" if goal else "—"
        t.add_row(name, _fmt_hours(hrs), goal_s, bar, str(checkin_count.get(pid, 0)))

    console.print(t)


def _show_insights(today: date) -> None:
    insights = []

    # stalled projects: active, no check-in in 2+ days
    projects = db.get_projects(active_only=True)
    two_days_ago = (today - timedelta(days=2)).isoformat()
    week_start   = (today - timedelta(days=today.weekday())).isoformat()

    checkins_week = db.get_checkins_range(week_start, today.isoformat())
    active_pids   = {c["project_id"] for c in checkins_week}
    recent_pids   = {
        c["project_id"] for c in checkins_week
        if c["timestamp"][:10] >= two_days_ago
    }

    for p in projects:
        pid = p["id"]
        if pid not in active_pids and p["weekly_goal_hrs"] > 0:
            insights.append(f"[yellow]⚠[/yellow]  [bold]{p['name']}[/bold] has no activity this week.")
        elif pid in active_pids and pid not in recent_pids:
            insights.append(f"[dim]○[/dim]  [bold]{p['name']}[/bold] hasn't had a check-in in 2+ days.")

    # blocked frequency
    blocked_counts: dict = defaultdict(int)
    for c in checkins_week:
        if c["status"] == "blocked":
            blocked_counts[c["project_id"]] += 1
    for pid, cnt in blocked_counts.items():
        if cnt >= 3:
            p = next((x for x in projects if x["id"] == pid), None)
            name = p["name"] if p else f"Project {pid}"
            insights.append(f"[red]🚫[/red]  [bold]{name}[/bold] has been blocked {cnt}x this week.")

    if insights:
        console.print(f"\n  [bold]INSIGHTS[/bold]")
        console.print(Rule(style="dim"))
        for line in insights:
            console.print(f"  {line}")


def _fmt_hours(hrs: float) -> str:
    if hrs < 0.017:
        return "—"
    h = int(hrs)
    m = int((hrs - h) * 60)
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def _progress_bar(actual: float, goal: float, width: int = 12) -> str:
    if not goal:
        return f"[dim]{_fmt_hours(actual)}[/dim]"
    ratio = min(actual / goal, 1.0)
    filled = int(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(ratio * 100)
    color = "green" if ratio >= 1.0 else "cyan" if ratio >= 0.5 else "yellow"
    return f"[{color}]{bar}[/{color}] [dim]{pct}%[/dim]"
