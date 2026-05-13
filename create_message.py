#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from work_time import add_work_minutes

TZ_TAIPEI = timezone(timedelta(hours=8))
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]
CHILD_WORK_FACTOR = 0.8


def to_local(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(TZ_TAIPEI)


def format_message_date(d: datetime) -> str:
    return f"{d.month}/{d.day}（{WEEKDAY_CN[d.weekday()]}）{d.strftime('%H:%M')}"


def format_duration_for_message(total_minutes: int) -> str:
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0 and minutes > 0:
        return f"{hours}時{minutes}分"
    if hours > 0:
        return f"{hours}時"
    return f"{minutes}分"


def round_minutes_to_step(raw_minutes: int, step: int = 10) -> int:
    if raw_minutes <= 0:
        return 0
    return max(step, int((raw_minutes / step) + 0.5) * step)


def js_math_round(x: float) -> int:
    return int(x + 0.5) if x >= 0 else int(x - 0.5)


def adjusted_child_minutes(raw_minutes: int, factor: float = CHILD_WORK_FACTOR) -> int:
    if raw_minutes <= 0:
        return 0
    rounded_input = round_minutes_to_step(raw_minutes)
    adjusted = max(1, js_math_round(rounded_input * factor))
    return round_minutes_to_step(adjusted)


def normalize_tasks(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError("JSON must be an object or array of objects")


def iter_tasks(tasks: list[dict]):
    for task in tasks:
        if isinstance(task, dict):
            yield task
            children = task.get("children")
            if isinstance(children, list):
                yield from iter_tasks(children)


def find_task_by_id(tasks: list[dict], task_id: str) -> dict | None:
    for task in iter_tasks(tasks):
        if task.get("id") == task_id:
            return task
    return None


def get_target_task(tasks: list[dict], task_id: str | None) -> dict:
    if not tasks:
        raise ValueError("No tasks found in input.")
    if task_id:
        task = find_task_by_id(tasks, task_id)
        if not task:
            raise ValueError(f"Task id not found: {task_id}")
        return task
    latest = tasks[-1]
    if not isinstance(latest, dict):
        raise ValueError("Latest task is invalid.")
    return latest


def aggregate_children(task: dict) -> list[tuple[str, int]]:
    totals: dict[str, int] = {}
    ordered_names: list[str] = []
    children = task.get("children")
    if not isinstance(children, list):
        return []

    for child in children:
        if not isinstance(child, dict):
            continue
        name = str(child.get("name") or "").strip()
        minutes = child.get("workMinutes")
        if not name or not isinstance(minutes, int) or minutes <= 0:
            continue
        rounded = adjusted_child_minutes(minutes)
        if name not in totals:
            ordered_names.append(name)
            totals[name] = 0
        totals[name] += rounded

    return [(name, totals[name]) for name in ordered_names]


def format_deadline_extension_message(task: dict) -> str:
    assignment = str(task.get("name") or "").strip()
    assignee = str(task.get("assignedBy") or "").strip()
    deadline_raw = task.get("deadline")
    if not isinstance(deadline_raw, str):
        raise ValueError("Task is missing deadline.")
    previous = to_local(deadline_raw)

    assignments = aggregate_children(task)
    total_minutes = sum(minutes for _, minutes in assignments)
    if total_minutes <= 0:
        raise ValueError("Task has no subtasks to build deadline extension message.")
    next_deadline = add_work_minutes(previous, total_minutes)
    transition_text = "延後至" if next_deadline >= previous else "提前至"

    lines = []
    if total_minutes > 0:
        lines.append(f"今日做其他事時間是 {format_duration_for_message(total_minutes)}")
        lines.append("")
        for name, minutes in assignments:
            lines.append(f"{name} {format_duration_for_message(minutes)}")
        lines.append("")

    prefix = f"{assignment}，" if assignment else ""
    assignee_text = f"，請{assignee}幫我確認" if assignee else ""
    lines.append(
        f"{prefix}deadline由{format_message_date(previous)}，"
        f"{transition_text}{format_message_date(next_deadline)}{assignee_text}，謝謝。"
    )
    return "\n".join(lines)


def create_message(tasks: list[dict], msg_type: str, task_id: str | None = None) -> str:
    if msg_type != "deadline-extension":
        raise ValueError(f"Unsupported message type: {msg_type}")
    task = get_target_task(tasks, task_id)
    return format_deadline_extension_message(task)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--infile", default="tasks.json", help="input JSON path")
    parser.add_argument("--type", required=True, help="message type, e.g. deadline-extension")
    parser.add_argument("--task-id", help="specific task id; default is latest top-level task")
    args = parser.parse_args()

    in_path = Path(args.infile)
    data = json.loads(in_path.read_text(encoding="utf-8"))
    tasks = normalize_tasks(data)
    try:
        message = create_message(tasks, msg_type=args.type, task_id=args.task_id)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(message)


if __name__ == "__main__":
    main()
