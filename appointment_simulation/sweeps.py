from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from .core import PatientClassConfig, SimulationConfig, SimulationResult, simulate
from .policies import AllocationPolicy


def split_two_class_arrival_rates(total_lambda: float, class_1_share: float) -> tuple[float, float]:
    """Split a total daily two-class arrival rate into class-specific rates using share ``p``."""
    if total_lambda < 0:
        raise ValueError("total_lambda must be non-negative")
    if not 0.0 <= class_1_share <= 1.0:
        raise ValueError("class_1_share must lie in [0, 1]")
    return class_1_share * total_lambda, (1.0 - class_1_share) * total_lambda


def simulate_replications(
    class_configs: Sequence[PatientClassConfig],
    config: SimulationConfig | None = None,
    policy: AllocationPolicy | None = None,
    replications: int = 1,
    base_seed: int = 0,
) -> list[SimulationResult]:
    """Run repeated simulation replications with deterministic seed offsets."""
    config = config or SimulationConfig()
    results: list[SimulationResult] = []
    for replication in range(replications):
        replication_config = replace(config, rng_seed=base_seed + replication)
        results.append(simulate(class_configs=class_configs, config=replication_config, policy=policy))
    return results


def replication_summary_frame(results: Sequence[SimulationResult]) -> pd.DataFrame:
    """Collect replication-level aggregate KPIs into a single data frame."""
    records = []
    for replication, result in enumerate(results):
        aggregate = result.summary_aggregate.copy()
        slot_aggregate = result.slot_summary_aggregate.copy()
        records.append(
            {
                "replication": replication,
                "policy": result.policy_name,
                "arrivals": aggregate.get("arrivals", 0),
                "booked": aggregate.get("booked", 0),
                "balked": aggregate.get("balked", 0),
                "canceled": aggregate.get("canceled", 0),
                "no_shows": aggregate.get("no_shows", 0),
                "served": aggregate.get("served", 0),
                "mean_delay_booked": aggregate.get("mean_delay_booked", 0.0),
                "booked_within_access_target_per_arrival": aggregate.get("booked_within_access_target_per_arrival", 0.0),
                "booked_within_access_target_per_booked": aggregate.get("booked_within_access_target_per_booked", 0.0),
                "served_per_booked": aggregate.get("served_per_booked", 0.0),
                "booked_slot_utilization": slot_aggregate.get("booked_slot_utilization", 0.0),
                "attended_slot_utilization": slot_aggregate.get("attended_slot_utilization", 0.0),
            }
        )
    return pd.DataFrame.from_records(records)


def bootstrap_metric_summary(
    frame: pd.DataFrame,
    *,
    group_cols: Sequence[str],
    metric_cols: Sequence[str],
    n_bootstrap: int = 2_000,
    ci: float = 95.0,
    rng_seed: int = 0,
    show_progress: bool = False,
    progress_desc: str = "Bootstrap summaries",
) -> pd.DataFrame:
    """
    Estimate grouped metric means and percentile bootstrap confidence intervals.

    The input is expected to contain one row per replication. The output is a
    long-form frame with one row per ``group_cols`` / metric combination.
    """
    if frame.empty:
        return pd.DataFrame(columns=[*group_cols, "metric", "replications", "mean", "sd", "ci_lower", "ci_upper"])
    if n_bootstrap <= 0:
        raise ValueError("n_bootstrap must be positive")
    if not 0.0 < ci < 100.0:
        raise ValueError("ci must lie strictly between 0 and 100")

    grouped = list(frame.groupby(list(group_cols), dropna=False, sort=True))
    tasks: list[tuple[tuple[object, ...], pd.DataFrame, str]] = []
    for group_key, group_frame in grouped:
        normalized_key = group_key if isinstance(group_key, tuple) else (group_key,)
        for metric in metric_cols:
            tasks.append((normalized_key, group_frame, metric))

    iterator = tasks
    if show_progress:
        from tqdm.auto import tqdm

        iterator = tqdm(tasks, desc=progress_desc)

    alpha = (1.0 - ci / 100.0) / 2.0
    rng = np.random.default_rng(rng_seed)
    records: list[dict[str, object]] = []
    for group_key, group_frame, metric in iterator:
        values = pd.to_numeric(group_frame[metric], errors="coerce").dropna().to_numpy(dtype=float)
        replications = int(group_frame["replication"].nunique()) if "replication" in group_frame.columns else int(len(values))
        record = {
            **dict(zip(group_cols, group_key)),
            "metric": metric,
            "replications": replications,
            "mean": float(values.mean()) if len(values) else float("nan"),
            "sd": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
            "ci_lower": float("nan"),
            "ci_upper": float("nan"),
        }
        if len(values):
            bootstrap_samples = values[rng.integers(0, len(values), size=(n_bootstrap, len(values)))]
            bootstrap_means = bootstrap_samples.mean(axis=1)
            record["ci_lower"] = float(np.quantile(bootstrap_means, alpha))
            record["ci_upper"] = float(np.quantile(bootstrap_means, 1.0 - alpha))
        records.append(record)

    return pd.DataFrame.from_records(records)


def run_lambda_sweep(
    class_configs: Sequence[PatientClassConfig],
    total_lambdas: Iterable[float],
    class_1_share: float,
    config: SimulationConfig | None = None,
    policy: AllocationPolicy | None = None,
    replications: int = 1,
    base_seed: int = 0,
) -> pd.DataFrame:
    """Evaluate the simulator over a sweep of total daily arrival rates with fixed class mix ``p``."""
    class_configs = tuple(class_configs)
    if len(class_configs) < 2:
        raise ValueError("run_lambda_sweep expects at least two patient classes")

    frames = []
    for scenario_index, total_lambda in enumerate(total_lambdas):
        lambda_1, lambda_2 = split_two_class_arrival_rates(total_lambda, class_1_share)
        scenario_classes = (
            replace(class_configs[0], arrival_rate=lambda_1),
            replace(class_configs[1], arrival_rate=lambda_2),
            *class_configs[2:],
        )
        results = simulate_replications(
            class_configs=scenario_classes,
            config=config,
            policy=policy,
            replications=replications,
            base_seed=base_seed + scenario_index * replications,
        )
        frame = replication_summary_frame(results)
        frame["lambda_total"] = total_lambda
        frame["class_1_share"] = class_1_share
        frame["lambda_1"] = lambda_1
        frame["lambda_2"] = lambda_2
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
