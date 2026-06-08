#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from work_time import add_work_minutes, next_work_start
from task_stages import get_task_work_minutes, normalize_stages
from task_titles import SUBS_PROGRAM_DEFAULT_ASSIGNEE, extract_subs_task_name
from work_time_adjustments import adjusted_child_minutes

TZ_TAIPEI = timezone(timedelta(hours=8))
RESET = '\x1b[0m'
YELLOW = '\x1b[33m'


def parse_datetime(md: str, hm: str, year: int) -> str:
    m = re.match(r"(\d{1,2})/(\d{1,2})", md)
    t = re.match(r"(\d{1,2}):(\d{2})", hm)
    if not m or not t:
        raise ValueError("invalid date/time")
    month, day = int(m.group(1)), int(m.group(2))
    hour, minute = int(t.group(1)), int(t.group(2))
    local_dt = datetime(year, month, day, hour, minute, tzinfo=TZ_TAIPEI)
    return local_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def to_local(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(TZ_TAIPEI)


def must_match(text: str, pattern: str, field: str, flags=0):
    m = re.search(pattern, text, flags)
    if not m:
        raise ValueError(f"Cannot parse {field}")
    return m


def extract_subs_program_name(subs_name: str) -> str:
    cleaned = re.sub(r"^\s*(?:\d+|[零一二三四五六七八九十百千兩]+)\s*集\s*", "", subs_name).strip()
    program = re.split(r"[（(]", cleaned, maxsplit=1)[0].strip()
    return program


def resolve_subs_assigned_by(subs_name: str) -> str:
    program = extract_subs_program_name(subs_name)
    expected_assignee = SUBS_PROGRAM_DEFAULT_ASSIGNEE.get(program)
    if expected_assignee is None:
        raise ValueError(f"No assignedBy mapping for subs program '{program}'")
    return expected_assignee


def parse_subs_input(text: str, year: int, task_id: str):
    name = extract_subs_task_name(text)
    if not name:
        raise ValueError("Cannot parse name")
    assigned_by = resolve_subs_assigned_by(name)

    content_match = must_match(text, r"(?:長度|片長)\s*(?:共|合計)?\s*(\d+)\s*分(?:\s*(\d+)\s*秒)?", "content duration")
    content_minutes = int(content_match.group(1))
    content_seconds_extra = int(content_match.group(2) or 0)
    content_seconds = content_minutes * 60 + content_seconds_extra

    work = must_match(
        text,
        r"預計(?:翻譯|做)\s*(\d+)\s*(?:時|小時)(?:\s*(\d+)\s*分)?(?:\s*[（(][^）)]*[）)])?",
        "work time",
    )
    work_minutes = int(work.group(1)) * 60 + int(work.group(2) or 0)

    start = re.search(
        r"(?:從|由)\s*(\d{1,2}/\d{1,2})\s*(?:[（(][^）)]*[）)])?\s*(\d{1,2}:\d{2})\s*起算",
        text,
    )
    dl = re.search(
        r"deadline\s*(?:為)?\s*(\d{1,2}/\d{1,2})\s*(?:[（(][^）)]*[）)])?\s*(\d{1,2}:\d{2})",
        text,
        flags=re.I,
    )
    if start and not dl:
        raise ValueError("Cannot parse deadline")
    if dl and not start:
        raise ValueError("Cannot parse start time")

    stage = {
        "type": "subs",
        "workMinutes": work_minutes,
        "contentSeconds": content_seconds,
    }
    if start and dl:
        created_at = parse_datetime(start.group(1), start.group(2), year)
        pm_deadline = parse_datetime(dl.group(1), dl.group(2), year)
        stage["startAt"] = created_at
        stage["deadline"] = pm_deadline
    task = {
        "id": task_id,
        "name": name,
        "assignedBy": assigned_by,
        "stages": [stage],
        "children": [],
        "sourceText": text,
    }

    if start and dl:
        start_local = next_work_start(to_local(stage["startAt"]))
        computed_deadline = add_work_minutes(start_local, work_minutes)
        pm_deadline_local = to_local(stage["deadline"])
        if pm_deadline_local != computed_deadline:
            task["__warning__"] = (
                f"Warning: PM deadline differs; keeping PM deadline "
                f"(PM: {pm_deadline_local.strftime('%Y-%m-%d %a %H:%M')}, "
                f"computed: {computed_deadline.strftime('%Y-%m-%d %a %H:%M')})."
            )

    return task


def parse_hhmm_to_work_minutes(hhmm: str) -> int:
    m = re.match(r"^\s*(\d+):(\d{2})\s*$", hhmm)
    if not m:
        raise ValueError(f"Invalid duration: {hhmm}")
    hours = int(m.group(1))
    minutes = int(m.group(2))
    if minutes >= 60:
        raise ValueError(f"Invalid minutes in duration: {hhmm}")
    return hours * 60 + minutes


def parse_news_input(text: str, year: int, owner_filter: str):
    tasks = []
    now_iso = datetime.now(TZ_TAIPEI).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        date_match = re.match(r"^(\d{1,2})/(\d{1,2})$", line)
        if date_match:
            continue

        row_match = re.match(r"^([^:]+):\s*(.+?)\s*(\d+:\d{2})$", line)
        if not row_match:
            continue

        owner = row_match.group(1).strip()
        name = row_match.group(2).strip()
        duration = row_match.group(3).strip()
        if not owner_matches_filter(owner, owner_filter):
            continue

        original_minutes = parse_hhmm_to_work_minutes(duration)
        work_minutes = original_minutes + 20
        task = {
            "name": name,
            "stages": [
                {
                    "type": "news",
                    "startAt": now_iso,
                    "workMinutes": work_minutes,
                    "contentSeconds": original_minutes * 60,
                }
            ],
            "children": [],
            "sourceText": raw_line,
        }
        tasks.append(task)

    return tasks


def strip_leading_md_date(text: str) -> str:
    # Example: "4/26無私大愛結好緣" -> "無私大愛結好緣"
    return re.sub(r"^\s*\d{1,2}/\d{1,2}\s*", "", text).strip()


def parse_posts_input(text: str, owner_filter: str):
    tasks = []
    now_iso = datetime.now(TZ_TAIPEI).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    default_work_minutes = 60  # Raw 1 hour; child factor is applied in view/message rendering

    lines = [line.rstrip() for line in text.splitlines()]
    i = 0

    def next_non_empty_index(start: int):
        j = start
        while j < len(lines) and not lines[j].strip():
            j += 1
        return j

    while i < len(lines):
        line = lines[i].strip()
        numbered_match = re.match(r"^\d+\.\s*(.+)$", line)
        if not numbered_match:
            i += 1
            continue
        owner_line = numbered_match.group(1).strip()
        if not owner_matches_filter(owner_line, owner_filter):
            i += 1
            continue

        title_idx = next_non_empty_index(i + 1)
        url_idx = next_non_empty_index(title_idx + 1)
        title_line = lines[title_idx].strip() if title_idx < len(lines) else ""
        url_line = lines[url_idx].strip() if url_idx < len(lines) else ""
        if not title_line:
            i += 1
            continue

        name = strip_leading_md_date(title_line)
        source_parts = [line]
        source_parts.append(title_line)
        if url_line.startswith("http://") or url_line.startswith("https://"):
            source_parts.append(url_line)

        task = {
            "name": name,
            "stages": [
                {
                    "type": "posts",
                    "startAt": now_iso,
                    "workMinutes": default_work_minutes,
                }
            ],
            "children": [],
            "sourceText": "\n".join(source_parts),
        }
        tasks.append(task)
        i = url_idx + 1 if url_idx < len(lines) else i + 1

    return tasks


def parse_simple_duration_input(text: str):
    now_iso = datetime.now(TZ_TAIPEI).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        hm_match = re.match(r"^(.+?)\s+(\d+)時(\d+)分$", line)
        if hm_match:
            name = hm_match.group(1).strip()
            hours = int(hm_match.group(2))
            minutes = int(hm_match.group(3))
            if name and 0 <= minutes < 60:
                return {
                    "name": name,
                    "stages": [
                        {
                            "type": "custom",
                            "startAt": now_iso,
                            "workMinutes": hours * 60 + minutes,
                        }
                    ],
                    "children": [],
                    "sourceText": raw_line,
                }

        m_match = re.match(r"^(.+?)\s+(\d+)分$", line)
        if m_match:
            name = m_match.group(1).strip()
            minutes = int(m_match.group(2))
            if name and minutes > 0:
                return {
                    "name": name,
                    "stages": [
                        {
                            "type": "custom",
                            "startAt": now_iso,
                            "workMinutes": minutes,
                        }
                    ],
                    "children": [],
                    "sourceText": raw_line,
                }

    return None


def parse_notes_input(text: str) -> list[str]:
    notes: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.match(r"^[•*-]\s*(.+)$", line)
        if not m:
            return []
        note = m.group(1).strip()
        if not note:
            return []
        notes.append(note)
    return notes


def parse_source_text(source_text: str, existing_tasks: list[dict], now_year: int) -> list[dict]:
    # Parse precedence matters: posts/news can include text that fails subs.
    new_items = []
    parsed_posts = parse_posts_input(source_text, "alex")
    if parsed_posts:
        for item in parsed_posts:
            item["id"] = next_numeric_task_id(existing_tasks + new_items)
            new_items.append(item)
        return new_items

    parsed_news = parse_news_input(source_text, now_year, "Alex Chen")
    if parsed_news:
        for item in parsed_news:
            item["id"] = next_numeric_task_id(existing_tasks + new_items)
            new_items.append(item)
        return new_items

    parsed_simple = parse_simple_duration_input(source_text)
    if parsed_simple:
        parsed_simple["id"] = next_numeric_task_id(existing_tasks + new_items)
        new_items.append(parsed_simple)
        return new_items

    new_task_id = next_numeric_task_id(existing_tasks)
    out = parse_subs_input(source_text, now_year, task_id=new_task_id)
    return [out]


def normalize_tasks_json(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError("Existing JSON must be an object or array of objects")


def normalize_owner_key(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def owner_matches_filter(owner_value: str, owner_filter: str) -> bool:
    owner_key = normalize_owner_key(owner_value)
    filter_key = normalize_owner_key(owner_filter)
    if not filter_key:
        return True
    if owner_key == filter_key:
        return True
    return owner_key.startswith(filter_key) or filter_key.startswith(owner_key)


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


def append_notes_under_parent(tasks, parent_id, notes: list[str]) -> bool:
    for task in tasks:
        if task.get("id") == parent_id:
            existing_notes = task.get("notes")
            if isinstance(existing_notes, list):
                normalized_existing = [n for n in existing_notes if isinstance(n, str)]
                task["notes"] = normalized_existing + notes
            else:
                task["notes"] = notes[:]
            return True
        children = task.get("children")
        if isinstance(children, list) and append_notes_under_parent(children, parent_id, notes):
            return True
    return False


def normalize_task_shape(task):
    children_raw = task.get("children")
    children = []
    if isinstance(children_raw, list):
        children = [normalize_task_shape(child) for child in children_raw if isinstance(child, dict)]

    normalized = {
        "id": str(task.get("id", "")),
        "name": task.get("name", ""),
    }
    assigned_by = task.get("assignedBy")
    if isinstance(assigned_by, str):
        normalized["assignedBy"] = assigned_by
    if isinstance(task.get("createdDate"), str):
        normalized["createdDate"] = task["createdDate"]
    if isinstance(task.get("deadlineDate"), str):
        normalized["deadlineDate"] = task["deadlineDate"]
    stages = normalize_stages(task)
    if stages:
        normalized["stages"] = stages
    notes = task.get("notes")
    if isinstance(notes, list):
        normalized_notes = [note for note in notes if isinstance(note, str) and note.strip()]
        if normalized_notes:
            normalized["notes"] = normalized_notes

    normalized["children"] = children

    if isinstance(task.get("sourceText"), str):
        normalized["sourceText"] = task["sourceText"]

    return normalized


def apply_child_work_rule(task: dict) -> None:
    stages = task.get("stages")
    if isinstance(stages, list):
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            minutes = stage.get("workMinutes")
            if isinstance(minutes, int) and minutes > 0:
                stage["workMinutes"] = adjusted_child_minutes(minutes)
    else:
        minutes = get_task_work_minutes(task)
        if isinstance(minutes, int) and minutes > 0:
            task["workMinutes"] = adjusted_child_minutes(minutes)

    children = task.get("children")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                apply_child_work_rule(child)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--infile", default="tasks.json", help="input/output JSON path")
    parser.add_argument("text", nargs="?", help="source task text")
    parser.add_argument("--parent-id", help="insert new task under this parent task id")
    parser.add_argument("--target", choices=["children", "notes"], default="children", help="parent field target when using --parent-id")
    parser.add_argument("--debug", action="store_true", help="show full traceback on errors")
    args = parser.parse_args()

    out_path = Path(args.infile)
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        tasks = normalize_tasks_json(existing)
    else:
        tasks = []

    if args.text:
        source_text = args.text
    else:
        raise ValueError("Provide source text")

    now_year = datetime.now(TZ_TAIPEI).year

    if args.target == "notes":
        try:
            if not args.parent_id:
                raise ValueError("--target notes requires --parent-id")
            notes = parse_notes_input(source_text)
            if not notes:
                raise ValueError("Cannot parse notes bullets")
            inserted = append_notes_under_parent(tasks, args.parent_id, notes)
            if not inserted:
                raise ValueError(f"Parent id not found: {args.parent_id}")
            normalized_tasks = [normalize_task_shape(task) for task in tasks if isinstance(task, dict)]
            out_path.write_text(json.dumps(normalized_tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Inserted {len(notes)} note(s) under {args.parent_id} in tasks.json")
            return
        except ValueError as exc:
            if args.debug:
                raise
            raise SystemExit(f"Cannot add notes. ({exc})") from exc

    try:
        new_items = parse_source_text(source_text, tasks, now_year)
    except ValueError as exc:
        if args.debug:
            raise
        raise SystemExit(
            f"Cannot parse input as posts/news/subs. Check clipboard text format. ({exc})"
        ) from exc

    if args.parent_id:
        for item in new_items:
            warning = item.pop("__warning__", None)
            if isinstance(warning, str) and warning.strip():
                print(f"{YELLOW}{warning}{RESET}")
            item.pop("assignedBy", None)
            item.pop("owner", None)
            apply_child_work_rule(item)
            inserted = insert_under_parent(tasks, args.parent_id, item)
            if not inserted:
                raise ValueError(f"Parent id not found: {args.parent_id}")
    else:
        for item in new_items:
            warning = item.pop("__warning__", None)
            if isinstance(warning, str) and warning.strip():
                print(f"{YELLOW}{warning}{RESET}")
        tasks.extend(new_items)

    normalized_tasks = [normalize_task_shape(task) for task in tasks if isinstance(task, dict)]
    out_path.write_text(json.dumps(normalized_tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.parent_id:
        print(f"Inserted {len(new_items)} task(s) under {args.parent_id} in tasks.json")
    else:
        print(f"Appended {len(new_items)} task(s) to tasks.json")


if __name__ == "__main__":
    main()
