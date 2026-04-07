from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Sequence

import pandas as pd

from .core import PatientClassConfig, SimulationConfig, SimulationResult, simulate
from .policies import AllocationPolicy


def simulate_replications(
    class_configs: Sequence[PatientClassConfig],
    config: SimulationConfig | None = None,
    policy: AllocationPolicy | None = None,
    replications: int = 1,
    base_seed: int = 0,
) -> list[SimulationResult]:
    config = config or SimulationConfig()
    results: list[SimulationResult] = []
    for replication in range(replications):
        replication_config = replace(config, rng_seed=base_seed + replication)
        results.append(simulate(class_configs=class_configs, config=replication_config, policy=policy))
    return results


def replication_summary_frame(results: Sequence[SimulationResult]) -> pd.DataFrame:
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


def run_lambda_sweep(
    class_configs: Sequence[PatientClassConfig],
    lambda_pairs: Iterable[tuple[float, float]],
    config: SimulationConfig | None = None,
    policy: AllocationPolicy | None = None,
    replications: int = 1,
    base_seed: int = 0,
) -> pd.DataFrame:
    class_configs = tuple(class_configs)
    if len(class_configs) < 2:
        raise ValueError("run_lambda_sweep expects at least two patient classes")

    frames = []
    for scenario_index, (lambda_1, lambda_2) in enumerate(lambda_pairs):
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
        frame["lambda_1"] = lambda_1
        frame["lambda_2"] = lambda_2
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
