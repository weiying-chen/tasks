#!/usr/bin/env python3
import argparse
import json
import os
import re
import select
import subprocess
import sys
import termios
import time
import tty
from datetime import datetime, timezone, timedelta
from pathlib import Path

from task_deadline import task_base_created_local, task_deadline_local
from task_stages import (
    get_task_assignee,
    get_task_stage,
    get_task_start_at,
    get_task_type,
    get_task_work_minutes,
)
from create_message import (
    final_deadline_local,
    format_message_date,
    parse_deadline_transition_message,
    parse_task_assignment_task_name,
)
from text_to_json import next_numeric_task_id, normalize_task_shape
from task_titles import extract_subs_task_name
from work_time import add_work_minutes, next_work_start

TZ_TAIPEI = timezone(timedelta(hours=8))
WORK_BLOCKS = (
    ((8, 0), (12, 0)),
    ((13, 0), (17, 0)),
)
RESET = '\x1b[0m'
BOLD = '\x1b[1m'
YELLOW = '\x1b[33m'   # theme yellow
GREEN = '\x1b[32m'    # theme green
RED = '\x1b[31m'      # terminal red (git-style error emphasis)
BLUE = '\x1b[34m'     # theme blue
MAGENTA = '\x1b[35m'  # ANSI magenta (matches repo-sync DIRTY)
STATUS_TTL_SECONDS = 4.0
DEADLINE_MESSAGE_COPIED_STATUS = "Success: Deadline extension message copied to clipboard"
NEXT_TASK_MESSAGE_COPIED_STATUS = "Success: Next task message copied to clipboard"
SUBS_SUMMARY_MESSAGE_COPIED_STATUS = "Success: Task assignment message copied to clipboard"
CONFIRM_DEADLINE_EXTENSION_STATUS = "Success: Confirm deadline extension checked"
TASK_INITIATION_MESSAGE_COPIED_STATUS = "Success: Task initiation message copied to clipboard"

PERSONAL_ACTIONS = ("t", "s", "n", "v", "q")
COWORKER_ACTIONS = ("a", "c", "d", "q")
ALL_ACTIONS = ("t", "a", "c", "s", "n", "d", "v", "m", "q")


def fmt_work(minutes: int | None) -> str:
    if not isinstance(minutes, int):
        return '-'
    h = minutes // 60
    m = minutes % 60
    if h > 0 and m > 0:
        return f'{h}h {m}m'
    if h > 0:
        return f'{h}h'
    return f'{m}m'


def detect_action_mode(input_file: str | None = None) -> str:
    filename = Path(str(input_file or "tasks.json")).name
    if filename == "tasks_coworkers.json":
        return "coworker"
    if filename == "tasks.json":
        return "personal"
    return "all"


def allowed_actions_for_mode(mode: str) -> tuple[str, ...]:
    if mode == "coworker":
        return COWORKER_ACTIONS
    if mode == "personal":
        return PERSONAL_ACTIONS
    return ALL_ACTIONS


def build_actions_line(input_file: str | None = None, selected_task: dict | None = None) -> str:
    mode = detect_action_mode(input_file)
    allowed = set(allowed_actions_for_mode(mode))
    if build_message_target_options(selected_task, input_file=input_file):
        allowed.add("m")
    labels = {
        "t": color('create ', MAGENTA) + color('t', GREEN) + color('ask', MAGENTA),
        "a": color('set ', MAGENTA) + color('a', GREEN) + color('ssignee', MAGENTA),
        "c": color('c', GREEN) + color('onfirm task start', MAGENTA),
        "s": color('add ', MAGENTA) + color('s', GREEN) + color('ubtasks', MAGENTA),
        "n": color('add ', MAGENTA) + color('n', GREEN) + color('otes', MAGENTA),
        "d": color('confirm ', MAGENTA) + color('d', GREEN) + color('eadline extension', MAGENTA),
        "v": color('toggle ', MAGENTA) + color('v', GREEN) + color('iew notes', MAGENTA),
        "m": color('copy ', MAGENTA) + color('m', GREEN) + color('essage', MAGENTA),
        "q": color('q', GREEN) + color('uit', MAGENTA),
    }
    order = [key for key in ALL_ACTIONS if key in allowed]
    return color('Actions: ', MAGENTA) + color(' | ', MAGENTA).join(labels[key] for key in order)


def to_local(iso_str: str) -> datetime:
    return datetime.fromisoformat(iso_str.replace('Z', '+00:00')).astimezone(TZ_TAIPEI)


