"""Background daemon — runs all day, fires check-in notifications."""
import logging
import os
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path

import schedule

from pulse import db
from pulse.notifications import notify, open_terminal_command

LOG_PATH = Path.home() / ".pulse_pm" / "daemon.log"

# Configurable via `pulse config`
DEFAULT_CHECKIN_INTERVAL_MIN = 90
WORK_START = dtime(9, 0)
WORK_END   = dtime(19, 0)
MORNING_AT = dtime(9, 0)
EVENING_AT = dtime(18, 30)


def _setup_logging() -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def _in_work_hours() -> bool:
    now = datetime.now().time()
    return WORK_START <= now <= WORK_END


def _is_weekday() -> bool:
    return datetime.now().weekday() < 5  # Mon-Fri


def _fire_checkin() -> None:
    if not _in_work_hours() or not _is_weekday():
        return
    logging.info("Firing check-in notification")
    notify(
        title="Pulse — Check-in time",
        message="What are you working on? Run: pulse checkin",
        subtitle="",
    )
    # open a new terminal window automatically
    open_terminal_command("pulse checkin")


def _fire_morning() -> None:
    if not _is_weekday():
        return
    logging.info("Firing morning meeting notification")
    notify(
        title="Pulse — Morning meeting",
        message="Plan your day. Run: pulse morning",
    )
    open_terminal_command("pulse morning")


def _fire_evening() -> None:
    if not _is_weekday():
        return
    logging.info("Firing evening review notification")
    notify(
        title="Pulse — Evening review",
        message="Close out the day. Run: pulse evening",
    )
    open_terminal_command("pulse evening")


def run_daemon() -> None:
    _setup_logging()
    db.init_db()
    logging.info("Pulse daemon started (PID %d)", os.getpid())

    interval = int(db.get_config("checkin_interval_min", str(DEFAULT_CHECKIN_INTERVAL_MIN)))

    schedule.every().day.at("09:00").do(_fire_morning)
    schedule.every().day.at("18:30").do(_fire_evening)
    schedule.every(interval).minutes.do(_fire_checkin)

    logging.info("Check-in interval: %d min", interval)

    while True:
        schedule.run_pending()
        time.sleep(60)
