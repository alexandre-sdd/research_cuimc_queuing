from __future__ import annotations

import numpy as np
import pandas as pd

from appointment_simulation import (
    ADVANCED_NO_SHOW_OPTIONS,
    BALKING_OPTIONS,
    CANCELLATION_OPTIONS,
    ClassWindowPolicy,
    FCFSPolicy,
    LatestAvailablePolicy,
    NO_SHOW_OPTIONS,
    PatientClassConfig,
    ReservedCapacityPolicy,
    SimulationConfig,
    behavior_option_frame,
    behavior_profile_frame,
    bootstrap_metric_summary,
    constant_probability,
    daily_cancellation_hazard,
    evaluate_cancellation_probability,
    green_savin_no_show,
    linear_taper_cancellation,
    make_note_config,
    make_two_class_classes,
    model_setup_frame,
    run_lambda_sweep,
    simulate,
    split_two_class_arrival_rates,
    step_balking,
    step_no_show,
)
from appointment_simulation.behaviors import exponential_no_show


def make_classes(
    lambda_1: float,
    lambda_2: float,
    *,
    balk_1: float = 0.0,
    balk_2: float = 0.0,
    cancel_1: float | tuple[float, float, float] = 0.0,
    cancel_2: float | tuple[float, float, float] = 0.0,
    no_show_1=(0.0, 0.0, 3.0),
    no_show_2=(0.0, 0.0, 3.0),
) -> list[PatientClassConfig]:
    cancel_rule_1 = (
        linear_taper_cancellation(*cancel_1) if isinstance(cancel_1, tuple) else cancel_1
    )
    cancel_rule_2 = (
        linear_taper_cancellation(*cancel_2) if isinstance(cancel_2, tuple) else cancel_2
    )
    return [
        PatientClassConfig(
            1,
            lambda_1,
            constant_probability(balk_1),
            cancel_rule_1,
            exponential_no_show(*no_show_1),
            "class_1",
        ),
        PatientClassConfig(
            2,
            lambda_2,
            constant_probability(balk_2),
            cancel_rule_2,
            exponential_no_show(*no_show_2),
            "class_2",
        ),
    ]


def make_config(seed: int) -> SimulationConfig:
    return SimulationConfig(burn_in_days=30, measure_days=100, rng_seed=seed)


