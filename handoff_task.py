#!/usr/bin/env python3
import argparse
import copy
import json
import os
import re
import tempfile
from pathlib import Path

from assign_task import assign_task, parse_assignment_message
from task_stages import normalize_stages
from text_to_json import next_numeric_task_id, normalize_task_shape, normalize_tasks_json


SELF_ASSIGNEE = "Alex Chen"
NEXT_STAGE_NAMES = {"edit", "finalize"}


def task_identity(name: str) -> tuple[str, str]:
    match = re.match(
        r"^\s*(?P<count>\d+|[零一二三四五六七八九十百千兩]+)\s*集\s*(?P<rest>.+?)\s*$",
        str(name or ""),
    )
    if not match:
        return "", ""
    rest = match.group("rest").strip()
    program = re.split(r"[（(]", rest, maxsplit=1)[0].strip()
    return match.group("count").strip(), program


def validate_assignment_matches_source(source_task: dict, parsed: dict[str, str]) -> None:
    source_identity = task_identity(str(source_task.get("name") or ""))
    assignment_identity = task_identity(parsed.get("name", ""))
    if not all(source_identity) or not all(assignment_identity) or source_identity != assignment_identity:
        raise ValueError("Assignment message does not match selected task")
    if parsed.get("stage") not in NEXT_STAGE_NAMES:
        raise ValueError("Handoff requires an edit or finalize assignment")


def completed_stage_projection(source_task: dict) -> dict:
    stages = normalize_stages(source_task)
    if not stages:
        raise ValueError("Selected task has no completed stage")
    source_stage = stages[-1]
    work_minutes = source_stage.get("workMinutes")
    if not isinstance(work_minutes, int) or work_minutes <= 0:
        raise ValueError("Selected task has no completed work minutes")
    stage_name = str(source_stage.get("name") or "translate").strip()
    assignee = str(source_stage.get("assignee") or "").strip()
    if not assignee and str(source_task.get("assigner") or "").strip() == SELF_ASSIGNEE:
        assignee = SELF_ASSIGNEE
    if not assignee:
        raise ValueError("Selected task has no completed-stage assignee")
    return {
        "name": stage_name,
        "assignee": assignee,
        "workMinutes": work_minutes,
    }


def find_linked_task(tasks: list[dict], origin_file: str, source_task_id: str) -> dict | None:
    for task in tasks:
        if not isinstance(task, dict):
            continue
        origin = task.get("origin")
        if not isinstance(origin, dict):
            continue
        if origin.get("file") == origin_file and str(origin.get("taskId") or "") == source_task_id:
            return task
    return None


def handoff_task(
    source_task: dict,
    coworker_tasks: list[dict],
    assignment_text: str,
    origin_file: str = "tasks.json",
) -> tuple[list[dict], str]:
    parsed = parse_assignment_message(assignment_text)
    validate_assignment_matches_source(source_task, parsed)
    source_task_id = str(source_task.get("id") or "").strip()
    if not source_task_id:
        raise ValueError("Selected task has no id")
    completed_stage = completed_stage_projection(source_task)
    updated = copy.deepcopy(coworker_tasks)
    projection = find_linked_task(updated, origin_file, source_task_id)
    if projection is None:
        projection = {
            "id": next_numeric_task_id(updated),
            "name": str(source_task.get("name") or "").strip(),
            "origin": {"file": origin_file, "taskId": source_task_id},
            "stages": [completed_stage],
        }
        updated.append(projection)
    else:
        existing_stages = projection.get("stages")
        later_stages = existing_stages[1:] if isinstance(existing_stages, list) else []
        projection["stages"] = [completed_stage, *later_stages]

    for field in ("name", "type", "contentSeconds", "sourceText"):
        value = source_task.get(field)
        if value is not None:
            projection[field] = copy.deepcopy(value)
    projection["origin"] = {"file": origin_file, "taskId": source_task_id}
    projection["assigner"] = parsed["assigner"]

    assign_task(updated, assignment_text, task_id=str(projection["id"]))
    normalized = [normalize_task_shape(task) for task in updated if isinstance(task, dict)]
    return normalized, str(projection["id"])


def find_task(tasks: list[dict], task_id: str) -> dict:
    for task in tasks:
        if isinstance(task, dict) and str(task.get("id") or "") == task_id:
            return task
    raise ValueError(f"Source task id not found: {task_id}")


def write_json_atomic(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_name = handle.name
    try:
        with handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="tasks.json", help="personal task JSON path")
    parser.add_argument("--target", default="tasks_coworkers.json", help="coworker task JSON path")
    parser.add_argument("--task-id", required=True, help="personal task id to hand off")
    parser.add_argument("--print-id", action="store_true", help="print only the coworker task id")
    parser.add_argument("text", help="next-stage assignment message")
    args = parser.parse_args()

    source_path = Path(args.source)
    target_path = Path(args.target)
    try:
        source_tasks = normalize_tasks_json(json.loads(source_path.read_text(encoding="utf-8")))
        if target_path.exists():
            coworker_tasks = normalize_tasks_json(json.loads(target_path.read_text(encoding="utf-8")))
        else:
            coworker_tasks = []
        source_task = find_task(source_tasks, args.task_id)
        updated, coworker_id = handoff_task(
            source_task,
            coworker_tasks,
            args.text,
            origin_file=source_path.name,
        )
        write_json_atomic(target_path, updated)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"Cannot hand off task. ({exc})") from exc

    if args.print_id:
        print(coworker_id)
    else:
        print(f"Handed off task {args.task_id} as coworker task {coworker_id}")


if __name__ == "__main__":
    main()