def to_display(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%d %a %H:%M')


def normalize_tasks(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError('JSON must be an object or array of objects')


def find_latest_task_id(tasks: list[dict]) -> str | None:
    if not tasks:
        return None
    latest = tasks[-1]
    if not isinstance(latest, dict):
        return None
    task_id = latest.get("id")
    if isinstance(task_id, str) and task_id.strip():
        return task_id
    return None


def find_task_by_id(tasks: list[dict], task_id: str) -> dict | None:
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if task.get("id") == task_id:
            return task
        children = task.get("children")
        if isinstance(children, list):
            found = find_task_by_id(children, task_id)
            if found is not None:
                return found
    return None


def get_view_task(tasks: list[dict], task_id: str | None = None) -> dict | None:
    if task_id:
        return find_task_by_id(tasks, task_id)
    if not tasks:
        return None
    latest = tasks[-1]
    return latest if isinstance(latest, dict) else None


def build_add_to_latest_command(
    script_dir: str,
    parent_id: str,
    target: str = "children",
    infile: str | None = None,
) -> list[str]:
    cmd = ["python3", f"{script_dir}/text_to_json.py"]
    if infile:
        cmd.extend(["--infile", infile])
    cmd.extend(["--parent-id", parent_id, "--target", target, "__CLIPBOARD__"])
    return cmd


def build_add_notes_command(script_dir: str, parent_id: str, infile: str | None = None) -> list[str]:
    return build_add_to_latest_command(script_dir, parent_id, "notes", infile)


def build_add_task_command(script_dir: str, infile: str | None = None) -> list[str]:
    cmd = [f"{script_dir}/add_task.sh"]
    if infile:
        cmd.extend(["--file", infile])
    return cmd


def build_assign_coworker_command(script_dir: str, infile: str | None = None) -> list[str]:
    cmd = ["python3", f"{script_dir}/assign_task.py"]
    if infile:
        cmd.extend(["--infile", infile])
    cmd.append("__CLIPBOARD__")
    return cmd


def build_confirm_task_start_command(script_dir: str, infile: str | None = None) -> list[str]:
    cmd = ["python3", f"{script_dir}/assign_task.py", "--mode", "task-start"]
    if infile:
        cmd.extend(["--infile", infile])
    cmd.append("__CLIPBOARD__")
    return cmd


def build_deadline_message_command(script_dir: str, infile: str, task_id: str) -> list[str]:
    return [
        "python3",
        f"{script_dir}/create_message.py",
        "-i",
        infile,
        "--type",
        "deadline-extension",
        "--task-id",
        task_id,
    ]


def build_task_completion_message_command(
    script_dir: str,
    infile: str,
    finished_task_id: str,
    next_task_name: str,
    next_assigner: str | None = None,
) -> list[str]:
    cmd = [
        "python3",
        f"{script_dir}/create_message.py",
        "-i",
        infile,
        "--type",
        "task-completion",
        "--task-id",
        finished_task_id,
        "--next-task-name",
        next_task_name,
    ]
    if next_assigner:
        cmd.extend(["--next-assigner", next_assigner])
    return cmd


def build_task_assignment_message_command(script_dir: str, infile: str, task_id: str) -> list[str]:
    return [
        "python3",
        f"{script_dir}/create_message.py",
        "-i",
        infile,
        "--type",
        "task-assignment",
        "--task-id",
        task_id,
    ]


def build_task_initiation_message_command(script_dir: str, infile: str, task_id: str) -> list[str]:
    return [
        "python3",
        f"{script_dir}/create_message.py",
        "-i",
        infile,
        "--type",
        "task-initiation",
        "--task-id",
        task_id,
    ]


def build_confirm_deadline_extension_status(task: dict, clipboard_text: str, now_local: datetime | None = None) -> str:
    if now_local is None:
        now_local = datetime.now(TZ_TAIPEI)
    text = clipboard_text.strip()
    if not text:
        raise ValueError("Clipboard is empty.")
    old_deadline, provided_deadline = parse_deadline_transition_message(text, year=now_local.year)
    computed_deadline = final_deadline_local(task)
    parsed_extension_minutes = parse_deadline_extension_work_minutes(text)
    if old_deadline is not None and parsed_extension_minutes > 0:
        computed_deadline = add_work_minutes(old_deadline, parsed_extension_minutes)
    if provided_deadline == computed_deadline:
        return f"{CONFIRM_DEADLINE_EXTENSION_STATUS} ({format_message_date(computed_deadline)})."
    return (
        f"Warning: Coworker deadline differs (provided {format_message_date(provided_deadline)}, "
        f"computed {format_message_date(computed_deadline)})."
    )


def extract_deadline_extension_subtasks(text: str) -> list[tuple[str, int]]:
    subtasks: list[tuple[str, int]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "deadline" in line.lower():
            continue
        if "做其他事時間是" in line:
            continue
        match = re.match(r"^(.+?)\s+((?:(\d+)時(?:(\d+)分)?)|(?:(\d+)分))$", line)
        if not match:
            continue
        name = match.group(1).strip()
        hours = int(match.group(3) or 0)
        minutes = int(match.group(4) or match.group(5) or 0)
        total_minutes = hours * 60 + minutes
        if name and total_minutes > 0:
            subtasks.append((name, total_minutes))
    return subtasks


def parse_deadline_extension_work_minutes(text: str) -> int:
    return sum(minutes for _, minutes in extract_deadline_extension_subtasks(text))


def ingest_deadline_extension_subtasks(tasks: list[dict], parent_id: str, clipboard_text: str) -> int:
    parent = find_task_by_id(tasks, parent_id)
    if not isinstance(parent, dict):
        raise ValueError(f"Task id not found: {parent_id}")

    children = parent.get("children")
    if not isinstance(children, list):
        children = []
        parent["children"] = children

    existing_pairs = set()
    for child in children:
        if not isinstance(child, dict):
            continue
        name = str(child.get("name") or "").strip()
        minutes = get_task_work_minutes(child)
        if name and isinstance(minutes, int) and minutes > 0:
            existing_pairs.add((name, minutes))

    inserted = 0
    for name, minutes in extract_deadline_extension_subtasks(clipboard_text):
        if (name, minutes) in existing_pairs:
            continue
        child = {
            "id": next_numeric_task_id(tasks),
            "name": name,
            "stages": [{"type": "custom", "workMinutes": minutes}],
            "children": [],
        }
        children.append(child)
        existing_pairs.add((name, minutes))
        inserted += 1
    return inserted


def parse_next_task_clipboard_payload(clipboard_text: str) -> tuple[str | None, str]:
    text = clipboard_text.strip()
    if not text:
        return None, ""
    task_name = extract_subs_task_name(text)
    if task_name:
        return None, task_name
    return None, text


def build_notes_target_options(latest_task: dict) -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    latest_id = str(latest_task.get("id") or "").strip()
    latest_name = str(latest_task.get("name") or "(Untitled)").strip()
    if latest_id:
        options.append((latest_id, latest_name))
    children = latest_task.get("children")
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, dict):
                continue
            child_id = str(child.get("id") or "").strip()
            child_name = str(child.get("name") or "(Untitled)").strip()
            if child_id:
                options.append((child_id, f"{child_name} (subtask)"))
    return options


def build_message_target_options(latest_task: dict | None = None, input_file: str | None = None) -> list[tuple[str, str]]:
    mode = detect_action_mode(input_file)
    options: list[tuple[str, str]] = []
    if mode != "coworker":
        options.extend(
            [
                ("deadline-extension", "Deadline extension message"),
                ("task-completion", "Task completion message"),
            ]
        )
    if isinstance(latest_task, dict):
        task_name = str(latest_task.get("name") or "").strip()
        start_at = str(get_task_start_at(latest_task) or "").strip()
        assignee = str(get_task_assignee(latest_task) or "").strip()
        if mode == "coworker" and task_name and assignee:
            try:
                parse_task_assignment_task_name(task_name)
            except ValueError:
                pass
            else:
                options.append(("task-assignment", "Task assignment message"))
        if mode == "coworker" and start_at and assignee and task_deadline_local(latest_task) is not None:
            options.append(("task-initiation", "Task initiation message"))
    return options


def choose_numbered_option(
    stdin_fd: int,
    render_once_fn,
    title: str,
    options: list[tuple[str, str]],
    invalid_selection_msg: str,
) -> tuple[int | None, str | None, bool]:
    numbered = [
        color(f"{idx}.", GREEN) + color(f" {label}", MAGENTA)
        for idx, (_, label) in enumerate(options, start=1)
    ]
    status = color(bold(title), MAGENTA) + "\n\n" + "\n".join(numbered)
    frame = render_once_fn(status=status)
    sys.stdout.write('\x1b[H\x1b[J')
    sys.stdout.write(frame)
    sys.stdout.flush()
    key = os.read(stdin_fd, 1).decode("utf-8", errors="ignore")
    if key == "q":
        return None, None, True
    if key == "\x1b":
        return None, None, False
    try:
        pick = int(key)
    except ValueError:
        return None, invalid_selection_msg, False
    if not 1 <= pick <= len(options):
        return None, invalid_selection_msg, False
    return pick - 1, None, False


def child_total_minutes(task: dict) -> int:
    total = 0
    children = task.get('children')
    if not isinstance(children, list):
        return 0
    for child in children:
        if not isinstance(child, dict):
            continue
        base_child_minutes = get_task_work_minutes(child)
        if isinstance(base_child_minutes, int) and base_child_minutes > 0:
            total += base_child_minutes
    return total


def fmt_countdown(now_local: datetime, target: datetime | None) -> str:
    if target is None:
        return '-'
    total_seconds = work_seconds_between(now_local, target)
    total_seconds = max(total_seconds, 0)

    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f'{hours}h {minutes}m {seconds}s'


def fmt_resume_hint(now_local: datetime, target: datetime | None) -> str:
    if target is None or target <= now_local:
        return ""
    resume_at = next_work_start(now_local)
    if resume_at <= now_local:
        return ""
    return f" (resumes {to_display(resume_at)})"


def color(text: str, code: str) -> str:
    return f'{code}{text}{RESET}'


def bold(text: str) -> str:
    return f'{BOLD}{text}{RESET}'


def work_seconds_between(start: datetime, end: datetime) -> int:
    if start == end:
        return 0
    if start > end:
        return -work_seconds_between(end, start)

    def at_local_time(day: datetime, hm: tuple[int, int]) -> datetime:
        return day.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)

    def is_weekend(day: datetime) -> bool:
        return day.weekday() >= 5

    cursor = start
    seconds = 0
    while cursor < end:
        day = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        if is_weekend(day):
            cursor = day + timedelta(days=1)
            continue

        progressed = False
        for start_hm, end_hm in WORK_BLOCKS:
            block_start = at_local_time(day, start_hm)
            block_end = at_local_time(day, end_hm)
            if end <= block_start:
                continue
            span_start = max(cursor, block_start)
            span_end = min(end, block_end)
            if span_start < span_end:
                seconds += int((span_end - span_start).total_seconds())
                progressed = True
            if end <= block_end:
                return seconds
        cursor = day + timedelta(days=1)
        if not progressed and cursor <= day:
            break

    return seconds


def clean_notes(task: dict) -> list[str]:
    notes = task.get("notes")
    if not isinstance(notes, list):
        return []
    return [note.strip() for note in notes if isinstance(note, str) and note.strip()]


def render_notes_block(lines: list[str], title: str, notes: list[str], show_notes: bool) -> None:
    if not notes:
        if title == "Notes":
            lines.append("Notes: -")
        return
    lines.append(title)
    lines.append('')
    if show_notes:
        for note in notes:
            lines.append(f'• {note}')
        lines.append('')


def render_task_block(
    lines: list[str],
    task: dict,
    now_local: datetime,
    level: int,
    show_subtask_notes: bool,
    show_notes: bool,
    show_subtask_assignment_fields: bool,
) -> None:
    created_base = task_base_created_local(task)
    created = next_work_start(created_base) if created_base is not None else None
    deadline = task_deadline_local(task, now_local=now_local)
    work_minutes = get_task_work_minutes(task)
    task_type = get_task_type(task)
    task_stage = get_task_stage(task)
    assignee = get_task_assignee(task)

    name = task.get("name") or "(Untitled)"

    if level > 2:
        lines.append(f'Name: {name}')
        lines.append(f'Type: {task_type if isinstance(task_type, str) and task_type.strip() else "-"}')
        if show_subtask_assignment_fields:
            lines.append(f'Stage: {task_stage if isinstance(task_stage, str) and task_stage.strip() else "-"}')
            lines.append(f'Assignee: {assignee if isinstance(assignee, str) and assignee.strip() else "-"}')
        lines.append(f'Work time: {fmt_work(work_minutes)}')
        if task_type != "custom":
            lines.append(f'Deadline: {color(to_display(deadline) if deadline else "-", YELLOW)}')
        if show_notes:
            notes = clean_notes(task)
            render_notes_block(lines, "Notes" if not notes else f'Notes ({len(notes)})', notes, show_subtask_notes)
        if not lines or lines[-1] != '':
            lines.append('')
    else:
        lines.append(bold('View task'))
        lines.append('')
        lines.append(f'Name: {name}')
        lines.append(f'Type: {task_type if isinstance(task_type, str) and task_type.strip() else "-"}')
        lines.append(f'Stage: {task_stage if isinstance(task_stage, str) and task_stage.strip() else "-"}')
        lines.append(f'Assignee: {assignee if isinstance(assignee, str) and assignee.strip() else "-"}')
        lines.append(f'Start: {to_display(created) if created else "-"}')
        lines.append(f'Work time: {fmt_work(work_minutes)}')

        extended = None
        child_minutes = child_total_minutes(task)
        if deadline and child_minutes > 0:
            extended = add_work_minutes(deadline, child_minutes)
        if extended:
            lines.append(f'Deadline: {to_display(deadline) if deadline else "-"}')
        else:
            lines.append(f'Deadline: {color(to_display(deadline) if deadline else "-", YELLOW)}')
        if extended:
            lines.append(f'Extended deadline: {color(to_display(extended), YELLOW)}')
            countdown = fmt_countdown(now_local, extended)
            resume_hint = fmt_resume_hint(now_local, extended)
            lines.append(f'Work time left: {color(countdown, GREEN)}{resume_hint}')
        else:
            countdown = fmt_countdown(now_local, deadline)
            resume_hint = fmt_resume_hint(now_local, deadline)
            lines.append(f'Work time left: {color(countdown, GREEN)}{resume_hint}')
        children = task.get('children')
        if isinstance(children, list) and children:
            lines.append('')
            lines.append(bold('Subtasks'))
            lines.append('')

        children = task.get('children')
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    render_task_block(
                        lines,
                        child,
                        now_local,
                        level + 1,
                        show_subtask_notes,
                        show_notes,
                        show_subtask_assignment_fields,
                    )

        if show_notes:
            notes = clean_notes(task)
            if notes and (not lines or lines[-1] != ''):
                lines.append('')
            render_notes_block(lines, "Notes" if not notes else bold(f'Notes ({len(notes)})'), notes, True)


def build_task_view(
    tasks: list[dict],
    task_id: str | None = None,
    now_local: datetime | None = None,
    status: str = "",
    show_subtask_notes: bool = False,
    input_file: str | None = None,
) -> str:
    if now_local is None:
        now_local = datetime.now(TZ_TAIPEI)

    lines: list[str] = []
    if not tasks:
        lines.append(color('No tasks', YELLOW))
        return '\n'.join(lines) + '\n'

    selected = get_view_task(tasks, task_id=task_id)
    if not isinstance(selected, dict):
        lines.append(color('Selected task is invalid', YELLOW))
        return '\n'.join(lines) + '\n'

    show_notes = detect_action_mode(input_file) != "coworker"
    show_subtask_assignment_fields = detect_action_mode(input_file) != "coworker"
    render_task_block(
        lines,
        selected,
        now_local,
        2,
        show_subtask_notes,
        show_notes,
        show_subtask_assignment_fields,
    )
    if status:
        if not lines or lines[-1] != '':
            lines.append('')
        lines.append(status)
    if not lines or lines[-1] != '':
        lines.append('')
    lines.append(build_actions_line(input_file, selected_task=selected))
    return '\n'.join(lines).rstrip() + '\n'


def build_latest_view(
    tasks: list[dict],
    now_local: datetime | None = None,
    status: str = "",
    show_subtask_notes: bool = False,
    input_file: str | None = None,
) -> str:
    return build_task_view(
        tasks,
        now_local=now_local,
        status=status,
        show_subtask_notes=show_subtask_notes,
        input_file=input_file,
    )


def resolve_input_path(input_file: str | None = None, fake_script: Path | None = None) -> Path:
    script_file = fake_script or Path(__file__)
    if input_file:
        candidate = Path(input_file).expanduser()
        if candidate.is_absolute():
            return candidate
        return script_file.resolve().parent / candidate
    return script_file.resolve().parent / 'tasks.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', help='input JSON path relative to script dir or absolute path')
    parser.add_argument('--id', help='specific task id to view instead of latest')
    parser.add_argument('--once', action='store_true', help='print once and exit')
    parser.add_argument('--interval', type=float, default=1.0, help='refresh seconds for live mode')
    args = parser.parse_args()

    in_path = resolve_input_path(args.file)

    show_notes = False
    input_file = str(in_path.resolve())
    base_allowed_actions = set(allowed_actions_for_mode(detect_action_mode(input_file)))

    def render_once(status: str = ""):
        data = json.loads(in_path.read_text(encoding='utf-8'))
        tasks = normalize_tasks(data)
        return build_task_view(
            tasks,
            task_id=args.id,
            status=status,
            show_subtask_notes=show_notes,
            input_file=input_file,
        )

    if args.once:
        print(render_once(), end='')
        return

    interval = max(0.2, args.interval)
    status = ""
    status_until = 0.0
    script_dir = str(Path(__file__).resolve().parent)
    stdin_fd = sys.stdin.fileno()
    old_term = termios.tcgetattr(stdin_fd)
    tty.setcbreak(stdin_fd)
    # Hide cursor in live mode for cleaner redraw.
    sys.stdout.write('\x1b[?25l')
    # Ensure we start from a clean visible frame.
    sys.stdout.write('\x1b[2J\x1b[H')
    sys.stdout.flush()
    try:
        while True:
            visible_status = status if time.time() < status_until else ""
            frame = render_once(status=visible_status)
            # Full-screen redraw avoids stale wrapped rows accumulating.
            sys.stdout.write('\x1b[H\x1b[J')
            sys.stdout.write(frame)
            sys.stdout.flush()
            ready, _, _ = select.select([sys.stdin], [], [], interval)
            if ready:
                ch = os.read(stdin_fd, 1)
                if ch == b"q":
                    break
                if ch == b"t" and "t" in base_allowed_actions:
                    try:
                        add_proc = subprocess.run(
                            build_add_task_command(script_dir, input_file),
                            capture_output=True,
                            text=True,
                            cwd=script_dir,
                        )
                        if add_proc.returncode != 0:
                            msg = (add_proc.stderr or add_proc.stdout or "Add failed").strip()
                            status = color(f"Error: {msg}", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                        else:
                            out = (add_proc.stdout or "").strip()
                            if "Warning:" in out:
                                status = out
                                status_until = time.time() + STATUS_TTL_SECONDS
                            else:
                                status = ""
                                status_until = 0.0
                    except Exception as exc:
                        status = color(f"Error: Add failed: {exc}", RED)
                        status_until = time.time() + STATUS_TTL_SECONDS
                if ch == b"a" and "a" in base_allowed_actions:
                    try:
                        clipboard_proc = subprocess.run(
                            ["wl-paste"],
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        clipboard_text = clipboard_proc.stdout
                        if not clipboard_text.strip():
                            status = color("Error: Clipboard is empty.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
                        cmd = build_assign_coworker_command(script_dir, input_file)
                        cmd[-1] = clipboard_text
                        assign_proc = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            cwd=script_dir,
                        )
                        if assign_proc.returncode != 0:
                            msg = (assign_proc.stderr or assign_proc.stdout or "Assign failed").strip()
                            status = color(f"Error: {msg}", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                        else:
                            status = ""
                            status_until = 0.0
                    except Exception as exc:
                        status = color(f"Error: Assign failed: {exc}", RED)
                        status_until = time.time() + STATUS_TTL_SECONDS
                if ch == b"c" and "c" in base_allowed_actions:
                    try:
                        clipboard_proc = subprocess.run(
                            ["wl-paste"],
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        clipboard_text = clipboard_proc.stdout
                        if not clipboard_text.strip():
                            status = color("Error: Clipboard is empty.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
                        cmd = build_confirm_task_start_command(script_dir, input_file)
                        cmd[-1] = clipboard_text
                        start_proc = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            cwd=script_dir,
                        )
                        if start_proc.returncode != 0:
                            msg = (start_proc.stderr or start_proc.stdout or "Confirm task start failed").strip()
                            status = color(f"Error: {msg}", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                        else:
                            status = ""
                            status_until = 0.0
                    except Exception as exc:
                        status = color(f"Error: Confirm task start failed: {exc}", RED)
                        status_until = time.time() + STATUS_TTL_SECONDS
                if ch == b"s" and "s" in base_allowed_actions:
                    try:
                        data = json.loads(in_path.read_text(encoding='utf-8'))
                        tasks = normalize_tasks(data)
                        selected_task = get_view_task(tasks, task_id=args.id)
                        selected_id = str(selected_task.get("id") or "").strip() if isinstance(selected_task, dict) else ""
                        if not selected_id:
                            status = color("Error: No selected task id found.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
                        clipboard_proc = subprocess.run(
                            ["wl-paste"],
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        clipboard_text = clipboard_proc.stdout
                        if not clipboard_text.strip():
                            status = color("Error: Clipboard is empty.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
                        cmd = build_add_to_latest_command(script_dir, selected_id, "children", input_file)
                        cmd[-1] = clipboard_text
                        add_proc = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            cwd=script_dir,
                        )
                        if add_proc.returncode != 0:
                            msg = (add_proc.stderr or add_proc.stdout or "Add failed").strip()
                            status = color(f"Error: {msg}", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                        else:
                            status = ""
                            status_until = 0.0
                    except Exception as exc:
                        status = color(f"Error: Add failed: {exc}", RED)
                        status_until = time.time() + STATUS_TTL_SECONDS
                if ch == b"n" and "n" in base_allowed_actions:
                    try:
                        data = json.loads(in_path.read_text(encoding='utf-8'))
                        tasks = normalize_tasks(data)
                        selected_task = get_view_task(tasks, task_id=args.id)
                        if not isinstance(selected_task, dict):
                            status = color("Error: Selected task is invalid.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
                        latest_task = selected_task
                        latest_id = str(selected_task.get("id") or "").strip()
                        if not latest_id:
                            status = color("Error: No selected task id found.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
                        target_id = latest_id
                        options = build_notes_target_options(latest_task)
                        if len(options) > 1:
                            pick_idx, pick_err, should_quit = choose_numbered_option(
                                stdin_fd=stdin_fd,
                                render_once_fn=render_once,
                                title="Select notes target",
                                options=options,
                                invalid_selection_msg="Error: Enter a valid number to select a task.",
                            )
                            if should_quit:
                                break
                            if pick_err:
                                status = color(pick_err, RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                            if pick_idx is None:
                                status = ""
                                status_until = 0.0
                                continue
                            target_id = options[pick_idx][0]
                        clipboard_proc = subprocess.run(
                            ["wl-paste"],
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        clipboard_text = clipboard_proc.stdout
                        if not clipboard_text.strip():
                            status = color("Error: Clipboard is empty.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
                        cmd = build_add_notes_command(script_dir, target_id, input_file)
                        cmd[-1] = clipboard_text
                        add_proc = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            cwd=script_dir,
                        )
                        if add_proc.returncode != 0:
                            msg = (add_proc.stderr or add_proc.stdout or "Add failed").strip()
                            status = color(f"Error: {msg}", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                        else:
                            status = ""
                            status_until = 0.0
                    except Exception as exc:
                        status = color(f"Error: Add failed: {exc}", RED)
                        status_until = time.time() + STATUS_TTL_SECONDS
                if ch == b"v" and "v" in base_allowed_actions:
                    show_notes = not show_notes
                if ch == b"d" and "d" in base_allowed_actions:
                    try:
                        data = json.loads(in_path.read_text(encoding='utf-8'))
                        tasks = normalize_tasks(data)
                        selected_task = get_view_task(tasks, task_id=args.id)
                        if not isinstance(selected_task, dict):
                            status = color("Error: Selected task is invalid.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
                        clipboard_proc = subprocess.run(
                            ["wl-paste"],
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        clipboard_text = clipboard_proc.stdout
                        selected_id = str(selected_task.get("id") or "").strip()
                        if not selected_id:
                            status = color("Error: No selected task id found.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
                        inserted_count = ingest_deadline_extension_subtasks(tasks, selected_id, clipboard_text)
                        if inserted_count > 0:
                            normalized_tasks = [normalize_task_shape(task) for task in tasks if isinstance(task, dict)]
                            in_path.write_text(
                                json.dumps(normalized_tasks, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8",
                            )
                            data = json.loads(in_path.read_text(encoding='utf-8'))
                            tasks = normalize_tasks(data)
                            selected_task = get_view_task(tasks, task_id=args.id)
                            if not isinstance(selected_task, dict):
                                status = color("Error: Selected task is invalid.", RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                        message = build_confirm_deadline_extension_status(selected_task, clipboard_text)
                        status_color = YELLOW if message.startswith("Warning:") else GREEN
                        status = color(message, status_color)
                        status_until = time.time() + STATUS_TTL_SECONDS
                    except Exception as exc:
                        status = color(f"Error: Confirm deadline extension failed: {exc}", RED)
                        status_until = time.time() + STATUS_TTL_SECONDS
                if ch == b"m":
                    try:
                        data = json.loads(in_path.read_text(encoding='utf-8'))
                        tasks = normalize_tasks(data)
                        selected_task = get_view_task(tasks, task_id=args.id)
                        latest_id = str(selected_task.get("id") or "").strip() if isinstance(selected_task, dict) else ""
                        if not latest_id:
                            status = color("Error: No selected task id found.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
                        msg_options = build_message_target_options(selected_task, input_file=input_file)
                        if not msg_options:
                            continue
                        pick_idx, pick_err, should_quit = choose_numbered_option(
                            stdin_fd=stdin_fd,
                            render_once_fn=render_once,
                            title="Select message type",
                            options=msg_options,
                            invalid_selection_msg="Error: Enter a valid number to select a message.",
                        )
                        if should_quit:
                            break
                        if pick_err:
                            status = color(pick_err, RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
                        if pick_idx is None:
                            status = ""
                            status_until = 0.0
                            continue
                        picked_kind = msg_options[pick_idx][0]
                        if picked_kind == "deadline-extension":
                            msg_cmd = build_deadline_message_command(script_dir, str(in_path.resolve()), latest_id)
                            msg_proc = subprocess.run(msg_cmd, capture_output=True, text=True)
                            if msg_proc.returncode != 0:
                                msg = (msg_proc.stderr or msg_proc.stdout or "Message generation failed").strip()
                                status = color(f"Error: {msg}", RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                            message_text = msg_proc.stdout.strip()
                            if not message_text:
                                status = color("Error: Generated message is empty.", RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                            copy_proc = subprocess.Popen(
                                ["wl-copy"],
                                stdin=subprocess.PIPE,
                                text=True,
                            )
                            if copy_proc.stdin:
                                copy_proc.stdin.write(message_text)
                                copy_proc.stdin.close()
                            status = color(DEADLINE_MESSAGE_COPIED_STATUS, GREEN)
                            status_until = time.time() + STATUS_TTL_SECONDS
                        elif picked_kind == "task-initiation":
                            msg_cmd = build_task_initiation_message_command(script_dir, str(in_path.resolve()), latest_id)
                            msg_proc = subprocess.run(msg_cmd, capture_output=True, text=True)
                            if msg_proc.returncode != 0:
                                msg = (msg_proc.stderr or msg_proc.stdout or "Message generation failed").strip()
                                status = color(f"Error: {msg}", RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                            message_text = msg_proc.stdout.strip()
                            if not message_text:
                                status = color("Error: Generated message is empty.", RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                            copy_proc = subprocess.Popen(
                                ["wl-copy"],
                                stdin=subprocess.PIPE,
                                text=True,
                            )
                            if copy_proc.stdin:
                                copy_proc.stdin.write(message_text)
                                copy_proc.stdin.close()
                            status = color(TASK_INITIATION_MESSAGE_COPIED_STATUS, GREEN)
                            status_until = time.time() + STATUS_TTL_SECONDS
                        elif picked_kind == "task-assignment":
                            msg_cmd = build_task_assignment_message_command(script_dir, str(in_path.resolve()), latest_id)
                            msg_proc = subprocess.run(msg_cmd, capture_output=True, text=True)
                            if msg_proc.returncode != 0:
                                msg = (msg_proc.stderr or msg_proc.stdout or "Message generation failed").strip()
                                status = color(f"Error: {msg}", RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                            message_text = msg_proc.stdout.strip()
                            if not message_text:
                                status = color("Error: Generated message is empty.", RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                            copy_proc = subprocess.Popen(
                                ["wl-copy"],
                                stdin=subprocess.PIPE,
                                text=True,
                            )
                            if copy_proc.stdin:
                                copy_proc.stdin.write(message_text)
                                copy_proc.stdin.close()
                            status = color(SUBS_SUMMARY_MESSAGE_COPIED_STATUS, GREEN)
                            status_until = time.time() + STATUS_TTL_SECONDS
                        else:
                            clipboard_proc = subprocess.run(
                                ["wl-paste"],
                                capture_output=True,
                                text=True,
                                check=True,
                            )
                            next_assigner, next_task_name = parse_next_task_clipboard_payload(clipboard_proc.stdout)
                            if not next_task_name:
                                status = color("Error: Clipboard is empty.", RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                            msg_cmd = build_task_completion_message_command(
                                script_dir,
                                str(in_path.resolve()),
                                latest_id,
                                next_task_name,
                                next_assigner,
                            )
                            msg_proc = subprocess.run(msg_cmd, capture_output=True, text=True)
                            if msg_proc.returncode != 0:
                                msg = (msg_proc.stderr or msg_proc.stdout or "Message generation failed").strip()
                                status = color(f"Error: {msg}", RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                            message_text = msg_proc.stdout.strip()
                            if not message_text:
                                status = color("Error: Generated message is empty.", RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                            copy_proc = subprocess.Popen(
                                ["wl-copy"],
                                stdin=subprocess.PIPE,
                                text=True,
                            )
                            if copy_proc.stdin:
                                copy_proc.stdin.write(message_text)
                                copy_proc.stdin.close()
                            status = color(NEXT_TASK_MESSAGE_COPIED_STATUS, GREEN)
                            status_until = time.time() + STATUS_TTL_SECONDS
                    except Exception as exc:
                        status = color(f"Error: Message failed: {exc}", RED)
                        status_until = time.time() + STATUS_TTL_SECONDS
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_term)
        # Show cursor again before exit.
        sys.stdout.write('\x1b[?25h')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
