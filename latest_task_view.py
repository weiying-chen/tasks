#!/usr/bin/env python3
import argparse
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from work_time import add_work_minutes, next_work_start

TZ_TAIPEI = timezone(timedelta(hours=8))
WORK_BLOCKS = (
    ((8, 0), (12, 0)),
    ((13, 0), (17, 0)),
)
RESET = '\x1b[0m'
DIM = '\x1b[2m'
YELLOW = '\x1b[33m'
GREEN = '\x1b[32m'
BROWN = '\x1b[38;5;180m'


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


def round_minutes_to_step(raw_minutes: int, step: int = 10) -> int:
    if raw_minutes <= 0:
        return 0
    return max(step, int((raw_minutes / step) + 0.5) * step)


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

    effective_minutes = round_minutes_to_step(work_minutes) if is_child else work_minutes
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
            total += round_minutes_to_step(minutes)
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
        work_minutes = round_minutes_to_step(work_minutes)

    name = task.get("name") or "(Untitled)"
    if is_child:
        lines.append(f'{color("Name", DIM)}: {name}')
        lines.append(f'{color("Deadline", DIM)}: {color(to_display(deadline) if deadline else "-", YELLOW)}')
        lines.append('')
    else:
        lines.append(color('Latest Task', BROWN))
        lines.append('')
        lines.append(f'{color("Name", DIM)}: {name}')
        lines.append(f'{color("Created", DIM)}: {to_display(created)}')
        lines.append(f'{color("Deadline", DIM)}: {color(to_display(deadline) if deadline else "-", YELLOW)}')
        lines.append(f'{color("Work time", DIM)}: {fmt_work(work_minutes)}')

        extended = None
        child_minutes = child_total_minutes(task)
        if deadline and child_minutes > 0:
            extended = add_work_minutes(deadline, child_minutes)
        if extended:
            lines.append(f'{color("Extended deadline", DIM)}: {to_display(extended)}')
            lines.append(f'{color("Work time left", DIM)}: {color(fmt_countdown(now_local, extended), GREEN)}')
        else:
            lines.append(f'{color("Work time left", DIM)}: {color(fmt_countdown(now_local, deadline), GREEN)}')
        lines.append('')
        children = task.get('children')
        if isinstance(children, list) and children:
            lines.append(color('Child Tasks', BROWN))
            lines.append('')

        children = task.get('children')
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    render_task_block(lines, child, now_local, level + 1)


def build_latest_view(tasks: list[dict], now_local: datetime | None = None) -> str:
    if now_local is None:
        now_local = datetime.now(TZ_TAIPEI)

    lines: list[str] = []
    if not tasks:
        lines.append(color('No tasks', YELLOW + BOLD))
        return '\n'.join(lines) + '\n'

    latest = tasks[-1]
    if not isinstance(latest, dict):
        lines.append(color('Latest task is invalid', YELLOW + BOLD))
        return '\n'.join(lines) + '\n'

    render_task_block(lines, latest, now_local, 2)
    return '\n'.join(lines).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile', default='tasks.json', help='input JSON path')
    parser.add_argument('--once', action='store_true', help='print once and exit')
    parser.add_argument('--interval', type=float, default=1.0, help='refresh seconds for live mode')
    args = parser.parse_args()

    in_path = Path(args.infile)

    def render_once():
        data = json.loads(in_path.read_text(encoding='utf-8'))
        tasks = normalize_tasks(data)
        return build_latest_view(tasks)

    if args.once:
        print(render_once(), end='')
        return

    previous_lines = 0
    interval = max(0.2, args.interval)
    # Hide cursor in live mode for cleaner redraw.
    sys.stdout.write('\x1b[?25l')
    # Ensure we start from a clean visible frame.
    sys.stdout.write('\x1b[2J\x1b[H')
    sys.stdout.flush()
    try:
        while True:
            frame = render_once()
            frame_lines = frame.splitlines()
            # Move back to the start of previous frame and redraw in place.
            if previous_lines > 0:
                sys.stdout.write(f'\x1b[{previous_lines}F')
            sys.stdout.write('\x1b[J')
            sys.stdout.write(frame)
            sys.stdout.flush()
            previous_lines = len(frame_lines)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        # Show cursor again before exit.
        sys.stdout.write('\x1b[?25h')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
