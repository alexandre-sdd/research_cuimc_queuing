from __future__ import annotations

import pandas as pd

from appointment_simulation import (
    ClassWindowPolicy,
    FCFSPolicy,
    LatestAvailablePolicy,
    PatientClassConfig,
    ReservedCapacityPolicy,
    SimulationConfig,
    behavior_profile_frame,
    bootstrap_metric_summary,
    constant_probability,
    green_savin_no_show,
    run_lambda_sweep,
    simulate,
    split_two_class_arrival_rates,
    step_balking,
)
from appointment_simulation.behaviors import exponential_no_show


def make_classes(
    lambda_1: float,
    lambda_2: float,
    *,
    balk_1: float = 0.0,
    balk_2: float = 0.0,
    cancel_1: float = 0.0,
    cancel_2: float = 0.0,
    no_show_1=(0.0, 0.0, 3.0),
    no_show_2=(0.0, 0.0, 3.0),
) -> list[PatientClassConfig]:
    return [
        PatientClassConfig(
            1,
            lambda_1,
            constant_probability(balk_1),
            cancel_1,
            exponential_no_show(*no_show_1),
            "class_1",
        ),
        PatientClassConfig(
            2,
            lambda_2,
            constant_probability(balk_2),
            cancel_2,
            exponential_no_show(*no_show_2),
            "class_2",
        ),
    ]


def make_config(seed: int) -> SimulationConfig:
    return SimulationConfig(burn_in_days=30, measure_days=100, rng_seed=seed)


def test_accounting_identities_hold_aggregate_and_by_class() -> None:
    result = simulate(
        make_classes(
            0.22,
            0.18,
            balk_1=0.10,
            balk_2=0.15,
            cancel_1=0.20,
            cancel_2=0.10,
            no_show_1=(0.05, 0.35, 4.0),
            no_show_2=(0.03, 0.25, 5.0),
        ),
        make_config(seed=5),
    )

    aggregate = result.summary_aggregate
    assert aggregate["arrivals"] == aggregate["balked"] + aggregate["no_offer"] + aggregate["booked"]
    assert aggregate["not_booked"] == aggregate["balked"] + aggregate["no_offer"]
    assert aggregate["booked"] == (
        aggregate["canceled"]
        + aggregate["no_shows"]
        + aggregate["served"]
        + aggregate["still_scheduled_end"]
    )

    for _, row in result.summary_by_class.iterrows():
        assert row["arrivals"] == row["balked"] + row["no_offer"] + row["booked"]
        assert row["not_booked"] == row["balked"] + row["no_offer"]
        assert row["booked"] == (
            row["canceled"] + row["no_shows"] + row["served"] + row["still_scheduled_end"]
        )

    assert result.summary_by_class["arrivals"].sum() == aggregate["arrivals"]
    assert result.summary_by_class["served"].sum() == aggregate["served"]


def test_low_friction_regime_has_near_zero_delay_and_full_service() -> None:
    result = simulate(make_classes(0.05, 0.04), make_config(seed=1))

    assert result.summary_aggregate["served_per_booked"] == 1.0
    assert result.summary_aggregate["mean_delay_booked"] < 0.10
    assert result.slot_summary_aggregate["booked_slot_utilization"] < 0.15


def test_higher_arrival_rates_increase_delay_and_booked_utilization() -> None:
    light = simulate(make_classes(0.10, 0.08), make_config(seed=1))
    heavy = simulate(make_classes(0.30, 0.25), make_config(seed=1))

    assert heavy.summary_aggregate["mean_delay_booked"] > light.summary_aggregate["mean_delay_booked"]
    assert heavy.slot_summary_aggregate["booked_slot_utilization"] > light.slot_summary_aggregate["booked_slot_utilization"]