def test_accounting_identities_hold_aggregate_and_by_class() -> None:
    result = simulate(
        make_classes(
            5.5,
            4.5,
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


def test_low_friction_regime_books_next_day_and_has_full_service() -> None:
    result = simulate(make_classes(1.25, 1.00), make_config(seed=1))

    assert result.summary_aggregate["served_per_booked"] == 1.0
    assert result.summary_aggregate["mean_delay_booked"] == 1.0
    assert result.slot_summary_aggregate["booked_slot_utilization"] < 0.15


def test_higher_arrival_rates_increase_delay_and_booked_utilization() -> None:
    light = simulate(make_classes(2.50, 2.00), make_config(seed=1))
    heavy = simulate(make_classes(15.00, 12.00), make_config(seed=1))

    assert heavy.summary_aggregate["mean_delay_booked"] > light.summary_aggregate["mean_delay_booked"]
    assert heavy.slot_summary_aggregate["booked_slot_utilization"] > light.slot_summary_aggregate["booked_slot_utilization"]


def test_more_delay_sensitive_no_show_reduces_service_fraction_and_attended_utilization() -> None:
    mild = simulate(
        make_classes(
            8.75,
            7.50,
            no_show_1=(0.02, 0.20, 6.0),
            no_show_2=(0.02, 0.20, 6.0),
        ),
        make_config(seed=17),
    )
    steep = simulate(
        make_classes(
            8.75,
            7.50,
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


def test_cancellations_reopen_future_slots_and_future_only_bookings_have_positive_delay() -> None:
    result = simulate(
        make_classes(20.00, 15.00, cancel_1=0.40, cancel_2=0.40),
        SimulationConfig(burn_in_days=20, measure_days=80, rng_seed=3),
    )

    assert result.summary_aggregate["canceled"] > 0
    assert int((result.cohort_log["tau_booked"] == 0).sum()) == 0
    assert int(result.cohort_log[["appointment_day", "appointment_slot"]].duplicated().sum()) > 0


def test_daily_arrivals_are_drawn_once_per_class_per_day() -> None:
    config = SimulationConfig(
        horizon_days=1,
        slots_per_day=5,
        burn_in_days=0,
        measure_days=5,
        cooldown_days=0,
        rng_seed=123,
    )
    result = simulate(make_classes(2.0, 3.0), config)

    expected_counts: list[dict[int, int]] = []
    rng = np.random.default_rng(config.rng_seed)
    for _ in range(config.total_days):
        class_1_count = int(rng.poisson(2.0))
        class_2_count = int(rng.poisson(3.0))
        arrival_order = [1] * class_1_count + [2] * class_2_count
        if arrival_order:
            rng.permutation(arrival_order)
        expected_counts.append({1: class_1_count, 2: class_2_count})

    observed = (
        result.arrival_log.groupby(["measured_day", "class_id"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=range(config.measure_days), columns=[1, 2], fill_value=0)
    )
    for measured_day, expected in enumerate(expected_counts):
        assert int(observed.loc[measured_day, 1]) == expected[1]
        assert int(observed.loc[measured_day, 2]) == expected[2]


def test_scalar_cancellation_probability_is_direct_daily_probability() -> None:
    direct = evaluate_cancellation_probability(0.36, tau=3, residual_delay=2)

    assert direct == 0.36
    assert direct != daily_cancellation_hazard(0.36, tau=3)


def test_cancellations_skip_same_day_appointments_before_service_resolution() -> None:
    result = simulate(
        make_classes(10.0, 0.0, cancel_1=1.0, cancel_2=1.0),
        SimulationConfig(
            horizon_days=2,
            slots_per_day=1,
            burn_in_days=0,
            measure_days=3,
            cooldown_days=0,
            rng_seed=0,
        ),
    )

    day_1 = result.daily_journal_aggregate.loc[result.daily_journal_aggregate["measured_day"] == 1].iloc[0]
    assert day_1["canceled"] == 0
    assert day_1["served"] == 1
    assert day_1["no_shows"] == 0
    assert day_1["empty_slots"] == 0

    day_1_progression = result.daily_progression.query("measured_day == 1").set_index("step")
    assert day_1_progression.loc["cancellations", "canceled"] == 0
    assert day_1_progression.loc["cancellations", "scheduled_for_today"] == 1
    assert day_1_progression.loc["no_shows", "served"] == 1
    assert day_1_progression.loc["no_shows", "empty_slots"] == 0


def test_fcfs_offers_earliest_future_days_only() -> None:
    result = simulate(
        make_classes(100.0, 0.0),
        SimulationConfig(
            horizon_days=4,
            slots_per_day=1,
            burn_in_days=0,
            measure_days=1,
            cooldown_days=0,
            rng_seed=0,
        ),
    )

    bookings = result.cohort_log.sort_values("patient_id")
    assert bookings["tau_booked"].tolist() == [1, 2, 3]
    assert bookings["appointment_day"].tolist() == [1, 2, 3]
    assert result.summary_aggregate["no_offer"] > 0


def test_state_log_records_all_configured_classes() -> None:
    classes = [
        *make_classes(0.0, 0.0),
        PatientClassConfig(
            3,
            0.0,
            constant_probability(0.0),
            0.0,
            exponential_no_show(0.0, 0.0, 3.0),
            "class_3",
        ),
    ]
    config = SimulationConfig(
        horizon_days=3,
        slots_per_day=2,
        burn_in_days=0,
        measure_days=2,
        cooldown_days=0,
        rng_seed=8,
    )
    result = simulate(classes, config)

    assert set(result.state_log["class_id"]) == {1, 2, 3}
    assert set(result.state_log["residual_delay"]) == {0, 1, 2}
    assert len(result.state_log) == config.measure_days * len(classes) * config.horizon_days


def test_alternate_policy_can_be_injected_without_engine_changes() -> None:
    classes = make_classes(4.50, 3.00)
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
    classes = make_classes(6.0, 4.0)
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
            3.00,
            2.50,
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


def test_daily_progression_exposes_the_model_step_order() -> None:
    config = SimulationConfig(
        horizon_days=4,
        slots_per_day=2,
        burn_in_days=0,
        measure_days=3,
        cooldown_days=0,
        rng_seed=15,
    )
    result = simulate(make_classes(3.0, 2.0, balk_1=0.25, balk_2=0.25), config)

    expected_steps = [
        "cancellations",
        "arrivals",
        "offers_and_balking",
        "no_shows",
        "metrics",
        "advance",
    ]
    assert len(result.daily_progression) == config.measure_days * len(expected_steps)
    for measured_day in range(config.measure_days):
        day_steps = result.daily_progression.query("measured_day == @measured_day").sort_values("step_order")
        assert day_steps["step"].tolist() == expected_steps

    first_day = result.daily_progression.query("measured_day == 0").set_index("step")
    assert first_day.loc["arrivals", "arrivals"] == first_day.loc["offers_and_balking", "arrivals"]
    assert first_day.loc["offers_and_balking", "offered"] == (
        first_day.loc["offers_and_balking", "booked"] + first_day.loc["offers_and_balking", "balked"]
    )
    assert first_day.loc["offers_and_balking", "open_future_slots"] <= first_day.loc["arrivals", "open_future_slots"]
    assert first_day.loc["advance", "scheduled_for_today"] <= first_day.loc["no_shows", "future_backlog"]
    assert first_day.loc["advance", "scheduled_total"] == first_day.loc["no_shows", "future_backlog"]


def test_behavior_profiles_match_simulator_conventions() -> None:
    classes = make_classes(
        2.50,
        2.00,
        cancel_1=(0.01, 0.01, 0.20),
        cancel_2=(0.02, 0.02, 0.30),
        no_show_1=(0.01, 0.20, 3.0),
        no_show_2=(0.02, 0.30, 4.0),
    )
    frame = behavior_profile_frame(classes, horizon_days=5)

    assert set(frame.columns) == {
        "class_id",
        "label",
        "tau_booked",
        "residual_delay",
        "balk_probability",
        "no_show_probability",
        "daily_cancel_probability",
        "cumulative_cancel_probability",
    }
    assert len(frame) == 30
    assert (frame.loc[frame["tau_booked"] == 0, "residual_delay"] == 0).all()
    assert (frame.loc[frame["tau_booked"] == 0, "daily_cancel_probability"] == 0.0).all()

    tau_4 = frame.loc[(frame["class_id"] == 1) & (frame["tau_booked"] == 4)].sort_values("residual_delay")
    assert set(tau_4["residual_delay"]) == {0, 1, 2, 3, 4}
    assert tau_4.iloc[0]["daily_cancel_probability"] == 0.0
    assert tau_4.iloc[-1]["daily_cancel_probability"] > tau_4.iloc[1]["daily_cancel_probability"]
    assert list(tau_4["daily_cancel_probability"]) == sorted(tau_4["daily_cancel_probability"])
    assert tau_4.loc[tau_4["residual_delay"] == 4, "cumulative_cancel_probability"].iloc[0] == 0.0
    assert tau_4.loc[tau_4["residual_delay"] == 0, "cumulative_cancel_probability"].iloc[0] > 0.0

    cumulative_in_time_order = (
        tau_4.sort_values("residual_delay", ascending=False)["cumulative_cancel_probability"].tolist()
    )
    assert cumulative_in_time_order == sorted(cumulative_in_time_order)

    booking_day_cancel_tau_4 = frame.loc[
        (frame["class_id"] == 1) & (frame["tau_booked"] == 4) & (frame["residual_delay"] == 4),
        "daily_cancel_probability",
    ].iloc[0]
    assert 0.0 < booking_day_cancel_tau_4 < 0.20

    repeated_profile = frame.loc[
        (frame["class_id"] == 2) & (frame["tau_booked"] == 3),
        ["balk_probability", "no_show_probability"],
    ].drop_duplicates()
    assert len(repeated_profile) == 1

    scalar_frame = behavior_profile_frame(make_classes(1.0, 0.0, cancel_1=0.25)[:1], horizon_days=3)
    assert (
        scalar_frame.loc[
            (scalar_frame["class_id"] == 1)
            & (scalar_frame["tau_booked"] == 2)
            & (scalar_frame["residual_delay"] == 0),
            "daily_cancel_probability",
        ].iloc[0]
        == 0.0
    )
    assert (
        scalar_frame.loc[
            (scalar_frame["class_id"] == 1)
            & (scalar_frame["tau_booked"] == 2)
            & (scalar_frame["residual_delay"] == 1),
            "daily_cancel_probability",
        ].iloc[0]
        == 0.25
    )


def test_daily_cancellation_hazard_matches_eventual_phi_over_tau_days() -> None:
    hazard = daily_cancellation_hazard(0.36, tau=3)
    eventual = 1.0 - (1.0 - hazard) ** 3

    assert hazard > 0.0
    assert abs(eventual - 0.36) < 1e-10
    assert daily_cancellation_hazard(0.36, tau=0) == 0.0


def test_linear_taper_cancellation_rises_with_tau_and_falls_with_residual_delay() -> None:
    fn = linear_taper_cancellation(base=0.01, slope=0.02, ceiling=0.20)

    assert fn(0, 0) == 0.0
    assert fn(4, 0) == 0.0
    assert fn(6, 6) > fn(3, 3)
    assert fn(6, 6) > fn(6, 2)
    assert fn(6, 8) == fn(6, 6)


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


def test_step_no_show_changes_probability_at_threshold() -> None:
    fn = step_no_show(threshold=7, low_delay_probability=0.05, high_delay_probability=0.35)
    assert fn(0) == 0.05
    assert fn(6) == 0.05
    assert fn(7) == 0.35
    assert fn(14) == 0.35


def test_total_lambda_split_and_sweep_use_class_share_parameterization() -> None:
    lambda_1, lambda_2 = split_two_class_arrival_rates(total_lambda=30.0, class_1_share=0.6)
    assert lambda_1 == 18.0
    assert lambda_2 == 12.0

    frame = run_lambda_sweep(
        class_configs=make_classes(2.50, 2.00),
        total_lambdas=[20.0, 30.0],
        class_1_share=0.6,
        config=make_config(seed=21),
        policy=FCFSPolicy(),
        replications=2,
        base_seed=50,
    )

    assert list(frame["lambda_total"].unique()) == [20.0, 30.0]
    assert set(frame["class_1_share"]) == {0.6}
    assert set(frame.loc[frame["lambda_total"] == 20.0, "lambda_1"].round(10)) == {12.0}
    assert set(frame.loc[frame["lambda_total"] == 20.0, "lambda_2"].round(10)) == {8.0}


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


def test_note_aligned_presets_build_two_realistic_classes() -> None:
    classes = make_two_class_classes(
        class_1_share=0.6,
        balking_option="step_access",
        no_show_option="step_access",
        cancellation_option="moderate",
    )

    assert len(classes) == 2
    assert round(classes[0].arrival_rate, 3) == 14.400
    assert round(classes[1].arrival_rate, 3) == 9.600
    assert classes[0].label == "MRI-like diagnostic"
    assert classes[1].label == "Behavioral-health follow-up"
    assert 0.0 <= classes[0].balk_probability(0) <= 1.0
    assert classes[0].no_show_probability(20) == NO_SHOW_OPTIONS["step_access"]["class_specs"][1]["low"]
    assert classes[0].no_show_probability(21) == NO_SHOW_OPTIONS["step_access"]["class_specs"][1]["high"]
    assert classes[1].no_show_probability(13) == NO_SHOW_OPTIONS["step_access"]["class_specs"][2]["low"]
    assert classes[1].no_show_probability(14) == NO_SHOW_OPTIONS["step_access"]["class_specs"][2]["high"]
    assert classes[0].cancel_probability == CANCELLATION_OPTIONS["moderate"]["class_specs"][1]["phi"]
    assert classes[1].cancel_probability == CANCELLATION_OPTIONS["moderate"]["class_specs"][2]["phi"]
    assert classes[1].cancel_probability > classes[0].cancel_probability


def test_behavior_option_frame_and_model_setup_frame_expose_notebook_inputs() -> None:
    option_frame = behavior_option_frame()
    assert set(option_frame["family"]) == {"balking", "no_show", "advanced_no_show", "cancellation"}
    assert set(option_frame["option"]) >= (
        set(BALKING_OPTIONS) | set(NO_SHOW_OPTIONS) | set(ADVANCED_NO_SHOW_OPTIONS) | set(CANCELLATION_OPTIONS)
    )

    classes = make_two_class_classes()
    setup = model_setup_frame(
        total_lambda=24.0,
        class_1_share=7 / 12,
        class_configs=classes,
        balking_option="step_access",
        no_show_option="step_access",
        cancellation_option="moderate",
    )
    config = make_note_config()

    assert list(setup["class_id"]) == [1, 2]
    assert "lambda_i" in setup.columns
    assert "phi_i" in setup.columns
    assert config.horizon_days == 15
    assert config.slots_per_day == 25
