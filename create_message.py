#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from task_deadline import require_task_deadline_local
from task_stages import (
    get_task_assigned_to,
    get_task_content_seconds,
    get_task_stage,
    get_task_start_at,
    get_task_type,
    get_task_work_minutes,
)
from text_to_json import resolve_subs_assigned_by
from work_time import add_work_minutes

TZ_TAIPEI = timezone(timedelta(hours=8))
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]
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


def format_duration_for_summary_message(total_minutes: int) -> str:
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0 and minutes > 0:
        return f"{hours}時{minutes:02d}分"
    if hours > 0:
        return f"{hours}時"
    return f"{minutes}分"


def format_content_duration_for_message(total_seconds: int) -> str:
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}分{seconds:02d}秒"


def format_mention(name: str) -> str:
    value = str(name or "").strip()
    if not value:
        return ""
    if value.startswith("@"):
        return value
    return f"@{value}"


def parse_message_datetime(md: str, hm: str, year: int) -> datetime:
    m = re.match(r"(\d{1,2})/(\d{1,2})", md)
    t = re.match(r"(\d{1,2}):(\d{2})", hm)
    if not m or not t:
        raise ValueError("invalid date/time")
    month, day = int(m.group(1)), int(m.group(2))
    hour, minute = int(t.group(1)), int(t.group(2))
    return datetime(year, month, day, hour, minute, tzinfo=TZ_TAIPEI)


def parse_deadline_transition_message(text: str, year: int | None = None) -> tuple[datetime | None, datetime]:
    target_year = year or datetime.now(TZ_TAIPEI).year
    old_match = re.search(
        r"deadline\s*由\s*(\d{1,2}/\d{1,2})\s*(?:[（(][^）)]*[）)])?\s*(\d{1,2}:\d{2})",
        text,
        flags=re.I,
    )
    new_match = re.search(
        r"(?:延後至|提前至)\s*(\d{1,2}/\d{1,2})\s*(?:[（(][^）)]*[）)])?\s*(\d{1,2}:\d{2})",
        text,
        flags=re.I,
    )
    if not new_match:
        raise ValueError("Cannot parse deadline")
    old_deadline = None
    if old_match:
        old_deadline = parse_message_datetime(old_match.group(1), old_match.group(2), target_year)
    new_deadline = parse_message_datetime(new_match.group(1), new_match.group(2), target_year)
    return old_deadline, new_deadline


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


def aggregate_children(task: dict, only_local_date=None) -> list[tuple[str, int]]:
    totals: dict[str, int] = {}
    ordered_labels: list[str] = []
    children = task.get("children")
    if not isinstance(children, list):
        return []

    for child in children:
        if not isinstance(child, dict):
            continue
        if only_local_date is not None:
            child_created = get_task_start_at(child)
            if isinstance(child_created, str):
                if to_local(child_created).date() != only_local_date:
                    continue
        child_type = str(get_task_type(child) or "").strip().lower()
        label = TYPE_LABELS.get(child_type)
        if not label:
            label = str(child.get("name") or "").strip()
        minutes = get_task_work_minutes(child)
        if not label or not isinstance(minutes, int) or minutes <= 0:
            continue
        if label not in totals:
            ordered_labels.append(label)
            totals[label] = 0
        totals[label] += minutes

    return [(label, totals[label]) for label in ordered_labels]


def total_child_minutes(task: dict, only_local_date=None) -> int:
    total = 0
    children = task.get("children")
    if not isinstance(children, list):
        return 0

    for child in children:
        if not isinstance(child, dict):
            continue
        if only_local_date is not None:
            child_created = get_task_start_at(child)
            if isinstance(child_created, str) and to_local(child_created).date() != only_local_date:
                continue
        minutes = get_task_work_minutes(child)
        if isinstance(minutes, int) and minutes > 0:
            total += minutes

    return total


def format_deadline_extension_message(task: dict, now_local: datetime | None = None) -> str:
    if now_local is None:
        now_local = datetime.now(TZ_TAIPEI)
    assignment = str(task.get("name") or "").strip()
    assignee = str(task.get("assignedBy") or "").strip()
    assignments = aggregate_children(task, only_local_date=now_local.date())
    today_minutes = sum(minutes for _, minutes in assignments)
    if today_minutes <= 0:
        raise ValueError("Task has no subtasks for current workday.")
    all_child_minutes = total_child_minutes(task)
    previous_minutes = max(all_child_minutes - today_minutes, 0)
    base_deadline = require_task_deadline_local(task)
    previous = add_work_minutes(base_deadline, previous_minutes) if previous_minutes > 0 else base_deadline
    next_deadline = add_work_minutes(previous, today_minutes)
    transition_text = "延後至" if next_deadline >= previous else "提前至"

    lines = []
    if today_minutes > 0:
        lines.append(f"今日做其他事時間是 {format_duration_for_message(today_minutes)}")
        lines.append("")
        for name, minutes in assignments:
            lines.append(f"{name} {format_duration_for_message(minutes)}")
        lines.append("")

    prefix = f"{assignment}，" if assignment else ""
    assignee_text = f"，請{format_mention(assignee)}幫我確認" if assignee else ""
    lines.append(
        f"{prefix}deadline由{format_message_date(previous)}，"
        f"{transition_text}{format_message_date(next_deadline)}{assignee_text}，謝謝。"
    )
    return "\n".join(lines)


