#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta

WORK_BLOCKS = (
    ((8, 0), (12, 0)),
    ((13, 0), (17, 0)),
)


def _at_local_time(day: datetime, hm: tuple[int, int]) -> datetime:
    return day.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)


def _is_weekend(day: datetime) -> bool:
    return day.weekday() >= 5


def _next_work_start(now: datetime) -> datetime:
    cursor = now
    while True:
        day = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        if _is_weekend(day):
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


def add_work_minutes(start: datetime, minutes: int) -> datetime:
    if minutes <= 0:
        return start

    remaining = minutes
    cursor = _next_work_start(start)

    while remaining > 0:
        day = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        if _is_weekend(day):
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

