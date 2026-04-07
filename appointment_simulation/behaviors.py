from __future__ import annotations

import math
from typing import Callable


ProbabilityFn = Callable[[int], float]


def clamp_probability(value: float) -> float:
    return max(0.0, min(1.0, value))


def constant_probability(value: float) -> ProbabilityFn:
    probability = clamp_probability(value)

    def fn(_: int) -> float:
        return probability

    return fn


def step_balking(
    threshold: int,
    low_delay_probability: float = 0.0,
    high_delay_probability: float = 1.0,
) -> ProbabilityFn:
    low_delay_probability = clamp_probability(low_delay_probability)
    high_delay_probability = clamp_probability(high_delay_probability)
    if threshold < 0:
        raise ValueError("threshold must be non-negative")

    def fn(tau: int) -> float:
        if tau < threshold:
            return low_delay_probability
        return high_delay_probability

    return fn


def logistic_balking(
    midpoint: float,
    slope: float,
    floor: float = 0.0,
    ceiling: float = 1.0,
) -> ProbabilityFn:
    floor = clamp_probability(floor)
    ceiling = clamp_probability(ceiling)
    if ceiling < floor:
        raise ValueError("ceiling must be greater than or equal to floor")

    def fn(tau: int) -> float:
        raw = 1.0 / (1.0 + math.exp(-slope * (tau - midpoint)))
        return clamp_probability(floor + (ceiling - floor) * raw)

    return fn


def exponential_no_show(
    base: float,
    maximum: float,
    scale: float,
) -> ProbabilityFn:
    base = clamp_probability(base)
    maximum = clamp_probability(maximum)
    if maximum < base:
        raise ValueError("maximum must be greater than or equal to base")
    if scale <= 0:
        raise ValueError("scale must be positive")

    def fn(tau: int) -> float:
        return clamp_probability(maximum - (maximum - base) * math.exp(-tau / scale))

    return fn


def green_savin_no_show(
    gamma_0: float,
    gamma_max: float,
    sensitivity: float,
) -> ProbabilityFn:
    """Green-Savin style exponential-saturation no-show probability."""
    return exponential_no_show(base=gamma_0, maximum=gamma_max, scale=sensitivity)
