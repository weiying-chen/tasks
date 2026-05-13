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
from work_time_adjustments import adjusted_child_minutes

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


def build_add_to_latest_command(script_dir: str, parent_id: str) -> list[str]:
    return ["python3", f"{script_dir}/text_to_json.py", "--parent-id", parent_id, "__CLIPBOARD__"]


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


def task_base_created(task: dict, now_local: datetime) -> datetime:
    created_at = task.get('createdAt')
    if isinstance(created_at, str):
        return to_local(created_at)

    created_date = task.get('createdDate')
    if isinstance(created_date, str):
        return datetime.fromisoformat(f'{created_date}T09:00:00+08:00')

    return now_local


def task_deadline(task: dict, now_local: datetime, is_child: bool) -> datetime | None:
    deadline = task.get('deadline')
    if isinstance(deadline, str):
        return to_local(deadline)

    deadline_date = task.get('deadlineDate')
    if isinstance(deadline_date, str):
        return datetime.fromisoformat(f'{deadline_date}T17:00:00+08:00')

    work_minutes = task.get('workMinutes')
    if not isinstance(work_minutes, int):
        return None

    effective_minutes = adjusted_child_minutes(work_minutes) if is_child else work_minutes
    start = next_work_start(task_base_created(task, now_local))
    return add_work_minutes(start, effective_minutes)


def child_total_minutes(task: dict) -> int:
    total = 0
    children = task.get('children')
    if not isinstance(children, list):
        return 0
    for child in children:
        if not isinstance(child, dict):
            continue
        minutes = child.get('workMinutes')
        if isinstance(minutes, int) and minutes > 0:
            total += adjusted_child_minutes(minutes)
    return total


def fmt_countdown(now_local: datetime, target: datetime | None) -> str:
    if target is None:
        return '-'
    total_seconds = work_seconds_between(now_local, target)
    overdue = total_seconds < 0
    total_seconds = abs(total_seconds)

    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    label = f'{hours}h {minutes}m {seconds}s'
    return f'Overdue by {label}' if overdue else f'{label}'


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
    is_child = level > 2
    created = next_work_start(task_base_created(task, now_local))
    deadline = task_deadline(task, now_local, is_child=is_child)
    work_minutes = task.get('workMinutes')
    if is_child and isinstance(work_minutes, int):
        work_minutes = adjusted_child_minutes(work_minutes)

    name = task.get("name") or "(Untitled)"
    if is_child:
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
        color('Actions: ', BLUE)
        + color('a', GREEN) + color('dd subtask', BLUE)
        + color(' | ', BLUE)
        + color('c', GREEN) + color('reate deadline message', BLUE)
        + color(' | ', BLUE)
        + color('q', GREEN) + color('uit', BLUE)
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

    previous_lines = 0
    interval = max(0.2, args.interval)
    status = ""
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
            frame = render_once(status=status)
            frame_lines = frame.splitlines()
            # Move back to the start of previous frame and redraw in place.
            if previous_lines > 0:
                sys.stdout.write(f'\x1b[{previous_lines}F')
            sys.stdout.write('\x1b[J')
            sys.stdout.write(frame)
            sys.stdout.flush()
            previous_lines = len(frame_lines)
            status = ""
            ready, _, _ = select.select([sys.stdin], [], [], interval)
            if ready:
                ch = os.read(stdin_fd, 1)
                if ch == b"q":
                    break
                if ch == b"a":
                    try:
                        data = json.loads(in_path.read_text(encoding='utf-8'))
                        tasks = normalize_tasks(data)
                        latest_id = find_latest_task_id(tasks)
                        if not latest_id:
                            status = color("No latest task id found.", RED)
                            continue
                        clipboard_proc = subprocess.run(
                            ["wl-paste"],
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        clipboard_text = clipboard_proc.stdout
                        if not clipboard_text.strip():
                            status = color("Clipboard is empty.", RED)
                            continue
                        cmd = build_add_to_latest_command(script_dir, latest_id)
                        cmd[-1] = clipboard_text
                        add_proc = subprocess.run(cmd, capture_output=True, text=True)
                        if add_proc.returncode != 0:
                            msg = (add_proc.stderr or add_proc.stdout or "Add failed").strip()
                            status = color(msg, RED)
                        else:
                            status = ""
                    except Exception as exc:
                        status = color(f"Add failed: {exc}", RED)
                if ch == b"c":
                    try:
                        data = json.loads(in_path.read_text(encoding='utf-8'))
                        tasks = normalize_tasks(data)
                        latest_id = find_latest_task_id(tasks)
                        if not latest_id:
                            status = color("No latest task id found.", RED)
                            continue
                        msg_cmd = build_deadline_message_command(script_dir, str(in_path.resolve()), latest_id)
                        msg_proc = subprocess.run(msg_cmd, capture_output=True, text=True)
                        if msg_proc.returncode != 0:
                            msg = (msg_proc.stderr or msg_proc.stdout or "Message generation failed").strip()
                            status = color(msg, RED)
                            continue
                        message_text = msg_proc.stdout.strip()
                        if not message_text:
                            status = color("Generated message is empty.", RED)
                            continue
                        copy_proc = subprocess.run(
                            ["wl-copy"],
                            input=message_text,
                            text=True,
                            capture_output=True,
                        )
                        if copy_proc.returncode != 0:
                            msg = (copy_proc.stderr or copy_proc.stdout or "Copy failed").strip()
                            status = color(msg, RED)
                        else:
                            status = color("Deadline message copied.", GREEN)
                    except Exception as exc:
                        status = color(f"Message failed: {exc}", RED)
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_term)
        # Show cursor again before exit.
        sys.stdout.write('\x1b[?25h')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
