import re

from task_assigned_by import SUBS_ASSIGNED_BY


def format_program_selection_title(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r"^【([^】]+)】\s*(.+)$", line)
        if not match:
            continue

        program = match.group(1).strip()
        title = match.group(2).strip()
        title = title.split("|", 1)[0].strip()
        date_match = re.search(r"\s*[-－—]\s*(\d{8})\s*$", title)
        if date_match:
            title = title[: date_match.start()].strip()

        if title:
            return f"{program} ({title})"
    return None


def mapped_program_name(name: str) -> str | None:
    if "節目部選" not in name:
        return None
    for program in SUBS_ASSIGNED_BY:
        if program in name:
            return program
    return None


def extract_subs_task_name(text: str) -> str | None:
    formatted = format_program_selection_title(text)
    if formatted:
        return formatted

    match = re.search(r"翻譯\s*([^，,\n]+?)\s*[，,]", text)
    if match:
        name = match.group(1).strip()
        return mapped_program_name(name) or name
    return None
