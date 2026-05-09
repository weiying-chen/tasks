#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from work_time import add_work_minutes

TZ_TAIPEI = timezone(timedelta(hours=8))


def to_local_display(iso_str: str) -> str:
    dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    return dt.astimezone(TZ_TAIPEI).strftime('%Y-%m-%d %H:%M')


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


def normalize_tasks(data):
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError('JSON must be an object or array of objects')


def render_task(lines: list[str], task: dict, level: int, parent_deadline_local: datetime | None, factor: float) -> None:
    name = task.get('name') or task.get('title') or '(Untitled)'
    owner = task.get('owner', '-')
    created_at = task.get('createdAt')
    deadline = task.get('deadline')
    created_date = task.get('createdDate')
    deadline_date = task.get('deadlineDate')
    work_minutes = task.get('workMinutes')

    heading_prefix = '#' * min(6, level)
    lines.append(f'{heading_prefix} {name}')
    lines.append('')
    lines.append(f'- Owner: {owner}')
    created_display = (
        to_local_display(created_at)
        if isinstance(created_at, str)
        else (created_date if isinstance(created_date, str) else '-')
    )
    deadline_display = (
        to_local_display(deadline)
        if isinstance(deadline, str)
        else (deadline_date if isinstance(deadline_date, str) else '-')
    )
    lines.append(f"- Created: {created_display}")
    lines.append(f"- Deadline: {deadline_display}")
    lines.append(f'- Work time: {fmt_work(work_minutes)}')
    if level > 2 and parent_deadline_local and isinstance(work_minutes, int):
        adjusted_minutes = int(round(work_minutes * factor))
        extended = add_work_minutes(parent_deadline_local, adjusted_minutes)
        lines.append(f"- Extended deadline: {extended.strftime('%Y-%m-%d %H:%M')}")
    lines.append('')

    children = task.get('children')
    current_deadline_local = parse_base_deadline_local(task)
    next_parent_deadline = current_deadline_local or parent_deadline_local
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                render_task(lines, child, level + 1, next_parent_deadline, factor)


def render(tasks: list[dict], factor: float) -> str:
    lines: list[str] = ['# Tasks', '']
    for task in tasks:
        if isinstance(task, dict):
            render_task(lines, task, 2, None, factor)

    return '\n'.join(lines).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile', default='tasks.json', help='input JSON path')
    parser.add_argument('-o', '--out', default='tasks.md', help='output markdown path')
    parser.add_argument('--factor', type=float, default=1.0, help='multiplier for child work minutes')
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
