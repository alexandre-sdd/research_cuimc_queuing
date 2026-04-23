from __future__ import annotations

from typing import Sequence

import pandas as pd

from .behaviors import clamp_probability, evaluate_cancellation_probability
from .core import PatientClassConfig


def effective_cancellation_probability(
    class_config: PatientClassConfig,
    tau: int,
    residual_delay: int,
) -> float:
    """Return the simulator's daily cancellation probability for the given residual delay."""
    if tau <= 0 or residual_delay <= 0:
        return 0.0
    return evaluate_cancellation_probability(class_config.cancel_probability, tau, residual_delay)


def cumulative_cancellation_probability(
    class_config: PatientClassConfig,
    tau: int,
    residual_delay: int,
) -> float:
    """
    Return the probability that the patient has already canceled by residual delay ``r``.

    This is the exact cumulative cancellation probability implied by the daily
    hazards used by the simulator. For the baseline scalar rule this is the
    repeated daily probability ``phi``; for advanced experiments it can be the
    callable ``tilde_phi(tau, k)`` for ``k = tau, tau - 1, ..., 1``. It is
    therefore based on a survival product, not a simple cumulative sum.
    """
    if tau <= 0:
        return 0.0
    if residual_delay < 0:
        residual_delay = 0
    if residual_delay >= tau:
        return 0.0

    survival_probability = 1.0
    for day_residual_delay in range(tau, residual_delay, -1):
        daily_hazard = effective_cancellation_probability(class_config, tau, day_residual_delay)
        survival_probability *= 1.0 - daily_hazard
    return clamp_probability(1.0 - survival_probability)


def behavior_profile_frame(
    class_configs: Sequence[PatientClassConfig],
    horizon_days: int,
) -> pd.DataFrame:
    """Tabulate balking, no-show, and cancellation profiles over delay values."""
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")

    records: list[dict[str, float | int | str]] = []
    for class_config in class_configs:
        label = class_config.label or f"class_{class_config.class_id}"
        for tau_booked in range(horizon_days):
            residual_delays = [0] if tau_booked == 0 else list(range(0, tau_booked + 1))
            for residual_delay in residual_delays:
                records.append(
                    {
                        "class_id": class_config.class_id,
                        "label": label,
                        "tau_booked": tau_booked,
                        "residual_delay": residual_delay,
                        "balk_probability": clamp_probability(class_config.balk_probability(tau_booked)),
                        "no_show_probability": clamp_probability(class_config.no_show_probability(tau_booked)),
                        "daily_cancel_probability": effective_cancellation_probability(
                            class_config,
                            tau_booked,
                            residual_delay,
                        ),
                        "cumulative_cancel_probability": cumulative_cancellation_probability(
                            class_config,
                            tau_booked,
                            residual_delay,
                        ),
                    }
                )
    return pd.DataFrame.from_records(records)
