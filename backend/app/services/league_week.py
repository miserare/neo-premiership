"""The league's own week, independent of where the server runs.

"This week" has to mean the same thing on a laptop in Europe, in CI, and on the
production VPS, so it is defined against a configured league time zone rather
than the process's local time:

    a week runs Monday 00:00:00 in LEAGUE_TIMEZONE, up to but not including
    the following Monday 00:00:00.

The window is half-open so a match at exactly Monday midnight belongs to the
week starting then, and to exactly one week.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings

# Monday. Kept as a name because "0" in a date calculation is unreadable, and
# because the boundary is documented in README.md and must not drift silently.
WEEK_STARTS_ON = 0


def league_zone() -> ZoneInfo:
    return ZoneInfo(settings.league_timezone)


def current_league_week(now: datetime | None = None) -> tuple[datetime, datetime]:
    """The [start, end) of the league week containing `now`, in UTC.

    `now` is a parameter rather than read from the clock inside, so tests state
    which instant they mean instead of depending on the day they run.
    """
    zone = league_zone()
    moment = (now or datetime.now(timezone.utc)).astimezone(zone)

    # Midnight local to the league, then back to the most recent Monday. Doing
    # this on the date and re-localizing (rather than subtracting from the
    # timestamp) keeps the boundary at real local midnight across a DST change,
    # where a week is 167 or 169 hours rather than 168.
    start_date = moment.date() - timedelta(days=(moment.weekday() - WEEK_STARTS_ON) % 7)
    start = datetime.combine(start_date, datetime.min.time(), tzinfo=zone)
    end = datetime.combine(start_date + timedelta(days=7), datetime.min.time(), tzinfo=zone)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
