from __future__ import annotations

from typing import Any

import pandas as pd

from .behaviors import green_savin_no_show, linear_taper_cancellation, logistic_balking, step_balking, step_no_show
from .core import PatientClassConfig, SimulationConfig
from .sweeps import split_two_class_arrival_rates


CLASS_DETAILS: dict[int, dict[str, str]] = {
    1: {
        "label": "MRI-like diagnostic",
        "short_label": "MRI-like",
    },
    2: {
        "label": "Behavioral-health follow-up",
        "short_label": "Behavioral-health",
    },
}


BALKING_OPTIONS: dict[str, dict[str, Any]] = {
    "step_access": {
        "description": "Step balking around a practical access threshold for each class.",
        "class_specs": {
            1: {"kind": "step", "threshold": 21, "low": 0.02, "high": 0.55},
            2: {"kind": "step", "threshold": 14, "low": 0.04, "high": 0.72},
        },
    },
    "smooth_access": {
        "description": "Smoother logistic balking when patients gradually react to delay.",
        "class_specs": {
            1: {"kind": "logistic", "midpoint": 18.0, "slope": 0.30, "floor": 0.02, "ceiling": 0.52},
            2: {"kind": "logistic", "midpoint": 12.0, "slope": 0.40, "floor": 0.04, "ceiling": 0.76},
        },
    },
}


NO_SHOW_OPTIONS: dict[str, dict[str, Any]] = {
    "step_access": {
        "description": "Baseline step no-show around a practical access threshold for each class.",
        "class_specs": {
            1: {"threshold": 21, "low": 0.01, "high": 0.31},
            2: {"threshold": 14, "low": 0.15, "high": 0.51},
        },
    },
    "step_more_delay_sensitive": {
        "description": "A stronger step no-show response after the access threshold.",
        "class_specs": {
            1: {"threshold": 18, "low": 0.02, "high": 0.38},
            2: {"threshold": 12, "low": 0.18, "high": 0.62},
        },
    },
}


ADVANCED_NO_SHOW_OPTIONS: dict[str, dict[str, Any]] = {
    "source_aligned": {
        "description": "Advanced Green-Savin style curves close to the literature examples used in the earlier note.",
        "class_specs": {
            1: {"gamma_0": 0.01, "gamma_max": 0.31, "sensitivity": 50.0},
            2: {"gamma_0": 0.15, "gamma_max": 0.51, "sensitivity": 9.0},
        },
    },
    "more_delay_sensitive": {
        "description": "Advanced stronger delay-sensitive no-show curves to stress-test the feedback loop.",
        "class_specs": {
            1: {"gamma_0": 0.02, "gamma_max": 0.38, "sensitivity": 28.0},
            2: {"gamma_0": 0.18, "gamma_max": 0.62, "sensitivity": 6.0},
        },
    },
}


CANCELLATION_OPTIONS: dict[str, dict[str, Any]] = {
    "moderate": {
        "description": "Moderate constant daily cancellation probability for each scheduled patient.",
        "class_specs": {
            1: {"phi": 0.01},
            2: {"phi": 0.02},
        },
    },
    "reschedule_heavy": {
        "description": "Higher constant daily cancellation pressure.",
        "class_specs": {
            1: {"phi": 0.02},
            2: {"phi": 0.03},
        },
    },
}


ADVANCED_CANCELLATION_OPTIONS: dict[str, dict[str, Any]] = {
    "linear_taper_moderate": {
        "description": "Advanced tilde-phi rule that rises with booked delay and tapers as the visit approaches.",
        "class_specs": {
            1: {"base": 0.01, "slope": 0.008, "ceiling": 0.12},
            2: {"base": 0.02, "slope": 0.012, "ceiling": 0.18},
        },
    },
    "linear_taper_heavy": {
        "description": "Advanced tilde-phi rule with higher pressure for patients booked far in advance.",
        "class_specs": {
            1: {"base": 0.02, "slope": 0.010, "ceiling": 0.16},
            2: {"base": 0.03, "slope": 0.015, "ceiling": 0.24},
        },
    },
}


def _build_balking_function(option_name: str, class_id: int):
    spec = BALKING_OPTIONS[option_name]["class_specs"][class_id]
    if spec["kind"] == "step":
        return step_balking(
            threshold=int(spec["threshold"]),
            low_delay_probability=float(spec["low"]),
            high_delay_probability=float(spec["high"]),
        )
    return logistic_balking(
        midpoint=float(spec["midpoint"]),
        slope=float(spec["slope"]),
        floor=float(spec["floor"]),
        ceiling=float(spec["ceiling"]),
    )


def _build_no_show_function(option_name: str, class_id: int):
    if option_name in NO_SHOW_OPTIONS:
        spec = NO_SHOW_OPTIONS[option_name]["class_specs"][class_id]
        return step_no_show(
            threshold=int(spec["threshold"]),
            low_delay_probability=float(spec["low"]),
            high_delay_probability=float(spec["high"]),
        )
    spec = ADVANCED_NO_SHOW_OPTIONS[option_name]["class_specs"][class_id]
    return green_savin_no_show(
        gamma_0=float(spec["gamma_0"]),
        gamma_max=float(spec["gamma_max"]),
        sensitivity=float(spec["sensitivity"]),
    )


def _build_cancellation_function(option_name: str, class_id: int):
    spec = CANCELLATION_OPTIONS[option_name]["class_specs"][class_id]
    return float(spec["phi"])


