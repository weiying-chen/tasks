#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from work_time import add_work_minutes

TZ_TAIPEI = timezone(timedelta(hours=8))


def to_local_display(iso_str: str) -> str:
    dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    return dt.astimezone(TZ_TAIPEI).strftime('%Y-%m-%d %a %H:%M')


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


def parse_base_deadline_local(task: dict) -> datetime | None:
    deadline = task.get('deadline')
    if isinstance(deadline, str):
        dt = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
        return dt.astimezone(TZ_TAIPEI)

    deadline_date = task.get('deadlineDate')
    if isinstance(deadline_date, str):
        return datetime.fromisoformat(f"{deadline_date}T17:00:00+08:00")

    return None


def parse_base_created_local(task: dict) -> datetime | None:
    created_at = task.get('createdAt')
    if isinstance(created_at, str):
        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        return dt.astimezone(TZ_TAIPEI)

    created_date = task.get('createdDate')
    if isinstance(created_date, str):
        return datetime.fromisoformat(f"{created_date}T09:00:00+08:00")

    return None


def sum_immediate_children_work_minutes(task: dict) -> int:
    total = 0
    children = task.get('children')
    if not isinstance(children, list):
        return 0
    for child in children:
        if not isinstance(child, dict):
            continue
        minutes = child.get('workMinutes')
        if isinstance(minutes, int) and minutes > 0:
            total += minutes
    return total


def normalize_tasks(data):
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError('JSON must be an object or array of objects')


def render_task(lines: list[str], task: dict, level: int, factor: float, now_local: datetime) -> None:
    name = task.get('name') or task.get('title') or '(Untitled)'
    created_at = task.get('createdAt')
    deadline = task.get('deadline')
    created_date = task.get('createdDate')
    deadline_date = task.get('deadlineDate')
    work_minutes = task.get('workMinutes')

    heading_prefix = '#' * min(6, level)
    lines.append(f'{heading_prefix} {name}')
    lines.append('')
    created_display = (
        to_local_display(created_at)
        if isinstance(created_at, str)
        else (f"{created_date} {datetime.fromisoformat(created_date).strftime('%a')} 09:00" if isinstance(created_date, str) else '-')
    )
    deadline_display = (
        to_local_display(deadline)
        if isinstance(deadline, str) else '-'
    )
    # For date-only tasks, derive display times from work-time schedule.
    if not isinstance(deadline, str) and isinstance(created_date, str) and isinstance(work_minutes, int):
        derived_created = now_local
        derived_deadline = add_work_minutes(derived_created, work_minutes)
        created_display = derived_created.strftime('%Y-%m-%d %a %H:%M')
        deadline_display = derived_deadline.strftime('%Y-%m-%d %a %H:%M')
    elif not isinstance(deadline, str) and isinstance(deadline_date, str):
        deadline_display = f"{deadline_date} {datetime.fromisoformat(deadline_date).strftime('%a')} 17:00"
    lines.append(f"- Created: {created_display}")
    lines.append(f"- Deadline: {deadline_display}")
    base_deadline_local = parse_base_deadline_local(task)
    child_minutes = sum_immediate_children_work_minutes(task)
    if base_deadline_local and child_minutes > 0:
        adjusted_minutes = int(round(child_minutes * factor))
        extended = add_work_minutes(base_deadline_local, adjusted_minutes)
        lines.append(f"- Extended deadline: {extended.strftime('%Y-%m-%d %a %H:%M')}")
    lines.append(f'- Work time: {fmt_work(work_minutes)}')
    lines.append('')

    children = task.get('children')
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                render_task(lines, child, level + 1, factor, now_local)


def render(tasks: list[dict], factor: float) -> str:
    lines: list[str] = ['# Tasks', '']
    now_local = datetime.now(TZ_TAIPEI)
    for task in tasks:
        if isinstance(task, dict):
            render_task(lines, task, 2, factor, now_local)

    return '\n'.join(lines).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile', default='tasks.json', help='input JSON path')
    parser.add_argument('-o', '--out', default='tasks.md', help='output markdown path')
    parser.add_argument('--factor', type=float, default=0.8, help='multiplier for child work minutes')
    args = parser.parse_args()

    in_path = Path(args.infile)
    out_path = Path(args.out)

    data = json.loads(in_path.read_text(encoding='utf-8'))
    tasks = normalize_tasks(data)
    md = render(tasks, args.factor)
    out_path.write_text(md, encoding='utf-8')
    print(f'Wrote {out_path}')


if __name__ == '__main__':
    main()
