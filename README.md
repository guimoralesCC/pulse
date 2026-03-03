# Pulse PM

A personal AI project manager that runs in your macOS terminal. Checks in with you throughout the day, tracks real work across projects, and helps you close the loop every morning and evening.

## How it works

- **Morning meeting** — pick your focus projects, set a done criteria, allocate time
- **Periodic check-ins** — every 90 min the daemon fires a notification and opens a terminal prompt
- **Evening review** — log what moved, what blocked, and tomorrow's first task
- **Dashboard** — hours per project, check-in history, weekly progress vs goals
- **AI summary** — daily and weekly summaries via OpenRouter or Anthropic

All data is stored locally in `~/.pulse_pm/pulse.db`. Nothing leaves your machine except AI API calls.

## Requirements

- macOS
- Python 3.11+

## Install

```bash
git clone https://github.com/YOUR_USERNAME/pulse-pm.git
cd pulse-pm
./install.sh
source ~/.zshrc
```

The installer:
- Creates a virtual environment at `~/.pulse_pm/venv`
- Installs the `pulse` CLI and adds it as a shell alias
- Registers a launchd agent that starts the daemon at login

## Daily workflow

```bash
pulse morning     # plan your day
pulse checkin     # quick status update (also runs automatically every 90 min)
pulse evening     # close out the day
pulse             # dashboard
```

## All commands

| Command | Description |
|---|---|
| `pulse` | Show dashboard |
| `pulse morning` | Morning meeting — plan your day |
| `pulse checkin` | Quick check-in — status, note, timer |
| `pulse evening` | Evening review — what moved, what blocked |
| `pulse projects` | Add, edit, or archive projects |
| `pulse timer start` | Start a work timer |
| `pulse timer stop` | Stop the running timer |
| `pulse timer status` | See active timer |
| `pulse ai` | AI weekly summary |
| `pulse config list` | Show all config values |
| `pulse config set KEY VALUE` | Set a config value |
| `pulse daemon` | Run the background scheduler manually |

## AI setup

Pulse supports two AI providers. Set one up to get daily and weekly summaries.

**Option A — OpenRouter (free models available):**
```bash
pulse config set openrouter_api_key  sk-or-v1-...
pulse config set openrouter_model    arcee-ai/trinity-large-preview
```

**Option B — Anthropic:**
```bash
pulse config set anthropic_api_key   sk-ant-...
```

OpenRouter takes priority if both are configured.

## Config reference

| Key | Description |
|---|---|
| `openrouter_api_key` | OpenRouter API key |
| `openrouter_model` | OpenRouter model ID (e.g. `arcee-ai/trinity-large-preview`) |
| `anthropic_api_key` | Anthropic API key |
| `checkin_interval_min` | Minutes between check-ins (default: 90) |

## Data

All data lives in `~/.pulse_pm/`:

```
~/.pulse_pm/
├── pulse.db       # SQLite database
├── daemon.log     # Background daemon logs
└── venv/          # Python virtual environment
```

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.pulspm.agent.plist
rm ~/Library/LaunchAgents/com.pulspm.agent.plist
rm -rf ~/.pulse_pm
# remove the alias from ~/.zshrc manually
```