def _build_advanced_cancellation_function(option_name: str, class_id: int):
    spec = ADVANCED_CANCELLATION_OPTIONS[option_name]["class_specs"][class_id]
    return linear_taper_cancellation(
        base=float(spec["base"]),
        slope=float(spec["slope"]),
        ceiling=float(spec["ceiling"]),
    )


def behavior_option_frame() -> pd.DataFrame:
    """List the notebook-friendly behavior choices by family, option, and class."""
    records: list[dict[str, object]] = []

    for option_name, option in BALKING_OPTIONS.items():
        for class_id, spec in option["class_specs"].items():
            detail = (
                f"step threshold={spec['threshold']}, low={spec['low']:.2f}, high={spec['high']:.2f}"
                if spec["kind"] == "step"
                else (
                    f"logistic midpoint={spec['midpoint']:.0f}, slope={spec['slope']:.2f}, "
                    f"floor={spec['floor']:.2f}, ceiling={spec['ceiling']:.2f}"
                )
            )
            records.append(
                {
                    "family": "balking",
                    "option": option_name,
                    "class_id": class_id,
                    "label": CLASS_DETAILS[class_id]["label"],
                    "description": option["description"],
                    "details": detail,
                }
            )

    for option_name, option in NO_SHOW_OPTIONS.items():
        for class_id, spec in option["class_specs"].items():
            records.append(
                {
                    "family": "no_show",
                    "option": option_name,
                    "class_id": class_id,
                    "label": CLASS_DETAILS[class_id]["label"],
                    "description": option["description"],
                    "details": (
                        f"step threshold={spec['threshold']}, low={spec['low']:.2f}, "
                        f"high={spec['high']:.2f}"
                    ),
                }
            )

    for option_name, option in ADVANCED_NO_SHOW_OPTIONS.items():
        for class_id, spec in option["class_specs"].items():
            records.append(
                {
                    "family": "advanced_no_show",
                    "option": option_name,
                    "class_id": class_id,
                    "label": CLASS_DETAILS[class_id]["label"],
                    "description": option["description"],
                    "details": (
                        f"gamma_0={spec['gamma_0']:.2f}, gamma_max={spec['gamma_max']:.2f}, "
                        f"sensitivity={spec['sensitivity']:.0f}"
                    ),
                }
            )

    for option_name, option in CANCELLATION_OPTIONS.items():
        for class_id, spec in option["class_specs"].items():
            records.append(
                {
                    "family": "cancellation",
                    "option": option_name,
                    "class_id": class_id,
                    "label": CLASS_DETAILS[class_id]["label"],
                    "description": option["description"],
                    "details": f"phi={spec['phi']:.2f}",
                }
            )

    return pd.DataFrame.from_records(records)


def make_two_class_classes(
    *,
    total_lambda: float = 6.0,
    class_1_share: float = 7 / 12,
    balking_option: str = "step_access",
    no_show_option: str = "step_access",
    cancellation_option: str = "moderate",
) -> tuple[PatientClassConfig, PatientClassConfig]:
    """Build the two-class daily-arrival configuration used in the notebooks."""
    if balking_option not in BALKING_OPTIONS:
        raise ValueError(f"unknown balking option: {balking_option}")
    if no_show_option not in NO_SHOW_OPTIONS and no_show_option not in ADVANCED_NO_SHOW_OPTIONS:
        raise ValueError(f"unknown no-show option: {no_show_option}")
    if cancellation_option not in CANCELLATION_OPTIONS:
        raise ValueError(f"unknown cancellation option: {cancellation_option}")

    lambda_1, lambda_2 = split_two_class_arrival_rates(total_lambda, class_1_share)
    arrival_rates = {1: lambda_1, 2: lambda_2}

    class_configs: list[PatientClassConfig] = []
    for class_id in (1, 2):
        class_configs.append(
            PatientClassConfig(
                class_id=class_id,
                label=CLASS_DETAILS[class_id]["label"],
                arrival_rate=arrival_rates[class_id],
                balk_probability=_build_balking_function(balking_option, class_id),
                cancel_probability=_build_cancellation_function(cancellation_option, class_id),
                no_show_probability=_build_no_show_function(no_show_option, class_id),
            )
        )

    return tuple(class_configs)


def model_setup_frame(
    *,
    total_lambda: float,
    class_1_share: float,
    class_configs: tuple[PatientClassConfig, PatientClassConfig],
    balking_option: str,
    no_show_option: str,
    cancellation_option: str,
) -> pd.DataFrame:
    """Summarize the selected model inputs in the notation used by the note."""
    records: list[dict[str, object]] = []
    for class_config in class_configs:
        class_id = class_config.class_id
        cancel_spec = CANCELLATION_OPTIONS[cancellation_option]["class_specs"][class_id]
        records.append(
            {
                "class_id": class_id,
                "label": class_config.label,
                "lambda_total": total_lambda,
                "p": class_1_share,
                "lambda_i": class_config.arrival_rate,
                "b_i option": balking_option,
                "phi_i option": cancellation_option,
                "xi_i option": no_show_option,
                "phi_i": cancel_spec["phi"],
            }
        )
    return pd.DataFrame.from_records(records)


def make_note_config(
    *,
    horizon_days: int = 15,
    slots_per_day: int = 25,
    burn_in_days: int = 250,
    measure_days: int = 365,
    access_target_days: int = 30,
    rng_seed: int = 7,
) -> SimulationConfig:
    """Create the simple FCFS simulation configuration used by the notebooks."""
    return SimulationConfig(
        horizon_days=horizon_days,
        slots_per_day=slots_per_day,
        burn_in_days=burn_in_days,
        measure_days=measure_days,
        access_target_days=access_target_days,
        rng_seed=rng_seed,
    )
