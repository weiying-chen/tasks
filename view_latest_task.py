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

from work_time import add_work_minutes, next_work_start

TZ_TAIPEI = timezone(timedelta(hours=8))
WORK_BLOCKS = (
    ((8, 0), (12, 0)),
    ((13, 0), (17, 0)),
)
RESET = '\x1b[0m'
YELLOW = '\x1b[33m'   # theme yellow
GREEN = '\x1b[32m'    # theme green
RED = '\x1b[31m'      # terminal red (git-style error emphasis)
BLUE = '\x1b[34m'     # theme blue
MAGENTA = '\x1b[35m'  # ANSI magenta (matches repo-sync DIRTY)
STATUS_TTL_SECONDS = 4.0
DEADLINE_MESSAGE_COPIED_STATUS = "Success: Deadline extension message copied to clipboard"
NEXT_TASK_MESSAGE_COPIED_STATUS = "Success: Next task message copied to clipboard"


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


def build_add_to_latest_command(script_dir: str, parent_id: str, target: str = "children") -> list[str]:
    return [
        "python3",
        f"{script_dir}/text_to_json.py",
        "--parent-id",
        parent_id,
        "--target",
        target,
        "__CLIPBOARD__",
    ]


def build_add_task_command(script_dir: str) -> list[str]:
    return [f"{script_dir}/add_task.sh"]


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


def parse_next_task_clipboard_payload(clipboard_text: str) -> tuple[str | None, str]:
    text = clipboard_text.strip()
    if not text:
        return None, ""
    return None, text


def task_base_created(task: dict, now_local: datetime) -> datetime:
    created_at = task.get('createdAt')
    if isinstance(created_at, str):
        return to_local(created_at)

    created_date = task.get('createdDate')
    if isinstance(created_date, str):
        return datetime.fromisoformat(f'{created_date}T09:00:00+08:00')

    return now_local


def task_deadline(task: dict, now_local: datetime) -> datetime | None:
    deadline = task.get('deadline')
    if isinstance(deadline, str):
        return to_local(deadline)

    deadline_date = task.get('deadlineDate')
    if isinstance(deadline_date, str):
        return datetime.fromisoformat(f'{deadline_date}T17:00:00+08:00')

    base_work_minutes = task.get('workMinutes')
    if not isinstance(base_work_minutes, int):
        return None

    start = next_work_start(task_base_created(task, now_local))
    return add_work_minutes(start, base_work_minutes)


def child_total_minutes(task: dict) -> int:
    total = 0
    children = task.get('children')
    if not isinstance(children, list):
        return 0
    for child in children:
        if not isinstance(child, dict):
            continue
        base_child_minutes = child.get('workMinutes')
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


def color(text: str, code: str) -> str:
    return f'{code}{text}{RESET}'


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


def render_task_block(lines: list[str], task: dict, now_local: datetime, level: int) -> None:
    created = next_work_start(task_base_created(task, now_local))
    deadline = task_deadline(task, now_local)
    work_minutes = task.get('workMinutes')

    name = task.get("name") or "(Untitled)"
    if level > 2:
        lines.append(f'Name: {name}')
        lines.append(f'Work time: {fmt_work(work_minutes)}')
        lines.append(f'Deadline: {color(to_display(deadline) if deadline else "-", YELLOW)}')
        lines.append('')
    else:
        lines.append('Latest task')
        lines.append('')
        lines.append(f'Name: {name}')
        lines.append(f'Created: {to_display(created)}')
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
            lines.append(f'Work time left: {color(fmt_countdown(now_local, extended), GREEN)}')
        else:
            lines.append(f'Work time left: {color(fmt_countdown(now_local, deadline), GREEN)}')
        lines.append('')
        children = task.get('children')
        if isinstance(children, list) and children:
            lines.append('Subtasks')
            lines.append('')

        children = task.get('children')
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    render_task_block(lines, child, now_local, level + 1)

        notes = task.get("notes")
        if isinstance(notes, list):
            rendered_notes = [note.strip() for note in notes if isinstance(note, str) and note.strip()]
            if rendered_notes:
                lines.append('Notes')
                lines.append('')
                for note in rendered_notes:
                    lines.append(f'• {note}')
                lines.append('')


def build_latest_view(tasks: list[dict], now_local: datetime | None = None, status: str = "") -> str:
    if now_local is None:
        now_local = datetime.now(TZ_TAIPEI)

    lines: list[str] = []
    if not tasks:
        lines.append(color('No tasks', YELLOW))
        return '\n'.join(lines) + '\n'

    latest = tasks[-1]
    if not isinstance(latest, dict):
        lines.append(color('Latest task is invalid', YELLOW))
        return '\n'.join(lines) + '\n'

    render_task_block(lines, latest, now_local, 2)
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
        + color('add ', MAGENTA) + color('s', GREEN) + color('ubtasks', MAGENTA)
        + color(' | ', MAGENTA)
        + color('add ', MAGENTA) + color('n', GREEN) + color('otes', MAGENTA)
        + color(' | ', MAGENTA)
        + color('copy ', MAGENTA) + color('e', GREEN) + color('xtension msg', MAGENTA)
        + color(' | ', MAGENTA)
        + color('copy ', MAGENTA) + color('c', GREEN) + color('ompletion msg', MAGENTA)
        + color(' | ', MAGENTA)
        + color('q', GREEN) + color('uit', MAGENTA)
    )
    return '\n'.join(lines).rstrip() + '\n'


def resolve_input_path(fake_script: Path | None = None) -> Path:
    script_file = fake_script or Path(__file__)
    return script_file.resolve().parent / 'tasks.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='print once and exit')
    parser.add_argument('--interval', type=float, default=1.0, help='refresh seconds for live mode')
    args = parser.parse_args()

    in_path = resolve_input_path()

    def render_once(status: str = ""):
        data = json.loads(in_path.read_text(encoding='utf-8'))
        tasks = normalize_tasks(data)
        return build_latest_view(tasks, status=status)

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
                            build_add_task_command(script_dir),
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
                if ch == b"s":
                    try:
                        data = json.loads(in_path.read_text(encoding='utf-8'))
                        tasks = normalize_tasks(data)
                        latest_id = find_latest_task_id(tasks)
                        if not latest_id:
                            status = color("Error: No latest task id found.", RED)
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
                        cmd = build_add_to_latest_command(script_dir, latest_id, "children")
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
                        latest_id = find_latest_task_id(tasks)
                        if not latest_id:
                            status = color("Error: No latest task id found.", RED)
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
                        cmd = build_add_to_latest_command(script_dir, latest_id, "notes")
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
                if ch == b"e":
                    try:
                        data = json.loads(in_path.read_text(encoding='utf-8'))
                        tasks = normalize_tasks(data)
                        latest_id = find_latest_task_id(tasks)
                        if not latest_id:
                            status = color("Error: No latest task id found.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
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
                    except Exception as exc:
                        status = color(f"Error: Message failed: {exc}", RED)
                        status_until = time.time() + STATUS_TTL_SECONDS
                if ch == b"c":
                    try:
                        data = json.loads(in_path.read_text(encoding='utf-8'))
                        tasks = normalize_tasks(data)
                        latest_id = find_latest_task_id(tasks)
                        if not latest_id:
                            status = color("Error: No latest task id found.", RED)
                            status_until = time.time() + STATUS_TTL_SECONDS
                            continue
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
