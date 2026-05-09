#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta

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


def build_task_id(title: str, owner: str, created_at: str, deadline: str) -> str:
    raw = f"{title}|{owner}|{created_at}|{deadline}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"task-{digest}"


def parse_task_input(text: str, year: int, split_shorts: bool = False):
    owner = must_match(text, r"請\s*([^\s]+(?:\s+[^\s]+)?)\s+翻譯", "owner").group(1).strip()
    title = must_match(text, r"翻譯\s*([^，,]+?)\s*\d+\s*個短版", "title").group(1).strip()

    short_count = int(must_match(text, r"(\d+)\s*個短版", "short count").group(1))
    content_minutes = int(must_match(text, r"長度\s*(\d+)\s*分", "content minutes").group(1))

    work = must_match(text, r"預計翻譯\s*(\d+)\s*時\s*(\d+)\s*分", "work time")
    work_minutes = int(work.group(1)) * 60 + int(work.group(2))

    start = must_match(text, r"從\s*(\d{1,2}/\d{1,2})(?:[（(][^）)]*[）)])?\s*(\d{1,2}:\d{2})\s*起算", "start time")
    dl = must_match(text, r"deadline為\s*(\d{1,2}/\d{1,2})(?:[（(][^）)]*[）)])?\s*(\d{1,2}:\d{2})", "deadline", flags=re.I)

    created_at = parse_datetime(start.group(1), start.group(2), year)
    deadline = parse_datetime(dl.group(1), dl.group(2), year)
    task_id = build_task_id(title, owner, created_at, deadline)

    task = {
        "id": task_id,
        "title": title,
        "createdAt": created_at,
        "owner": owner,
        "deadline": deadline,
        "workMinutes": work_minutes,
        "contentMinutes": content_minutes,
        "contentSeconds": content_minutes * 60,
        "relations": [],
        "sourceText": text,
    }

    if split_shorts:
        per_short = work_minutes // short_count
        remainder = work_minutes % short_count
        tasks = []
        for i in range(short_count):
            item_minutes = per_short + (1 if i < remainder else 0)
            tasks.append({
                "id": f"task-{i + 1}",
                "title": f"短版 {i + 1}",
                "deadline": deadline,
                "workMinutes": item_minutes,
                "contentMinutes": round(content_minutes / short_count),
                "contentSeconds": round((content_minutes * 60) / short_count),
                "relations": [],
                "comments": [],
            })
        return [task, *tasks]

    return task


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", help="source task text")
    parser.add_argument("-o", "--out", default="tasks.json", help="output JSON file path")
    parser.add_argument("--split-shorts", action="store_true", help="split into short-item tasks")
    args = parser.parse_args()

    out = parse_task_input(args.text, datetime.now(TZ_TAIPEI).year, split_shorts=args.split_shorts)
    json_text = json.dumps(out, ensure_ascii=False, indent=2)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(json_text)
        f.write("\n")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
