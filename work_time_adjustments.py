#!/usr/bin/env python3

CHILD_WORK_FACTOR = 0.8


def round_minutes_to_step(raw_minutes: int, step: int = 10) -> int:
    if raw_minutes <= 0:
        return 0
    return max(step, int((raw_minutes / step) + 0.5) * step)


def js_math_round(x: float) -> int:
    return int(x + 0.5) if x >= 0 else int(x - 0.5)


def adjusted_child_minutes(raw_minutes: int, factor: float = CHILD_WORK_FACTOR) -> int:
    if raw_minutes <= 0:
        return 0
    adjusted = max(1, js_math_round(raw_minutes * factor))
    return round_minutes_to_step(adjusted)
