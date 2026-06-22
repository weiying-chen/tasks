#!/usr/bin/env python3
import math

CHILD_WORK_FACTOR = 0.8


def js_math_round(x: float) -> int:
    return int(x + 0.5) if x >= 0 else int(x - 0.5)


def round_minutes_to_step(raw_minutes: float, step: int = 10) -> int:
    if raw_minutes <= 0:
        return 0
    return max(step, math.ceil(raw_minutes / step) * step)


def adjusted_extension_minutes(raw_minutes: int, factor: float = CHILD_WORK_FACTOR) -> int:
    if raw_minutes <= 0:
        return 0
    return round_minutes_to_step(raw_minutes * factor)
