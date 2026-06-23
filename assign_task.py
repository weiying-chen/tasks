#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from task_stages import get_previous_stage_work_minutes, get_task_content_seconds, normalize_stages
from text_to_json import normalize_task_shape, normalize_tasks_json, parse_datetime
from work_time import add_work_minutes, next_work_start

DEFAULT_SELF_ASSIGNEE = "Alex Chen"
TZ_TAIPEI = timezone(timedelta(hours=8))
TRANSLATION_WORK_RATE_BY_ASSIGNEE = {
    "Emily Ding": 1.0,
}


def strip_assignment_tail(name: str) -> str:
    return re.sub(r"\s*[，,。!！~～]?\s*謝謝\s*[~～]?\s*$", "", name).strip()


def strip_task_name_trailing_punctuation(name: str) -> str:
    return re.sub(r"[\s，,。!！~～]+$", "", name).strip()


def normalize_assignee_key(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip().lstrip("@"))


def get_assignee_work_rate(name: str) -> float:
    return TRANSLATION_WORK_RATE_BY_ASSIGNEE.get(normalize_assignee_key(name), 1.0)


def populate_stage_work_minutes(task: dict, stage: dict, assignee: str, stage_label: str) -> None:
    existing_minutes = stage.get("workMinutes")
    if isinstance(existing_minutes, int) and existing_minutes > 0:
        return

    stage_label = stage_label.strip().lower()
    if stage_label == "edit":
        base_minutes = get_previous_stage_work_minutes(task, "translate")
        if base_minutes is None:
            return
        stage["workMinutes"] = max(1, int(round(base_minutes / 2)))
        return

    content_seconds = get_task_content_seconds(task)
    if not isinstance(content_seconds, int) or content_seconds <= 0:
        return
    rate = get_assignee_work_rate(assignee)
    stage["workMinutes"] = int(round(content_seconds * rate))


def parse_assignment_message(text: str) -> dict[str, str]:
    stripped = text.strip()
    patterns: list[tuple[str, str, str | None]] = [
        (
            r"^\s*(?P<assigner>.+?)\s*請\s*(?P<assignee>.+?)\s*edit\s*\+\s*定稿\s*(?P<name>.+?)\s*$",
            "edit",
            None,
        ),
        (
            r"^\s*請\s*(?P<assigner>.+?)\s*給我\s*edit\s*\+\s*定稿\s*(?P<name>.+?)\s*$",
            "edit",
            DEFAULT_SELF_ASSIGNEE,
        ),
        (
            r"^\s*(?P<assigner>.+?)\s*[.。．]?\s*請\s*(?P<assignee>.+?)\s*翻譯\s*(?P<name>.+?)\s*$",
            "translate",
            None,
        ),
    ]

    for pattern, stage, default_assignee in patterns:
        match = re.match(pattern, stripped, flags=re.I | re.S)
        if not match:
            continue
        parsed = {key: value.strip() for key, value in match.groupdict().items() if value is not None}
        parsed["assigner"] = re.sub(r"\s*[.。．]\s*$", "", parsed["assigner"]).strip()
        parsed["assignee"] = parsed.get("assignee", default_assignee or "").strip()
        parsed["name"] = strip_assignment_tail(parsed["name"])
        parsed["stage"] = stage
        if not parsed["assignee"]:
            raise ValueError("Cannot parse assignee")
        return parsed

    raise ValueError("Cannot parse assignment message")


def get_or_create_current_stage(task: dict) -> dict:
    stages = task.get("stages")
    if not isinstance(stages, list):
        stages = normalize_stages(task)
        task["stages"] = stages
    if not stages:
        stage = {}
        task["stages"] = [stage]
        return stage

    for stage in reversed(stages):
        if not isinstance(stage, dict):
            continue
        return stage
    stage = {}
    stages.append(stage)
    return stage


def ensure_mutable_stage_for_assignment(task: dict, stage_name: str) -> dict:
    stages = task.get("stages")
    if not isinstance(stages, list):
        stages = normalize_stages(task)
        task["stages"] = stages
    if not stages:
        stage = {}
        task["stages"] = [stage]
        return stage

    for stage in reversed(stages):
        if not isinstance(stage, dict):
            continue
        current_name = str(stage.get("name") or stage.get("stage") or "").strip().lower()
        if current_name == stage_name.strip().lower():
            return stage
        if not current_name:
            return stage
        break

    new_stage = {}
    stages.append(new_stage)
    return new_stage


