from __future__ import annotations

from typing import Any


STAGE_FIELD_NAMES = (
    "type",
    "stage",
    "assignee",
    "startAt",
    "deadline",
    "workMinutes",
    "contentSeconds",
)


def _normalized_stage(stage: dict) -> dict:
    normalized: dict[str, Any] = {}
    for field in STAGE_FIELD_NAMES:
        value = stage.get(field)
        if isinstance(value, str):
            if value.strip():
                normalized[field] = value
        elif isinstance(value, int):
            normalized[field] = value
    return normalized


def build_single_stage(task: dict) -> list[dict]:
    stage = _normalized_stage(task)
    return [stage] if stage else []


def normalize_stages(task: dict) -> list[dict]:
    raw = task.get("stages")
    if isinstance(raw, list):
        normalized = [_normalized_stage(stage) for stage in raw if isinstance(stage, dict)]
        return [stage for stage in normalized if stage]
    return build_single_stage(task)


def active_stage(task: dict) -> dict:
    stages = normalize_stages(task)
    if not stages:
        return {}
    return stages[-1]


def get_task_type(task: dict) -> str | None:
    value = active_stage(task).get("type")
    return value if isinstance(value, str) else None


def get_task_stage(task: dict) -> str | None:
    value = active_stage(task).get("stage")
    return value if isinstance(value, str) else None


def get_task_assignee(task: dict) -> str | None:
    value = active_stage(task).get("assignee")
    return value if isinstance(value, str) else None


def get_task_start_at(task: dict) -> str | None:
    value = active_stage(task).get("startAt")
    return value if isinstance(value, str) else None


def get_task_deadline(task: dict) -> str | None:
    value = active_stage(task).get("deadline")
    return value if isinstance(value, str) else None


def get_task_work_minutes(task: dict) -> int | None:
    value = active_stage(task).get("workMinutes")
    return value if isinstance(value, int) else None


def get_task_content_seconds(task: dict) -> int | None:
    value = active_stage(task).get("contentSeconds")
    return value if isinstance(value, int) else None


def _stage_label(stage: dict) -> str:
    value = stage.get("stage")
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    value = stage.get("type")
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return ""


def get_previous_stage_work_minutes(task: dict, stage_label: str) -> int | None:
    target = stage_label.strip().lower()
    if not target:
        return None
    stages = normalize_stages(task)
    for stage in reversed(stages):
        if not isinstance(stage, dict):
            continue
        if _stage_label(stage) != target:
            continue
        value = stage.get("workMinutes")
        if isinstance(value, int) and value > 0:
            return value
    return None
