from __future__ import annotations

import math
from typing import Callable


ProbabilityFn = Callable[[int], float]
CancellationFn = Callable[[int, int], float]


def clamp_probability(value: float) -> float:
    """Clip a numeric value to the probability interval ``[0, 1]``."""
    return max(0.0, min(1.0, value))


def constant_probability(value: float) -> ProbabilityFn:
    """Return a delay-independent probability function."""
    probability = clamp_probability(value)

    def fn(_: int) -> float:
        return probability

    return fn


def linear_taper_cancellation(
    base: float,
    slope: float,
    ceiling: float,
) -> CancellationFn:
    """
    Return a simple daily cancellation rule ``phi(tau, r)``.

    The returned function increases with the original promised delay ``tau``
    through ``min(base + slope * tau, ceiling)`` and decreases as the
    appointment approaches through the taper factor ``r / tau``.
    """
    base = clamp_probability(base)
    ceiling = clamp_probability(ceiling)
    if slope < 0:
        raise ValueError("slope must be non-negative")
    if ceiling < base:
        raise ValueError("ceiling must be greater than or equal to base")

    def fn(tau: int, residual_delay: int) -> float:
        if tau <= 0 or residual_delay <= 0:
            return 0.0
        if residual_delay > tau:
            residual_delay = tau
        level = min(base + slope * tau, ceiling)
        return clamp_probability(level * (residual_delay / tau))

    return fn


def daily_cancellation_hazard(cancel_probability: float, tau: int) -> float:
    """
    Convert an eventual pre-appointment cancellation probability into a daily hazard.

    For a patient who booked with delay ``tau >= 1``, the simulator applies one
    cancellation trial at the end of each pre-appointment day. This helper
    returns the constant daily cancellation probability that yields total
    cancellation probability ``cancel_probability`` over those ``tau`` trials.
    Same-day bookings (``tau <= 0``) have no pre-appointment cancellation
    opportunity and therefore a zero hazard.
    """
    if tau <= 0:
        return 0.0
    cancel_probability = clamp_probability(cancel_probability)
    if cancel_probability >= 1.0:
        return 1.0
    return clamp_probability(1.0 - (1.0 - cancel_probability) ** (1.0 / float(tau)))


def evaluate_cancellation_probability(
    cancellation_rule: float | CancellationFn,
    tau: int,
    residual_delay: int,
) -> float:
    """
    Evaluate either a direct ``phi(tau, r)`` rule or a legacy scalar parameter.

    A callable is interpreted as the direct daily cancellation rule. A numeric
    value is treated as the older eventual cancellation probability and mapped
    to a constant daily hazard through ``daily_cancellation_hazard``.
    """
    if callable(cancellation_rule):
        return clamp_probability(cancellation_rule(tau, residual_delay))
    return daily_cancellation_hazard(float(cancellation_rule), tau)


def step_balking(
    threshold: int,
    low_delay_probability: float = 0.0,
    high_delay_probability: float = 1.0,
) -> ProbabilityFn:
    """Return a step balking rule with a single jump at the offered delay threshold."""
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
    """Return a smooth delay-sensitive balking rule based on a logistic curve."""
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
    """Return an increasing no-show curve that saturates exponentially with delay."""
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
    """Return the Green-Savin exponential-saturation no-show specification."""
    return exponential_no_show(base=gamma_0, maximum=gamma_max, scale=sensitivity)