def test_more_delay_sensitive_no_show_reduces_service_fraction_and_attended_utilization() -> None:
    mild = simulate(
        make_classes(
            0.35,
            0.30,
            no_show_1=(0.02, 0.20, 6.0),
            no_show_2=(0.02, 0.20, 6.0),
        ),
        make_config(seed=17),
    )
    steep = simulate(
        make_classes(
            0.35,
            0.30,
            no_show_1=(0.02, 0.60, 1.5),
            no_show_2=(0.02, 0.60, 1.5),
        ),
        make_config(seed=17),
    )

    assert steep.summary_aggregate["served_per_booked"] < mild.summary_aggregate["served_per_booked"]
    assert (
        steep.slot_summary_aggregate["attended_slot_utilization"]
        < mild.slot_summary_aggregate["attended_slot_utilization"]
    )


def test_cancellations_reopen_future_slots_and_same_day_bookings_never_precancel() -> None:
    result = simulate(
        make_classes(0.30, 0.20, cancel_1=0.40, cancel_2=0.40),
        SimulationConfig(burn_in_days=20, measure_days=80, rng_seed=3),
    )

    assert result.summary_aggregate["canceled"] > 0
    assert int(((result.cohort_log["tau_booked"] == 0) & (result.cohort_log["outcome"] == "canceled")).sum()) == 0
    assert int(result.cohort_log[["appointment_day", "appointment_slot"]].duplicated().sum()) > 0


def test_alternate_policy_can_be_injected_without_engine_changes() -> None:
    classes = make_classes(0.18, 0.12)
    config = SimulationConfig(burn_in_days=20, measure_days=60, rng_seed=9)
    fcfs = simulate(classes, config, policy=FCFSPolicy())
    latest = simulate(classes, config, policy=LatestAvailablePolicy())

    assert latest.summary_aggregate["mean_delay_booked"] > fcfs.summary_aggregate["mean_delay_booked"]
    assert latest.policy_name == "LatestAvailablePolicy"


def test_reserved_capacity_policy_blocks_other_classes_when_only_reserved_slots_remain() -> None:
    policy = ReservedCapacityPolicy(reserved_slots_by_class={2: 1})
    occupied = object()
    calendar = [[occupied, occupied, occupied, None]]

    assert policy.select_slot(calendar, class_id=1, current_day=0, current_slot=0) is None
    assert policy.select_slot(calendar, class_id=2, current_day=0, current_slot=0) == (0, 3)


def test_class_window_policy_limits_booked_delay_by_class() -> None:
    classes = make_classes(0.35, 0.25)
    config = SimulationConfig(horizon_days=8, slots_per_day=5, burn_in_days=10, measure_days=50, rng_seed=22)
    windowed = simulate(
        classes,
        config,
        policy=ClassWindowPolicy(max_delay_by_class={1: 1, 2: 3}),
    )

    class_1_delays = windowed.cohort_log.loc[windowed.cohort_log["class_id"] == 1, "tau_booked"]
    class_2_delays = windowed.cohort_log.loc[windowed.cohort_log["class_id"] == 2, "tau_booked"]
    assert int(class_1_delays.max()) <= 1
    assert int(class_2_delays.max()) <= 3


def test_access_metric_and_daily_journal_are_exposed() -> None:
    result = simulate(
        make_classes(
            0.12,
            0.10,
            balk_1=0.05,
            balk_2=0.05,
            no_show_1=(0.01, 0.30, 3.0),
            no_show_2=(0.01, 0.30, 3.0),
        ),
        SimulationConfig(horizon_days=10, slots_per_day=5, burn_in_days=10, measure_days=30, access_target_days=4, rng_seed=4),
    )

    assert "booked_within_access_target" in result.summary_by_class.columns
    assert "booked_within_access_target_per_arrival" in result.summary_by_class.columns
    assert "booked_within_access_target_per_arrival" in result.summary_aggregate.index
    assert len(result.daily_journal_by_class) == 30 * 2
    assert len(result.daily_journal_aggregate) == 30
    assert set(result.daily_journal_by_class["measured_day"]) == set(range(30))
    assert set(result.daily_journal_aggregate["measured_day"]) == set(range(30))