def assign_task(tasks: list[dict], text: str) -> list[dict]:
    parsed = parse_assignment_message(text)
    task = get_latest_top_level_task(tasks)
    stage = ensure_mutable_stage_for_assignment(task, parsed["stage"])
    task["assigner"] = parsed["assigner"]
    stage["assignee"] = parsed["assignee"]
    populate_stage_work_minutes(task, stage, parsed["assignee"], parsed["stage"])
    stage["name"] = parsed["stage"]
    return tasks


def parse_task_start_message(text: str, year: int | None = None) -> dict[str, str]:
    if year is None:
        year = datetime.now(TZ_TAIPEI).year
    stripped = text.strip()
    match = re.search(
        r"接下來(?:我會|會)?開始翻譯\s*(?P<name>.+?)\s*deadline從\s*"
        r"(?P<md>\d{1,2}/\d{1,2})\s*(?:[（(][^）)]*[）)])?\s*"
        r"(?P<hm>\d{1,2}:\d{2})\s*起算",
        stripped,
        flags=re.I | re.S,
    )
    if not match:
        raise ValueError("Cannot parse task start message")
    name = strip_task_name_trailing_punctuation(match.group("name"))
    if not name:
        raise ValueError("Cannot parse task start task name")
    start_at = parse_datetime(match.group("md"), match.group("hm"), year)
    return {
        "name": name,
        "startAt": start_at,
    }


def confirm_task_start(
    tasks: list[dict],
    text: str,
    year: int | None = None,
) -> list[dict]:
    parsed = parse_task_start_message(text, year=year)
    task = get_latest_top_level_task(tasks)
    stage = get_or_create_current_stage(task)
    assignee = normalize_assignee_key(stage.get("assignee"))
    if not assignee:
        raise ValueError("Missing assignee for task start confirmation")
    work_minutes = stage.get("workMinutes")
    if not isinstance(work_minutes, int) or work_minutes <= 0:
        raise ValueError("Missing work minutes for task start confirmation")

    start_at = parsed["startAt"]
    start_local = next_work_start(datetime.fromisoformat(start_at.replace("Z", "+00:00")).astimezone(TZ_TAIPEI))
    deadline_local = add_work_minutes(start_local, work_minutes) + timedelta(minutes=1)
    stage["startAt"] = start_at
    stage["deadline"] = deadline_local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return tasks


def parse_translate_assignment_message(text: str) -> dict[str, str]:
    return parse_assignment_message(text)


def assign_translate_task(tasks: list[dict], text: str) -> list[dict]:
    return assign_task(tasks, text)


def get_latest_top_level_task(tasks: list[dict]) -> dict:
    if not tasks:
        raise ValueError("No matching top-level task: latest")
    latest = tasks[-1]
    if not isinstance(latest, dict):
        raise ValueError("No matching top-level task: latest")
    return latest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--infile", default="tasks.json", help="input/output JSON path")
    parser.add_argument(
        "--mode",
        choices=("assignment", "task-start"),
        default="assignment",
        help="update mode",
    )
    parser.add_argument("text", nargs="?", help="assignment message text")
    args = parser.parse_args()

    if not args.text:
        raise ValueError("Provide source text")

    out_path = Path(args.infile)
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        tasks = normalize_tasks_json(existing)
    else:
        tasks = []

    try:
        if args.mode == "task-start":
            updated = confirm_task_start(tasks, args.text)
        else:
            updated = assign_task(tasks, args.text)
    except ValueError as exc:
        if args.mode == "task-start":
            raise SystemExit(f"Cannot confirm coworker task start. ({exc})") from exc
        raise SystemExit(f"Cannot assign coworker. ({exc})") from exc

    normalized_tasks = [normalize_task_shape(task) for task in updated if isinstance(task, dict)]
    out_path.write_text(json.dumps(normalized_tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.mode == "task-start":
        print("Confirmed coworker task start in tasks.json")
    else:
        print("Assigned coworker in tasks.json")


if __name__ == "__main__":
    main()
