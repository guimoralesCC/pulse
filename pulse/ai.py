"""AI layer — supports OpenRouter (primary) and Anthropic (fallback)."""
import os
from collections import defaultdict
from datetime import date, timedelta

from rich.console import Console
from rich.panel import Panel

from pulse import db

console = Console()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


# ── Provider detection ─────────────────────────────────────────────────────────

def _get_openrouter_client():
    """Return an openai.OpenAI client pointed at OpenRouter, or None."""
    try:
        from openai import OpenAI
    except ImportError:
        return None, None

    api_key = os.environ.get("OPENROUTER_API_KEY") or db.get_config("openrouter_api_key")
    if not api_key:
        return None, None

    model = db.get_config("openrouter_model")
    if not model:
        return None, None
    client = OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://github.com/pulse-pm",
            "X-Title": "Pulse PM",
        },
    )
    return client, model


def _get_anthropic_client():
    """Return an anthropic.Anthropic client, or None."""
    try:
        import anthropic
    except ImportError:
        return None, None

    api_key = os.environ.get("ANTHROPIC_API_KEY") or db.get_config("anthropic_api_key")
    if not api_key:
        return None, None

    return anthropic.Anthropic(api_key=api_key), "claude-haiku-4-5-20251001"


def _complete(prompt: str, max_tokens: int = 400) -> str:
    """
    Call whichever provider is configured, return the response text.
    OpenRouter takes priority over Anthropic.
    """
    # try OpenRouter first
    client, model = _get_openrouter_client()
    if client:
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()

    # fall back to Anthropic
    client, model = _get_anthropic_client()
    if client:
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    return ""


def _provider_label() -> str:
    or_key = os.environ.get("OPENROUTER_API_KEY") or db.get_config("openrouter_api_key")
    if or_key:
        model = db.get_config("openrouter_model")
        return f"OpenRouter ({model})" if model else ""
    an_key = os.environ.get("ANTHROPIC_API_KEY") or db.get_config("anthropic_api_key")
    if an_key:
        return "Anthropic (claude-haiku)"
    return ""


# ── Public functions ───────────────────────────────────────────────────────────

def generate_daily_summary(
    day: str,
    checkins: list,
    hours: dict,
    projects: dict,
) -> str:
    lines = [f"Date: {day}", "Check-ins today:"]
    for c in checkins:
        line = f"  [{c['timestamp'][11:16]}] {c['project_name']}: {c['status']}"
        if c["note"]:
            line += f" — {c['note']}"
        if c["blocked_reason"]:
            line += f" (blocked: {c['blocked_reason']})"
        lines.append(line)

    lines.append("\nTime tracked:")
    for pid, hrs in hours.items():
        p = projects.get(pid)
        pname = p["name"] if p else f"Project {pid}"
        lines.append(f"  {pname}: {hrs:.1f}h")

    review = db.get_or_create_daily_review(day)
    if review["done_criteria"]:
        lines.append(f"\nDone criteria: {review['done_criteria']}")
    if review["what_moved"]:
        lines.append(f"What moved: {review['what_moved']}")
    if review["what_blocked"]:
        lines.append(f"What blocked: {review['what_blocked']}")
    if review["tomorrow_first"]:
        lines.append(f"Tomorrow first: {review['tomorrow_first']}")

    prompt = (
        "You are a personal productivity assistant. Based on this workday data, "
        "write a short, direct daily summary (3-5 sentences). Focus on what got done, "
        "any blockers, and one actionable suggestion for tomorrow. "
        "Under 100 words. Be direct, not cheerful.\n\n"
        f"Workday data:\n" + "\n".join(lines)
    )

    try:
        return _complete(prompt, max_tokens=200)
    except Exception:
        return ""


def show_ai_summary() -> None:
    db.init_db()

    label = _provider_label()
    if not label:
        console.print(
            "\n  [yellow]No AI provider configured (or missing model ID).[/yellow]\n\n"
            "  Option A — OpenRouter (both required):\n"
            "    [bold]pulse config set openrouter_api_key  sk-or-v1-...[/bold]\n"
            "    [bold]pulse config set openrouter_model    arcee-ai/trinity-large-preview[/bold]\n\n"
            "  Option B — Anthropic:\n"
            "    [bold]pulse config set anthropic_api_key   sk-ant-...[/bold]\n"
        )
        return

    today      = date.today()
    week_start = today - timedelta(days=today.weekday())
    checkins   = db.get_checkins_range(week_start.isoformat(), today.isoformat())
    projects   = {p["id"]: p for p in db.get_projects(active_only=False)}
    hours      = db.get_hours_week()

    by_project = defaultdict(lambda: {"checkins": 0, "blocked": 0, "statuses": [], "notes": []})
    for c in checkins:
        pid = c["project_id"]
        by_project[pid]["checkins"] += 1
        by_project[pid]["statuses"].append(c["status"])
        if c["status"] == "blocked":
            by_project[pid]["blocked"] += 1
        if c["note"]:
            by_project[pid]["notes"].append(c["note"])

    lines = [f"Week of {week_start.strftime('%B %-d')}:"]
    for pid, info in by_project.items():
        p = projects.get(pid)
        name = p["name"] if p else f"Project {pid}"
        hrs  = hours.get(pid, 0.0)
        lines.append(
            f"  {name}: {hrs:.1f}h, {info['checkins']} check-ins, "
            f"{info['blocked']} blocks, statuses={info['statuses']}"
        )

    prompt = (
        "You are a personal productivity assistant. Based on this week's data, provide:\n"
        "1. A 2-sentence week summary\n"
        "2. Top 2 observations (patterns, blockers, imbalances)\n"
        "3. Top 3 priorities for next week\n\n"
        "Be concise and direct. No filler phrases.\n\n"
        f"Week data:\n" + "\n".join(lines)
    )

    try:
        with console.status(f"[dim]Asking {label}...[/dim]"):
            result = _complete(prompt, max_tokens=400)

        console.print()
        console.print(Panel(
            result,
            title=f"AI Weekly Summary  [dim]({label})[/dim]",
            style="dim",
            padding=(1, 2),
        ))
        console.print()
    except Exception as e:
        console.print(f"\n  [red]AI error:[/red] {e}\n")
