from __future__ import annotations

from datetime import datetime, timezone, timedelta

from work_time import add_work_minutes, next_work_start

TZ_TAIPEI = timezone(timedelta(hours=8))


def to_local(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(TZ_TAIPEI)


def task_base_created_local(task: dict, now_local: datetime | None = None) -> datetime | None:
    created_at = task.get("startAt")
    if isinstance(created_at, str):
        return to_local(created_at)

    created_date = task.get("createdDate")
    if isinstance(created_date, str):
        return datetime.fromisoformat(f"{created_date}T09:00:00+08:00")

    return now_local


def task_deadline_local(task: dict, now_local: datetime | None = None) -> datetime | None:
    deadline = task.get("deadline")
    if isinstance(deadline, str):
        return to_local(deadline)

    deadline_date = task.get("deadlineDate")
    if isinstance(deadline_date, str):
        return datetime.fromisoformat(f"{deadline_date}T17:00:00+08:00")

    base_work_minutes = task.get("workMinutes")
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
