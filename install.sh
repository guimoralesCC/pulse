#!/usr/bin/env bash
# Pulse PM -- installer
# Usage: ./install.sh

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

log()  { echo -e "${BOLD}${GREEN}> $*${RESET}"; }
warn() { echo -e "${YELLOW}!  $*${RESET}"; }
err()  { echo -e "${RED}x  $*${RESET}"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PULSE_HOME="$HOME/.pulse_pm"
PLIST_SRC="$SCRIPT_DIR/com.pulspm.agent.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.pulspm.agent.plist"

# -- 1. Python check -----------------------------------------------------------
log "Checking Python >= 3.11..."
PYTHON=$(command -v python3 || true)
[[ -z "$PYTHON" ]] && err "python3 not found. Install via Homebrew: brew install python"

PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 11) ]]; then
    err "Python 3.11+ required. Found: $PY_VER"
fi
echo "  Found Python $PY_VER at $PYTHON"

# -- 2. Virtual environment ----------------------------------------------------
VENV="$PULSE_HOME/venv"
log "Creating virtual environment at $VENV..."
mkdir -p "$PULSE_HOME"
"$PYTHON" -m venv "$VENV"
source "$VENV/bin/activate"

# -- 3. Install dependencies ---------------------------------------------------
log "Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
pip install --quiet -e "$SCRIPT_DIR"

PULSE_BIN="$VENV/bin/pulse"
[[ ! -f "$PULSE_BIN" ]] && err "pulse binary not found at $PULSE_BIN -- install failed."

# -- 4. Shell alias ------------------------------------------------------------
log "Adding 'pulse' alias to your shell..."
ALIAS_LINE="alias pulse='$PULSE_BIN'"

for RC in "$HOME/.zshrc" "$HOME/.bashrc"; do
    if [[ -f "$RC" ]]; then
        if grep -q "alias pulse=" "$RC"; then
            warn "Alias already exists in $RC -- skipping."
        else
            echo "" >> "$RC"
            echo "# Pulse PM" >> "$RC"
            echo "$ALIAS_LINE" >> "$RC"
            echo "  Added alias to $RC"
        fi
    fi
done

# -- 5. launchd agent ----------------------------------------------------------
log "Installing launchd agent (launch at login + background daemon)..."
mkdir -p "$HOME/Library/LaunchAgents"

sed \
    -e "s|PULSE_BIN_PATH|$PULSE_BIN|g" \
    -e "s|PULSE_HOME|$PULSE_HOME|g" \
    "$PLIST_SRC" > "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load -w "$PLIST_DST"
echo "  Daemon registered: com.pulspm.agent"

# -- 6. Init database ----------------------------------------------------------
log "Initialising database..."
"$PULSE_BIN" dashboard > /dev/null 2>&1 || true

# -- Done ----------------------------------------------------------------------
echo ""
echo -e "${BOLD}${GREEN}Pulse PM installed.${RESET}"
echo ""
echo "  Reload your shell:   source ~/.zshrc"
echo "  Start your day:      pulse morning"
echo "  Check in:            pulse checkin"
echo "  See dashboard:       pulse"
echo "  Evening review:      pulse evening"
echo "  Manage projects:     pulse projects"
echo "  AI weekly summary:   pulse ai   (requires ANTHROPIC_API_KEY)"
echo ""
echo "  Daemon is running -- will prompt every 90 min during work hours."
echo "  Logs: $PULSE_HOME/daemon.log"
echo ""
