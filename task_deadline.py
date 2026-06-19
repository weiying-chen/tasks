from __future__ import annotations

from datetime import datetime, timezone, timedelta

from task_stages import get_task_deadline, get_task_start_at, get_task_work_minutes
from work_time import add_work_minutes, next_work_start

TZ_TAIPEI = timezone(timedelta(hours=8))


def to_local(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(TZ_TAIPEI)


def task_base_created_local(task: dict, now_local: datetime | None = None) -> datetime | None:
    created_at = get_task_start_at(task)
    if isinstance(created_at, str):
        return to_local(created_at)

    created_date = task.get("createdDate")
    if isinstance(created_date, str):
        return datetime.fromisoformat(f"{created_date}T09:00:00+08:00")

    return None


def task_deadline_local(task: dict, now_local: datetime | None = None) -> datetime | None:
    deadline = get_task_deadline(task)
    if isinstance(deadline, str):
        return to_local(deadline)

    deadline_date = task.get("deadlineDate")
    if isinstance(deadline_date, str):
        return datetime.fromisoformat(f"{deadline_date}T17:00:00+08:00")

    base_work_minutes = get_task_work_minutes(task)
    base_created = task_base_created_local(task, now_local=now_local)
    if isinstance(base_work_minutes, int) and base_created is not None:
        start = next_work_start(base_created)
        return add_work_minutes(start, base_work_minutes)

    return None


def require_task_deadline_local(task: dict, now_local: datetime | None = None) -> datetime:
    deadline = task_deadline_local(task, now_local=now_local)
    if deadline is None:
        raise ValueError("Task is missing deadline.")
    return deadline


def deadlines_match(provided_deadline: datetime, computed_deadline: datetime) -> bool:
    return provided_deadline == computed_deadline
