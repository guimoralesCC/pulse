"""macOS notifications via osascript."""
import subprocess


def notify(title: str, message: str, subtitle: str = "") -> None:
    sub_part = f' subtitle "{subtitle}"' if subtitle else ""
    script = f'display notification "{message}" with title "{title}"{sub_part}'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except Exception:
        pass  # notifications are best-effort


def open_terminal_command(cmd: str) -> None:
    """Open a new Terminal window and run a pulse command."""
    script = f'tell application "Terminal" to do script "{cmd}"'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except Exception:
        pass
