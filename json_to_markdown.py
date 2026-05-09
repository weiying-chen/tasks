#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

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


def normalize_tasks(data):
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError('JSON must be an object or array of objects')


def render(tasks: list[dict]) -> str:
    lines: list[str] = ['# Tasks', '']
    for task in tasks:
        name = task.get('name') or task.get('title') or '(Untitled)'
        owner = task.get('owner', '-')
        created_at = task.get('createdAt')
        deadline = task.get('deadline')
        work_minutes = task.get('workMinutes')

        lines.append(f'## {name}')
        lines.append('')
        lines.append(f'- Owner: {owner}')
        lines.append(f"- Created: {to_local_display(created_at) if isinstance(created_at, str) else '-'}")
        lines.append(f"- Deadline: {to_local_display(deadline) if isinstance(deadline, str) else '-'}")
        lines.append(f'- Work time: {fmt_work(work_minutes)}')
        lines.append('')

    return '\n'.join(lines).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile', default='tasks.json', help='input JSON path')
    parser.add_argument('-o', '--out', default='tasks.md', help='output markdown path')
    args = parser.parse_args()

    in_path = Path(args.infile)
    out_path = Path(args.out)

    data = json.loads(in_path.read_text(encoding='utf-8'))
    tasks = normalize_tasks(data)
    md = render(tasks)
    out_path.write_text(md, encoding='utf-8')
    print(f'Wrote {out_path}')


if __name__ == '__main__':
    main()
