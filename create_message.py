#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from work_time import add_work_minutes

TZ_TAIPEI = timezone(timedelta(hours=8))
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]
NEXT_TASK_RATE_NOTE = "之前是1分鐘算1小時，現在改成1分鐘算0.8 小時，謝謝。"
TYPE_LABELS = {
    "news": "英文新聞+錄音",
    "posts": "小編文",
}


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
    ordered_labels: list[str] = []
    children = task.get("children")
    if not isinstance(children, list):
        return []

    for child in children:
        if not isinstance(child, dict):
            continue
        child_type = str(child.get("type") or "").strip().lower()
        label = TYPE_LABELS.get(child_type)
        if not label:
            label = str(child.get("name") or "").strip()
        minutes = child.get("workMinutes")
        if not label or not isinstance(minutes, int) or minutes <= 0:
            continue
        if label not in totals:
            ordered_labels.append(label)
            totals[label] = 0
        totals[label] += minutes

    return [(label, totals[label]) for label in ordered_labels]


def format_deadline_extension_message(task: dict) -> str:
    assignment = str(task.get("name") or "").strip()
    assignee = str(task.get("assignedBy") or "").strip()
    assignments = aggregate_children(task)
    total_minutes = sum(minutes for _, minutes in assignments)
    if total_minutes <= 0:
        raise ValueError("Task has no subtasks to build deadline extension message.")
    previous, next_deadline = deadline_window_local(task)
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


def deadline_window_local(task: dict) -> tuple[datetime, datetime]:
    deadline_raw = task.get("deadline")
    if not isinstance(deadline_raw, str):
        raise ValueError("Task is missing deadline.")
    base_deadline = to_local(deadline_raw)
    child_minutes = sum(minutes for _, minutes in aggregate_children(task))
    if child_minutes <= 0:
        return base_deadline, base_deadline
    return base_deadline, add_work_minutes(base_deadline, child_minutes)


def final_deadline_local(task: dict) -> datetime:
    _, final_deadline = deadline_window_local(task)
    return final_deadline


def format_next_task_message(finished_task: dict, next_task_name: str) -> str:
    completed_task = str(finished_task.get("name") or "").strip()
    assignee = str(finished_task.get("assignedBy") or "").strip()
    if not completed_task or not next_task_name or not assignee:
        raise ValueError("Missing required fields for next-task message.")

    start = final_deadline_local(finished_task)
    return (
        f"已完成{completed_task}，接下來會開始翻譯{next_task_name}，"
        f"再麻煩{assignee}便時幫忙設deadline，"
        f"從{format_message_date(start)}起算，謝謝。\n=====\n"
        f"{NEXT_TASK_RATE_NOTE}"
    )


def create_message(
    tasks: list[dict],
    msg_type: str,
    task_id: str | None = None,
    next_task_name: str | None = None,
) -> str:
    if msg_type == "deadline-extension":
        task = get_target_task(tasks, task_id)
        return format_deadline_extension_message(task)
    if msg_type == "next-task":
        if not task_id:
            raise ValueError("--task-id is required for next-task message.")
        name = str(next_task_name or "").strip()
        if not name:
            raise ValueError("--next-task-name is required for next-task message.")
        finished_task = get_target_task(tasks, task_id)
        return format_next_task_message(finished_task, name)
    raise ValueError(f"Unsupported message type: {msg_type}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--infile", default="tasks.json", help="input JSON path")
    parser.add_argument("--type", required=True, help="message type, e.g. deadline-extension")
    parser.add_argument("--task-id", help="specific task id; default is latest top-level task")
    parser.add_argument("--next-task-name", help="next task name text for next-task message")
    args = parser.parse_args()

    in_path = Path(args.infile)
    data = json.loads(in_path.read_text(encoding="utf-8"))
    tasks = normalize_tasks(data)
    try:
        message = create_message(
            tasks,
            msg_type=args.type,
            task_id=args.task_id,
            next_task_name=args.next_task_name,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(message)


if __name__ == "__main__":
    main()