def deadline_window_local(task: dict, child_minutes: int | None = None) -> tuple[datetime, datetime]:
    base_deadline = require_task_deadline_local(task)
    if child_minutes is None:
        child_minutes = sum(minutes for _, minutes in aggregate_children(task))
    if child_minutes <= 0:
        return base_deadline, base_deadline
    return base_deadline, add_work_minutes(base_deadline, child_minutes)


def final_deadline_local(task: dict) -> datetime:
    _, final_deadline = deadline_window_local(task)
    return final_deadline


def resolve_next_task_assignee(next_task_name: str, fallback_assignee: str | None = None) -> str:
    try:
        return resolve_subs_assigned_by(next_task_name)
    except ValueError:
        return str(fallback_assignee or "").strip()


def parse_task_assignment_task_name(task_name: str) -> tuple[str, str, list[str]]:
    match = re.match(
        r"^\s*(?P<count>\d+|[零一二三四五六七八九十百千兩]+)\s*集\s*"
        r"(?P<program>.+?)\s*[（(](?P<episodes>.+?)[）)]\s*$",
        task_name,
    )
    if not match:
        raise ValueError("Task name does not include parenthesized episode titles.")

    count = match.group("count").strip()
    program = match.group("program").strip()
    episodes_text = match.group("episodes").strip()
    episodes = [part.strip() for part in re.split(r"\s*[+＋]\s*", episodes_text) if part.strip()]
    if not program or not episodes:
        raise ValueError("Task name does not include parenthesized episode titles.")
    return count, program, episodes


def format_small_chinese_number(value: int) -> str:
    digits = "零一二三四五六七八九"
    if value < 0:
        raise ValueError("Negative counts are not supported.")
    if value < 10:
        return digits[value]
    if value < 20:
        return "十" if value == 10 else f"十{digits[value - 10]}"
    if value < 100:
        tens, ones = divmod(value, 10)
        out = f"{digits[tens]}十"
        if ones:
            out += digits[ones]
        return out
    return str(value)


def task_assignment_action_text(task: dict) -> str:
    stage = str(get_task_stage(task) or "").strip().lower()
    if stage == "edit":
        return "edit + 定稿"
    return "翻譯"


def format_task_assignment_message(task: dict) -> str:
    task_name = str(task.get("name") or "").strip()
    assigned_to = str(get_task_assigned_to(task) or "").strip()
    work_minutes = get_task_work_minutes(task)
    content_seconds = get_task_content_seconds(task)
    if not task_name or not assigned_to:
        raise ValueError("Missing required fields for task-assignment message.")
    if not isinstance(work_minutes, int) or work_minutes <= 0:
        raise ValueError("Missing required work minutes for task-assignment message.")
    if not isinstance(content_seconds, int) or content_seconds < 0:
        raise ValueError("Missing required content seconds for task-assignment message.")

    count_text, program_name, episodes = parse_task_assignment_task_name(task_name)
    action_text = task_assignment_action_text(task)
    action_prefix = action_text if action_text == "翻譯" else f" {action_text}"
    if count_text.isdigit():
        count_display = format_small_chinese_number(int(count_text))
    else:
        count_display = count_text
    episode_text = " + ".join(episodes)
    return (
        f"請{format_mention(assigned_to)}{action_prefix}{count_display}集{program_name}（{episode_text}），"
        f"片長共{format_content_duration_for_message(content_seconds)}，"
        f"預計{action_prefix}{format_duration_for_summary_message(work_minutes)}，"
        "deadline等手上工作完成後再給，謝謝~"
    )


def format_next_task_message(finished_task: dict, next_task_name: str, next_assignee: str | None = None) -> str:
    completed_task = str(finished_task.get("name") or "").strip()
    fallback_assignee = str(finished_task.get("assignedBy") or "").strip()
    assignee = str(next_assignee or "").strip() or resolve_next_task_assignee(next_task_name, fallback_assignee)
    if not completed_task or not next_task_name or not assignee:
        raise ValueError("Missing required fields for task-completion message.")

    start = final_deadline_local(finished_task)
    return (
        f"已完成{completed_task}，接下來會開始翻譯{next_task_name}，"
        f"再麻煩{format_mention(assignee)}便時幫忙設deadline，"
        f"從{format_message_date(start)}起算，謝謝。"
    )


def create_message(
    tasks: list[dict],
    msg_type: str,
    task_id: str | None = None,
    next_task_name: str | None = None,
    next_assignee: str | None = None,
    now_local: datetime | None = None,
) -> str:
    if msg_type == "deadline-extension":
        task = get_target_task(tasks, task_id)
        return format_deadline_extension_message(task, now_local=now_local)
    if msg_type == "task-completion":
        if not task_id:
            raise ValueError("--task-id is required for task-completion message.")
        name = str(next_task_name or "").strip()
        if not name:
            raise ValueError("--next-task-name is required for task-completion message.")
        finished_task = get_target_task(tasks, task_id)
        assignee = str(next_assignee or "").strip() or None
        return format_next_task_message(finished_task, name, assignee)
    if msg_type == "task-assignment":
        task = get_target_task(tasks, task_id)
        return format_task_assignment_message(task)
    raise ValueError(f"Unsupported message type: {msg_type}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--infile", default="tasks.json", help="input JSON path")
    parser.add_argument("--type", required=True, help="message type, e.g. deadline-extension")
    parser.add_argument("--task-id", help="specific task id; default is latest top-level task")
    parser.add_argument("--next-task-name", help="next task name text for task-completion message")
    parser.add_argument("--next-assignee", help="assignee to ask for task-completion deadline")
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
            next_assignee=args.next_assignee,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(message)


if __name__ == "__main__":
    main()
