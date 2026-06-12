#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from task_stages import get_previous_stage_work_minutes, normalize_stages
from text_to_json import normalize_task_shape, normalize_tasks_json

DEFAULT_SELF_ASSIGNEE = "Alex Chen"
ASSIGNEE_WORK_RATES = {
    "Emily": 1.0,
}


def normalize_task_name_for_match(name: str) -> str:
    normalized = (
        name.strip()
        .replace("（", "(")
        .replace("）", ")")
        .replace("－", "-")
        .replace("—", "-")
        .replace("～", "~")
    )
    return re.sub(r"\s+", "", normalized)


def normalize_program_name_for_match(name: str) -> str:
    normalized = normalize_task_name_for_match(name)
    return re.split(r"[(（]", normalized, maxsplit=1)[0]


def strip_assignment_tail(name: str) -> str:
    return re.sub(r"\s*[，,。!！~～]?\s*謝謝\s*[~～]?\s*$", "", name).strip()


def normalize_assignee_key(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip().lstrip("@"))


def get_assignee_work_rate(name: str) -> float:
    return ASSIGNEE_WORK_RATES.get(normalize_assignee_key(name), 1.0)


def populate_stage_work_minutes(task: dict, stage: dict, assigned_to: str, stage_label: str) -> None:
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

    content_seconds = stage.get("contentSeconds")
    if not isinstance(content_seconds, int) or content_seconds <= 0:
        return
    rate = get_assignee_work_rate(assigned_to)
    stage["workMinutes"] = int(round(content_seconds * rate))


def parse_assignment_message(text: str) -> dict[str, str]:
    stripped = text.strip()
    patterns: list[tuple[str, str, str | None]] = [
        (
            r"^\s*(?P<assignedBy>.+?)\s*請\s*(?P<assignedTo>.+?)\s*edit\s*\+\s*定稿\s*(?P<name>.+?)\s*$",
            "edit",
            None,
        ),
        (
            r"^\s*請\s*(?P<assignedBy>.+?)\s*給我\s*edit\s*\+\s*定稿\s*(?P<name>.+?)\s*$",
            "edit",
            DEFAULT_SELF_ASSIGNEE,
        ),
        (
            r"^\s*(?P<assignedBy>.+?)\s*[.。．]?\s*請\s*(?P<assignedTo>.+?)\s*翻譯\s*(?P<name>.+?)\s*$",
            "translate",
            None,
        ),
    ]

    for pattern, stage, default_assigned_to in patterns:
        match = re.match(pattern, stripped, flags=re.I | re.S)
        if not match:
            continue
        parsed = {key: value.strip() for key, value in match.groupdict().items() if value is not None}
        parsed["assignedBy"] = re.sub(r"\s*[.。．]\s*$", "", parsed["assignedBy"]).strip()
        parsed["assignedTo"] = parsed.get("assignedTo", default_assigned_to or "").strip()
        parsed["name"] = strip_assignment_tail(parsed["name"])
        parsed["stage"] = stage
        if not parsed["assignedTo"]:
            raise ValueError("Cannot parse assignedTo")
        return parsed

    raise ValueError("Cannot parse assignment message")


def ensure_mutable_active_stage(task: dict) -> dict:
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


def find_matching_top_level_tasks(tasks: list[dict], task_name: str) -> list[dict]:
    target = normalize_task_name_for_match(task_name)
    target_program = normalize_program_name_for_match(task_name)
    exact_matched = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_name_value = str(task.get("name") or "")
        normalized_name = normalize_task_name_for_match(task_name_value)
        if normalized_name == target:
            exact_matched.append(task)
            continue
        normalized_program = normalize_program_name_for_match(task_name_value)
        if normalized_program == target_program:
            exact_matched.append(task)
    return exact_matched


def assign_task(tasks: list[dict], text: str) -> list[dict]:
    parsed = parse_assignment_message(text)
    matched = find_matching_top_level_tasks(tasks, parsed["name"])
    if not matched:
        raise ValueError(f"No matching top-level task: {parsed['name']}")
    if len(matched) > 1:
        raise ValueError(f"Multiple matching top-level tasks: {parsed['name']}")

    task = matched[0]
    stage = ensure_mutable_active_stage(task)
    task["assignedBy"] = parsed["assignedBy"]
    stage["assignedTo"] = parsed["assignedTo"]
    populate_stage_work_minutes(task, stage, parsed["assignedTo"], parsed["stage"])
    stage["stage"] = parsed["stage"]
    return tasks


def parse_translate_assignment_message(text: str) -> dict[str, str]:
    return parse_assignment_message(text)


def assign_translate_task(tasks: list[dict], text: str) -> list[dict]:
    return assign_task(tasks, text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--infile", default="tasks.json", help="input/output JSON path")
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
        updated = assign_task(tasks, args.text)
    except ValueError as exc:
        raise SystemExit(f"Cannot assign coworker. ({exc})") from exc

    normalized_tasks = [normalize_task_shape(task) for task in updated if isinstance(task, dict)]
    out_path.write_text(json.dumps(normalized_tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Assigned coworker in tasks.json")


if __name__ == "__main__":
    main()