def test_behavior_profiles_match_simulator_conventions() -> None:
    classes = make_classes(
        0.10,
        0.08,
        cancel_1=0.25,
        cancel_2=0.40,
        no_show_1=(0.01, 0.20, 3.0),
        no_show_2=(0.02, 0.30, 4.0),
    )
    frame = behavior_profile_frame(classes, horizon_days=5)

    assert set(frame.columns) == {
        "class_id",
        "label",
        "tau_booked",
        "balk_probability",
        "no_show_probability",
        "effective_cancel_probability",
    }
    assert len(frame) == 10
    assert (frame.loc[frame["tau_booked"] == 0, "effective_cancel_probability"] == 0.0).all()
    assert (
        frame.loc[(frame["class_id"] == 1) & (frame["tau_booked"] >= 1), "effective_cancel_probability"] == 0.25
    ).all()
    assert (
        frame.loc[(frame["class_id"] == 2) & (frame["tau_booked"] >= 1), "effective_cancel_probability"] == 0.40
    ).all()


def test_step_balking_changes_probability_at_threshold() -> None:
    fn = step_balking(threshold=4, low_delay_probability=0.10, high_delay_probability=0.80)
    assert fn(0) == 0.10
    assert fn(3) == 0.10
    assert fn(4) == 0.80
    assert fn(10) == 0.80


def test_green_savin_wrapper_matches_exponential_shape() -> None:
    fn = green_savin_no_show(gamma_0=0.01, gamma_max=0.31, sensitivity=50.0)
    assert 0.009 <= fn(0) <= 0.011
    assert fn(5) > fn(0)
    assert fn(50) < 0.31
    assert fn(200) <= 0.31


def test_total_lambda_split_and_sweep_use_class_share_parameterization() -> None:
    lambda_1, lambda_2 = split_two_class_arrival_rates(total_lambda=0.30, class_1_share=0.6)
    assert lambda_1 == 0.18
    assert lambda_2 == 0.12

    frame = run_lambda_sweep(
        class_configs=make_classes(0.10, 0.08),
        total_lambdas=[0.20, 0.30],
        class_1_share=0.6,
        config=make_config(seed=21),
        policy=FCFSPolicy(),
        replications=2,
        base_seed=50,
    )

    assert list(frame["lambda_total"].unique()) == [0.20, 0.30]
    assert set(frame["class_1_share"]) == {0.6}
    assert set(frame.loc[frame["lambda_total"] == 0.20, "lambda_1"].round(10)) == {0.12}
    assert set(frame.loc[frame["lambda_total"] == 0.20, "lambda_2"].round(10)) == {0.08}


def test_bootstrap_metric_summary_returns_grouped_means_and_intervals() -> None:
    frame = pd.DataFrame(
        {
            "scenario": ["low", "low", "high", "high"],
            "replication": [0, 1, 0, 1],
            "metric_a": [1.0, 3.0, 5.0, 7.0],
            "metric_b": [2.0, 4.0, 6.0, 8.0],
        }
    )

    summary = bootstrap_metric_summary(
        frame,
        group_cols=["scenario"],
        metric_cols=["metric_a", "metric_b"],
        n_bootstrap=200,
        ci=90.0,
        rng_seed=12,
        show_progress=False,
    )

    assert set(summary.columns) == {"scenario", "metric", "replications", "mean", "sd", "ci_lower", "ci_upper"}
    assert len(summary) == 4

    low_metric_a = summary[(summary["scenario"] == "low") & (summary["metric"] == "metric_a")].iloc[0]
    assert low_metric_a["replications"] == 2
    assert low_metric_a["mean"] == 2.0
    assert low_metric_a["ci_lower"] <= low_metric_a["mean"] <= low_metric_a["ci_upper"]
