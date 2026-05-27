"""Business-hours elapsed time for SLA comparisons (org calendar + holidays)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from apps.organizations.models import Organization


def _work_weekday_set(cal) -> set[int]:
    raw = cal.work_weekdays or []
    if not raw:
        return {0, 1, 2, 3, 4}
    return {int(x) for x in raw}


def business_elapsed_minutes(start: datetime, end: datetime, organization: Organization) -> int:
    """
    Count minutes between ``start`` and ``end`` that fall inside configured
    business windows (org calendar). If no calendar exists, falls back to wall-clock minutes.
    """
    from zoneinfo import ZoneInfo

    from apps.sla.models import BusinessCalendar, SLAHoliday

    if end <= start:
        return 0

    cal = BusinessCalendar.objects.filter(organization_id=organization.id).first()
    if cal is None:
        return int((end - start).total_seconds() // 60)

    try:
        tz = ZoneInfo(cal.timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")

    if timezone.is_naive(start):
        start = timezone.make_aware(start, timezone.utc)
    if timezone.is_naive(end):
        end = timezone.make_aware(end, timezone.utc)

    start_l = start.astimezone(tz)
    end_l = end.astimezone(tz)
    holiday_dates = set(
        SLAHoliday.objects.filter(organization_id=organization.id).values_list("date", flat=True)
    )
    work_days = _work_weekday_set(cal)

    total_seconds = 0.0
    cur = start_l.date()
    last = end_l.date()
    while cur <= last:
        if cur in holiday_dates or cur.weekday() not in work_days:
            cur += timedelta(days=1)
            continue

        day_start = datetime.combine(cur, cal.workday_start, tzinfo=tz)
        day_end = datetime.combine(cur, cal.workday_end, tzinfo=tz)
        if day_end <= day_start:
            cur += timedelta(days=1)
            continue

        seg_a = max(start_l, day_start)
        seg_b = min(end_l, day_end)
        if seg_b > seg_a:
            total_seconds += (seg_b - seg_a).total_seconds()
        cur += timedelta(days=1)

    return int(total_seconds // 60)
