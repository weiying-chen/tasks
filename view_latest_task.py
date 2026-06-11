#!/usr/bin/env python3
import argparse
import json
import os
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
    get_task_assigned_to,
    get_task_stage,
    get_task_status,
    get_task_type,
    get_task_work_minutes,
)
from create_message import parse_subs_summary_task_name
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


def build_next_task_message_command(
    script_dir: str,
    infile: str,
    finished_task_id: str,
    next_task_name: str,
    next_assignee: str | None = None,
) -> list[str]:
    cmd = [
        "python3",
        f"{script_dir}/create_message.py",
        "-i",
        infile,
        "--type",
        "next-task",
        "--task-id",
        finished_task_id,
        "--next-task-name",
        next_task_name,
    ]
    if next_assignee:
        cmd.extend(["--next-assignee", next_assignee])
    return cmd


def build_subs_summary_message_command(script_dir: str, infile: str, task_id: str) -> list[str]:
    return [
        "python3",
        f"{script_dir}/create_message.py",
        "-i",
        infile,
        "--type",
        "subs-summary",
        "--task-id",
        task_id,
    ]


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


def build_message_target_options(latest_task: dict | None = None) -> list[tuple[str, str]]:
    options = [
        ("deadline-extension", "Deadline extension message"),
        ("next-task", "Task completion message"),
    ]
    if isinstance(latest_task, dict):
        task_name = str(latest_task.get("name") or "").strip()
        if task_name:
            try:
                parse_subs_summary_task_name(task_name)
            except ValueError:
                pass
            else:
                options.append(("subs-summary", "Task assignment message"))
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


def fmt_status(status: str | None) -> str:
    if not isinstance(status, str):
        return "-"
    return status.replace("_", " ").strip()


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
        return
    lines.append(title)
    lines.append('')
    if show_notes:
        for note in notes:
            lines.append(f'• {note}')
        lines.append('')


def render_task_block(lines: list[str], task: dict, now_local: datetime, level: int, show_subtask_notes: bool) -> None:
    created_base = task_base_created_local(task, now_local=now_local) or now_local
    created = next_work_start(created_base)
    deadline = task_deadline_local(task, now_local=now_local)
    work_minutes = get_task_work_minutes(task)
    task_type = get_task_type(task)
    task_stage = get_task_stage(task)
    assigned_to = get_task_assigned_to(task)
    status = get_task_status(task)

    name = task.get("name") or "(Untitled)"

    if level > 2:
        lines.append(f'Name: {name}')
        if isinstance(task_type, str) and task_type.strip():
            lines.append(f'Type: {task_type}')
        if isinstance(task_stage, str) and task_stage.strip():
            lines.append(f'Stage: {task_stage}')
        if isinstance(assigned_to, str) and assigned_to.strip():
            lines.append(f'Assigned to: {assigned_to}')
        if isinstance(status, str) and status.strip():
            lines.append(f'Status: {fmt_status(status)}')
        lines.append(f'Work time: {fmt_work(work_minutes)}')
        lines.append(f'Deadline: {color(to_display(deadline) if deadline else "-", YELLOW)}')
        notes = clean_notes(task)
        render_notes_block(lines, f'Notes ({len(notes)})', notes, show_subtask_notes)
        if not lines or lines[-1] != '':
            lines.append('')
    else:
        lines.append(bold('View task'))
        lines.append('')
        lines.append(f'Name: {name}')
        if isinstance(task_type, str) and task_type.strip():
            lines.append(f'Type: {task_type}')
        if isinstance(task_stage, str) and task_stage.strip():
            lines.append(f'Stage: {task_stage}')
        if isinstance(assigned_to, str) and assigned_to.strip():
            lines.append(f'Assigned to: {assigned_to}')
        if isinstance(status, str) and status.strip():
            lines.append(f'Status: {fmt_status(status)}')
        lines.append(f'Start: {to_display(created)}')
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
        lines.append('')
        children = task.get('children')
        if isinstance(children, list) and children:
            lines.append(bold('Subtasks'))
            lines.append('')

        children = task.get('children')
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    render_task_block(lines, child, now_local, level + 1, show_subtask_notes)

        notes = clean_notes(task)
        render_notes_block(lines, bold(f'Notes ({len(notes)})'), notes, True)


def build_task_view(
    tasks: list[dict],
    task_id: str | None = None,
    now_local: datetime | None = None,
    status: str = "",
    show_subtask_notes: bool = False,
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

    render_task_block(lines, selected, now_local, 2, show_subtask_notes)
    if status:
        if not lines or lines[-1] != '':
            lines.append('')
        lines.append(status)
    if not lines or lines[-1] != '':
        lines.append('')
    lines.append(
        color('Actions: ', MAGENTA)
        + color('create ', MAGENTA) + color('t', GREEN) + color('ask', MAGENTA)
        + color(' | ', MAGENTA)
        + color('set ', MAGENTA) + color('a', GREEN) + color('ssignee', MAGENTA)
        + color(' | ', MAGENTA)
        + color('add ', MAGENTA) + color('s', GREEN) + color('ubtasks', MAGENTA)
        + color(' | ', MAGENTA)
        + color('add ', MAGENTA) + color('n', GREEN) + color('otes', MAGENTA)
        + color(' | ', MAGENTA)
        + color('toggle ', MAGENTA) + color('v', GREEN) + color('iew notes', MAGENTA)
        + color(' | ', MAGENTA)
        + color('copy ', MAGENTA) + color('m', GREEN) + color('essage', MAGENTA)
        + color(' | ', MAGENTA)
        + color('q', GREEN) + color('uit', MAGENTA)
    )
    return '\n'.join(lines).rstrip() + '\n'


def build_latest_view(
    tasks: list[dict],
    now_local: datetime | None = None,
    status: str = "",
    show_subtask_notes: bool = False,
) -> str:
    return build_task_view(tasks, now_local=now_local, status=status, show_subtask_notes=show_subtask_notes)


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

    def render_once(status: str = ""):
        data = json.loads(in_path.read_text(encoding='utf-8'))
        tasks = normalize_tasks(data)
        return build_task_view(tasks, task_id=args.id, status=status, show_subtask_notes=show_notes)

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
                if ch == b"t":
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
                if ch == b"a":
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
                if ch == b"s":
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
                if ch == b"n":
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
                if ch == b"v":
                    show_notes = not show_notes
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
                        msg_options = build_message_target_options(selected_task)
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
                        elif picked_kind == "subs-summary":
                            msg_cmd = build_subs_summary_message_command(script_dir, str(in_path.resolve()), latest_id)
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
                            next_assignee, next_task_name = parse_next_task_clipboard_payload(clipboard_proc.stdout)
                            if not next_task_name:
                                status = color("Error: Clipboard is empty.", RED)
                                status_until = time.time() + STATUS_TTL_SECONDS
                                continue
                            msg_cmd = build_next_task_message_command(
                                script_dir,
                                str(in_path.resolve()),
                                latest_id,
                                next_task_name,
                                next_assignee,
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
