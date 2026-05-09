#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ_TAIPEI = timezone(timedelta(hours=8))


def parse_datetime(md: str, hm: str, year: int) -> str:
    m = re.match(r"(\d{1,2})/(\d{1,2})", md)
    t = re.match(r"(\d{1,2}):(\d{2})", hm)
    if not m or not t:
        raise ValueError("invalid date/time")
    month, day = int(m.group(1)), int(m.group(2))
    hour, minute = int(t.group(1)), int(t.group(2))
    local_dt = datetime(year, month, day, hour, minute, tzinfo=TZ_TAIPEI)
    return local_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def must_match(text: str, pattern: str, field: str, flags=0):
    m = re.search(pattern, text, flags)
    if not m:
        raise ValueError(f"Cannot parse {field}")
    return m


def parse_task_input(text: str, year: int, task_id: str):
    owner = must_match(text, r"請\s*([^\s]+(?:\s+[^\s]+)?)\s+翻譯", "owner").group(1).strip()
    name = must_match(text, r"翻譯\s*([^，,]+?)\s*\d+\s*個短版", "name").group(1).strip()

    must_match(text, r"(\d+)\s*個短版", "short count")
    content_minutes = int(must_match(text, r"長度\s*(\d+)\s*分", "content minutes").group(1))

    work = must_match(text, r"預計翻譯\s*(\d+)\s*時\s*(\d+)\s*分", "work time")
    work_minutes = int(work.group(1)) * 60 + int(work.group(2))

    start = must_match(text, r"從\s*(\d{1,2}/\d{1,2})(?:[（(][^）)]*[）)])?\s*(\d{1,2}:\d{2})\s*起算", "start time")
    dl = must_match(text, r"deadline為\s*(\d{1,2}/\d{1,2})(?:[（(][^）)]*[）)])?\s*(\d{1,2}:\d{2})", "deadline", flags=re.I)

    created_at = parse_datetime(start.group(1), start.group(2), year)
    deadline = parse_datetime(dl.group(1), dl.group(2), year)
    task = {
        "id": task_id,
        "name": name,
        "owner": owner,
        "createdAt": created_at,
        "deadline": deadline,
        "workMinutes": work_minutes,
        "contentSeconds": content_minutes * 60,
        "children": [],
        "sourceText": text,
    }

    return task


def parse_mmss_to_work_minutes(mmss: str) -> int:
    m = re.match(r"^\s*(\d+):(\d{2})\s*$", mmss)
    if not m:
        raise ValueError(f"Invalid duration: {mmss}")
    mins = int(m.group(1))
    secs = int(m.group(2))
    return mins + (1 if secs >= 30 else 0)


def parse_batch_tasks(text: str, year: int, owner_filter: str):
    tasks = []
    current_month = None
    current_day = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        date_match = re.match(r"^(\d{1,2})/(\d{1,2})$", line)
        if date_match:
            current_month = int(date_match.group(1))
            current_day = int(date_match.group(2))
            continue

        row_match = re.match(r"^([^:]+):\s*(.+?)\s+(\d+:\d{2})$", line)
        if not row_match:
            continue

        owner = row_match.group(1).strip()
        name = row_match.group(2).strip()
        duration = row_match.group(3).strip()
        if owner != owner_filter:
            continue

        work_minutes = parse_mmss_to_work_minutes(duration)
        created_at = None
        deadline = None
        if current_month is not None and current_day is not None:
            local_start = datetime(year, current_month, current_day, 9, 0, tzinfo=TZ_TAIPEI)
            local_deadline = datetime(year, current_month, current_day, 17, 0, tzinfo=TZ_TAIPEI)
            created_at = local_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            deadline = local_deadline.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        task = {
            "name": name,
            "owner": owner,
            "workMinutes": work_minutes,
            "contentSeconds": work_minutes * 60,
            "children": [],
            "sourceText": raw_line,
        }
        if created_at:
            task["createdAt"] = created_at
        if deadline:
            task["deadline"] = deadline
        tasks.append(task)

    return tasks


def normalize_tasks_json(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError("Existing JSON must be an object or array of objects")


def walk_tasks(tasks):
    for task in tasks:
        yield task
        children = task.get("children")
        if isinstance(children, list):
            yield from walk_tasks(children)


def next_numeric_task_id(tasks):
    max_id = 0
    for task in walk_tasks(tasks):
        raw_id = task.get("id")
        if isinstance(raw_id, str) and raw_id.isdigit():
            max_id = max(max_id, int(raw_id))
    return str(max_id + 1)


def ensure_children(task):
    children = task.get("children")
    if isinstance(children, list):
        return children
    task["children"] = []
    return task["children"]


def insert_under_parent(tasks, parent_id, new_task):
    for task in tasks:
        if task.get("id") == parent_id:
            ensure_children(task).append(new_task)
            return True
        children = task.get("children")
        if isinstance(children, list) and insert_under_parent(children, parent_id, new_task):
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="?", help="source task text")
    parser.add_argument("-i", "--infile", help="input text file path")
    parser.add_argument("-o", "--out", default="tasks.json", help="output JSON file path")
    parser.add_argument("--parent-id", help="insert new task under this parent task id")
    parser.add_argument("--owner", default="Alex Chen", help="owner filter for batch text format")
    args = parser.parse_args()

    out_path = Path(args.out)
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        tasks = normalize_tasks_json(existing)
    else:
        tasks = []

    if args.infile:
        source_text = Path(args.infile).read_text(encoding="utf-8")
    elif args.text:
        source_text = args.text
    else:
        raise ValueError("Provide text or --infile")

    now_year = datetime.now(TZ_TAIPEI).year
    if "\n" in source_text and ":" in source_text and re.search(r"^\d{1,2}/\d{1,2}\s*$", source_text, re.M):
        parsed_items = parse_batch_tasks(source_text, now_year, args.owner)
        new_items = []
        for item in parsed_items:
            item["id"] = next_numeric_task_id(tasks + new_items)
            new_items.append(item)
    else:
        new_task_id = next_numeric_task_id(tasks)
        out = parse_task_input(source_text, now_year, task_id=new_task_id)
        new_items = [out]

    if args.parent_id:
        for item in new_items:
            inserted = insert_under_parent(tasks, args.parent_id, item)
            if not inserted:
                raise ValueError(f"Parent id not found: {args.parent_id}")
    else:
        tasks.extend(new_items)

    out_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.parent_id:
        print(f"Inserted {len(new_items)} task(s) under {args.parent_id} in {args.out}")
    else:
        print(f"Appended {len(new_items)} task(s) to {args.out}")


if __name__ == "__main__":
    main()
