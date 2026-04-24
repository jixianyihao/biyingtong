"""Schedule → next-tick time computation. Pure functions, no IO."""
from __future__ import annotations

from datetime import datetime, time, timedelta


def next_tick(schedule: str, now: datetime) -> datetime:
    """Returns the next datetime at which the given schedule should fire.

    Schedules:
    - 'daily'       : next 9:30 (or today's 9:30 if now < 9:30)
    - 'weekly'      : next Monday 9:30
    - 'intraday_5m' : next 5-minute boundary during trading hours
                      (9:30-11:30, 13:00-15:00 CST). After-hours → next day 9:30.

    Unknown schedule → next day 9:30 (graceful default).
    """
    if schedule == 'weekly':
        # Find next Monday at 9:30
        target_weekday = 0  # Monday
        days_ahead = (target_weekday - now.weekday()) % 7
        if days_ahead == 0:
            # Already Monday — use 9:30 today if in the future, else next Monday
            today_930 = datetime.combine(now.date(), time(9, 30))
            if now < today_930:
                return today_930
            days_ahead = 7
        target_date = now.date() + timedelta(days=days_ahead)
        return datetime.combine(target_date, time(9, 30))

    if schedule == 'intraday_5m':
        return _next_intraday_tick(now)

    # 'daily' and fallback: next 9:30
    today_930 = datetime.combine(now.date(), time(9, 30))
    if now < today_930:
        return today_930
    return datetime.combine(
        now.date() + timedelta(days=1), time(9, 30),
    )


def _next_intraday_tick(now: datetime) -> datetime:
    """Next 5-min boundary during trading hours (9:30-11:30, 13:00-15:00).
    Skips lunch break. After 15:00 → next day 9:30."""
    date = now.date()
    # Round current time up to next 5-min boundary
    minute = now.minute
    next_min = minute - (minute % 5) + 5
    candidate = now.replace(minute=0, second=0, microsecond=0) + \
        timedelta(minutes=next_min)

    morning_open = datetime.combine(date, time(9, 30))
    morning_close = datetime.combine(date, time(11, 30))
    afternoon_open = datetime.combine(date, time(13, 0))
    afternoon_close = datetime.combine(date, time(15, 0))

    if candidate < morning_open:
        return morning_open
    if candidate <= morning_close:
        return candidate
    if candidate < afternoon_open:
        return afternoon_open
    if candidate <= afternoon_close:
        return candidate
    # After 15:00 → tomorrow 9:30
    return datetime.combine(date + timedelta(days=1), time(9, 30))
