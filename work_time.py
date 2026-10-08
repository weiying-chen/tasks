#!/usr/bin/env python3
from __future__ import annotations

from datetime import date, datetime, timedelta

WORK_BLOCKS = (
    ((8, 0), (12, 0)),
    ((13, 0), (17, 0)),
)

# Weekday holidays from the DGPA government-office calendar dataset:
# https://data.gov.tw/dataset/14718
TAIWAN_HOLIDAYS = {
    date(2026, 1, 1),
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 2, 18),
    date(2026, 2, 19),
    date(2026, 2, 20),
    date(2026, 2, 27),
    date(2026, 4, 3),
    date(2026, 4, 6),
    date(2026, 5, 1),
    date(2026, 6, 19),
    date(2026, 9, 25),
    date(2026, 9, 28),
    date(2026, 10, 9),
    date(2026, 10, 26),
    date(2026, 12, 25),
    date(2027, 1, 1),
    date(2027, 2, 4),
    date(2027, 2, 5),
    date(2027, 2, 8),
    date(2027, 2, 9),
    date(2027, 2, 10),
    date(2027, 3, 1),
    date(2027, 4, 5),
    date(2027, 4, 6),
    date(2027, 4, 30),
    date(2027, 6, 9),
    date(2027, 9, 15),
    date(2027, 9, 28),
    date(2027, 10, 11),
    date(2027, 10, 25),
    date(2027, 12, 24),
    date(2027, 12, 31),
}

# Keep this override available for years whose official calendar designates a
# Saturday or Sunday as a working day.
TAIWAN_WEEKEND_WORKDAYS: set[date] = set()


def _at_local_time(day: datetime, hm: tuple[int, int]) -> datetime:
    return day.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)


def _is_weekend(day: datetime) -> bool:
    return day.weekday() >= 5


def _is_non_workday(day: datetime) -> bool:
    calendar_date = day.date()
    if calendar_date in TAIWAN_WEEKEND_WORKDAYS:
        return False
    return _is_weekend(day) or calendar_date in TAIWAN_HOLIDAYS


def _next_work_start(now: datetime) -> datetime:
    cursor = now
    while True:
        day = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        if _is_non_workday(day):
            cursor = day + timedelta(days=1)
            continue

        for start_hm, end_hm in WORK_BLOCKS:
            start = _at_local_time(day, start_hm)
            end = _at_local_time(day, end_hm)
            if cursor < start:
                return start
            if start <= cursor < end:
                return cursor

        cursor = day + timedelta(days=1)


def next_work_start(now: datetime) -> datetime:
    return _next_work_start(now)


def add_work_minutes(start: datetime, minutes: int) -> datetime:
    if minutes <= 0:
        return start

    remaining = minutes
    cursor = _next_work_start(start)

    while remaining > 0:
        day = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        if _is_non_workday(day):
            cursor = _next_work_start(day + timedelta(days=1))
            continue

        advanced_in_day = False
        for start_hm, end_hm in WORK_BLOCKS:
            block_start = _at_local_time(day, start_hm)
            block_end = _at_local_time(day, end_hm)
            if cursor >= block_end:
                continue
            if cursor < block_start:
                cursor = block_start

            available = int((block_end - cursor).total_seconds() // 60)
            if available <= 0:
                continue

            use = min(remaining, available)
            cursor = cursor + timedelta(minutes=use)
            remaining -= use
            advanced_in_day = True
            if remaining == 0:
                return cursor

        if not advanced_in_day or remaining > 0:
            cursor = _next_work_start(day + timedelta(days=1))

    return cursor
