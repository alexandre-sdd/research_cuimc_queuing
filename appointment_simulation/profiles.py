from __future__ import annotations

from typing import Sequence

import pandas as pd

from .behaviors import clamp_probability
from .core import PatientClassConfig


def effective_cancellation_probability(class_config: PatientClassConfig, tau: int) -> float:
    """Return the pre-appointment cancellation probability used by the simulator."""
    if tau <= 0:
        return 0.0
    return clamp_probability(class_config.cancel_probability)


def behavior_profile_frame(
    class_configs: Sequence[PatientClassConfig],
    horizon_days: int,
) -> pd.DataFrame:
    """Tabulate balking, no-show, and cancellation profiles over offered delay values."""
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")

    records: list[dict[str, float | int | str]] = []
    for class_config in class_configs:
        label = class_config.label or f"class_{class_config.class_id}"
        for tau_booked in range(horizon_days):
            records.append(
                {
                    "class_id": class_config.class_id,
                    "label": label,
                    "tau_booked": tau_booked,
                    "balk_probability": clamp_probability(class_config.balk_probability(tau_booked)),
                    "no_show_probability": clamp_probability(class_config.no_show_probability(tau_booked)),
                    "effective_cancel_probability": effective_cancellation_probability(class_config, tau_booked),
                }
            )
    return pd.DataFrame.from_records(records)
