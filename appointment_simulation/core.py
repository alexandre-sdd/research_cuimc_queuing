from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd

from .behaviors import CancellationFn, ProbabilityFn, clamp_probability, evaluate_cancellation_probability
from .policies import AllocationPolicy, FCFSPolicy


MEASURED_ARRIVAL_COLUMNS = [
    "arrival_day",
    "arrival_slot",
    "measured_day",
    "class_id",
    "patient_id",
    "offered_day",
    "offered_slot",
    "tau_offered",
    "booked",
    "balked",
    "no_offer",
    "not_booked",
]

SLOT_LOG_COLUMNS = [
    "day",
    "slot",
    "measured_day",
    "occupied",
    "class_id",
    "tau_booked",
    "outcome",
]

COHORT_COLUMNS = [
    "patient_id",
    "class_id",
    "booking_day",
    "booking_slot",
    "measured_day",
    "appointment_day",
    "appointment_slot",
    "tau_booked",
    "outcome",
    "resolution_day",
    "resolution_slot",
]

STATE_COLUMNS = [
    "day",
    "measured_day",
    "class_id",
    "residual_delay",
    "count",
]

DAILY_JOURNAL_BY_CLASS_COLUMNS = [
    "day",
    "measured_day",
    "class_id",
    "label",
    "scheduled_start_of_day",
    "scheduled_for_today_start",
    "arrivals",
    "booked",
    "balked",
    "no_offer",
    "not_booked",
    "booked_within_access_target",
    "canceled",
    "no_shows",
    "served",
    "booked_slots",
    "served_slots",
    "no_show_slots",
    "mean_tau_booked_new_bookings",
    "booked_per_arrival",
    "booked_within_access_target_per_arrival",
    "booked_within_access_target_per_booked",
    "served_per_booked",
    "booked_slot_utilization",
    "attended_slot_utilization",
]

DAILY_JOURNAL_AGGREGATE_COLUMNS = [
    "day",
    "measured_day",
    "label",
    "scheduled_start_of_day",
    "scheduled_for_today_start",
    "arrivals",
    "booked",
    "balked",
    "no_offer",
    "not_booked",
    "booked_within_access_target",
    "canceled",
    "no_shows",
    "served",
    "booked_slots",
    "served_slots",
    "no_show_slots",
    "empty_slots",
    "mean_tau_booked_new_bookings",
    "booked_per_arrival",
    "booked_within_access_target_per_arrival",
    "booked_within_access_target_per_booked",
    "served_per_booked",
    "booked_slot_utilization",
    "attended_slot_utilization",
]


@dataclass(frozen=True)
class PatientClassConfig:
    """
    Behavioral and demand parameters for one patient class.

    The three behavior fields mirror the note:
    ``b_i(\\tau)``, ``\\phi_i(\\tau, r)``, and ``\\xi_i(\\tau)``.

    ``arrival_rate`` is the expected number of class-i arrivals per day.
    ``cancel_probability`` can be either a daily scalar probability or a
    callable daily rule ``phi_i(tau, r)``.
    """
    class_id: int
    arrival_rate: float
    balk_probability: ProbabilityFn
    cancel_probability: float | CancellationFn
    no_show_probability: ProbabilityFn
    label: str | None = None

    def __post_init__(self) -> None:
        if self.arrival_rate < 0:
            raise ValueError("arrival_rate must be non-negative")
        if isinstance(self.cancel_probability, (int, float)) and not 0.0 <= float(self.cancel_probability) <= 1.0:
            raise ValueError("cancel_probability must lie in [0, 1]")


@dataclass(frozen=True)
class SimulationConfig:
    horizon_days: int = 15
    slots_per_day: int = 25
    burn_in_days: int = 250
    measure_days: int = 1000
    cooldown_days: int | None = None
    access_target_days: int = 30
    rng_seed: int | None = None

    def __post_init__(self) -> None:
        if self.horizon_days <= 0:
            raise ValueError("horizon_days must be positive")
        if self.slots_per_day <= 0:
            raise ValueError("slots_per_day must be positive")
        if self.burn_in_days < 0:
            raise ValueError("burn_in_days must be non-negative")
        if self.measure_days <= 0:
            raise ValueError("measure_days must be positive")
        if self.cooldown_days is not None and self.cooldown_days < 0:
            raise ValueError("cooldown_days must be non-negative")
        if self.access_target_days < 0:
            raise ValueError("access_target_days must be non-negative")

    @property
    def effective_cooldown_days(self) -> int:
        """Return the cooldown length, defaulting to one full booking horizon."""
        return self.horizon_days if self.cooldown_days is None else self.cooldown_days

    @property
    def measured_slot_count(self) -> int:
        """Return the number of slots included in the measurement window."""
        return self.measure_days * self.slots_per_day

    @property
    def total_days(self) -> int:
        """Return the full simulation length including burn-in and cooldown."""
        return self.burn_in_days + self.measure_days + self.effective_cooldown_days


@dataclass
class Appointment:
    """
    Booked-slot record carried by the simulator.

    Mathematically, the day-level state only needs class counts by residual
    day. The implementation keeps appointment-level timing fields so results
    can be audited, summarized, and linked back to booking and service events.
    """
    patient_id: int
    class_id: int
    booking_day: int
    booking_slot: int | None
    appointment_day: int
    appointment_slot: int
    tau_booked: int
    tracked_cohort: bool


@dataclass
class SimulationResult:
    config: SimulationConfig
    class_configs: tuple[PatientClassConfig, ...]
    policy_name: str
    arrival_log: pd.DataFrame
    slot_log: pd.DataFrame
    cohort_log: pd.DataFrame
    state_log: pd.DataFrame
    summary_by_class: pd.DataFrame
    summary_aggregate: pd.Series
    slot_summary_by_class: pd.DataFrame
    slot_summary_aggregate: pd.Series
    delay_distribution_by_class: dict[int, pd.Series]
    delay_distribution_aggregate: pd.Series
    daily_journal_by_class: pd.DataFrame
    daily_journal_aggregate: pd.DataFrame


def _build_frame(records: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    """Convert record dictionaries into a DataFrame with a fixed column order."""
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame.from_records(records, columns=columns)


def _combine_counts(frames: Sequence[pd.Series], fill_value: float = 0.0) -> pd.Series:
    """Add together count series while preserving indexes across missing keys."""
    if not frames:
        return pd.Series(dtype=float)
    result = frames[0].copy()
    for series in frames[1:]:
        result = result.add(series, fill_value=fill_value)
    return result


def _safe_ratio(numerator: float, denominator: float) -> float:
    """Return ``numerator / denominator`` and map zero-denominator cases to zero."""
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _label_for(class_configs: Sequence[PatientClassConfig], class_id: int) -> str:
    """Return the display label associated with a patient class identifier."""
    for config in class_configs:
        if config.class_id == class_id:
            return config.label or f"class_{class_id}"
    return f"class_{class_id}"


def _validate_class_configs(class_configs: Sequence[PatientClassConfig]) -> tuple[PatientClassConfig, ...]:
    """Validate and freeze the patient-class configuration sequence."""
    if len(class_configs) < 1:
        raise ValueError("at least one patient class is required")
    class_ids = [config.class_id for config in class_configs]
    if len(set(class_ids)) != len(class_ids):
        raise ValueError("class_id values must be unique")
    return tuple(class_configs)


def _is_measured_day(day: int, config: SimulationConfig) -> bool:
    """Check whether an absolute simulation day belongs to the measurement window."""
    return config.burn_in_days <= day < config.burn_in_days + config.measure_days


def _measured_day_index(day: int, config: SimulationConfig) -> int:
    """Map an absolute simulation day to its zero-based measured-day index."""
    return day - config.burn_in_days


def simulate(
    class_configs: Sequence[PatientClassConfig],
    config: SimulationConfig | None = None,
    policy: AllocationPolicy | None = None,
) -> SimulationResult:
    """
    Run the day-level rolling-horizon appointment-book simulation.

    Each day applies scheduled-patient cancellations, draws class-specific
    arrivals, offers future slots in policy order, applies balking, resolves
    that day's no-shows/service, records measured metrics, and advances the
    rolling calendar.
    """
    config = config or SimulationConfig()
    class_configs = _validate_class_configs(class_configs)
    policy = policy or FCFSPolicy()
    rng = np.random.default_rng(config.rng_seed)
    class_lookup = {class_config.class_id: class_config for class_config in class_configs}

    calendar: list[list[Appointment | None]] = [
        [None for _ in range(config.slots_per_day)] for _ in range(config.horizon_days)
    ]
    arrival_records: list[dict[str, Any]] = []
    slot_records: list[dict[str, Any]] = []
    state_records: list[dict[str, Any]] = []
    cohort_records: dict[int, dict[str, Any]] = {}
    next_patient_id = 1

    def apply_daily_cancellations(day: int) -> None:
        """Release slots whose booked patient cancels at the start of the day."""
        for day_offset, day_slots in enumerate(calendar):
            for slot_index, appointment in enumerate(day_slots):
                if appointment is None:
                    continue
                class_config = class_lookup[appointment.class_id]
                cancel_hazard = evaluate_cancellation_probability(
                    class_config.cancel_probability,
                    appointment.tau_booked,
                    day_offset,
                )
                if rng.random() >= cancel_hazard:
                    continue
                if appointment.tracked_cohort:
                    cohort_record = cohort_records[appointment.patient_id]
                    if cohort_record["outcome"] is None:
                        cohort_record["outcome"] = "canceled"
                        cohort_record["resolution_day"] = day
                        cohort_record["resolution_slot"] = -1
                calendar[day_offset][slot_index] = None

    def record_state(day: int) -> None:
        """Record the post-cancellation day-level state summary ``X_{i,r}^D``."""
        measured_day = _measured_day_index(day, config)
        counts = {
            (class_id, residual_delay): 0
            for class_id in class_lookup
            for residual_delay in range(config.horizon_days)
        }
        for residual_delay, day_slots in enumerate(calendar):
            for appointment in day_slots:
                if appointment is None:
                    continue
                counts[(appointment.class_id, residual_delay)] += 1
        for (class_id, residual_delay), count in counts.items():
            state_records.append(
                {
                    "day": day,
                    "measured_day": measured_day,
                    "class_id": class_id,
                    "residual_delay": residual_delay,
                    "count": count,
                }
            )

    def select_future_slot(class_id: int, day: int) -> Any | None:
        """Ask the allocation policy for a future slot only."""
        selection = policy.select_slot(
            calendar,
            class_id,
            day,
            config.slots_per_day - 1,
        )
        if selection is None or selection.day_offset <= 0:
            return None
        return selection

    for day in range(config.total_days):
        apply_daily_cancellations(day)
        if _is_measured_day(day, config):
            record_state(day)

        arrivals_by_class = {
            class_config.class_id: int(rng.poisson(class_config.arrival_rate))
            for class_config in class_configs
        }
        arrival_order = [
            class_id
            for class_id, count in arrivals_by_class.items()
            for _ in range(count)
        ]
        if arrival_order:
            arrival_order = list(rng.permutation(arrival_order))

        for class_id in arrival_order:
            class_config = class_lookup[class_id]
            selection = select_future_slot(class_id, day)
            no_offer = selection is None
            if no_offer:
                offered_day = None
                offered_slot = None
                tau_offered = None
                booked = False
                balked = False
            else:
                offered_day = day + selection.day_offset
                offered_slot = selection.slot_index
                tau_offered = int(selection.day_offset)
                balk_probability = clamp_probability(class_config.balk_probability(tau_offered))
                booked = bool(rng.random() >= balk_probability)
                balked = not booked

            if _is_measured_day(day, config):
                arrival_records.append(
                    {
                        "arrival_day": day,
                        "arrival_slot": None,
                        "measured_day": _measured_day_index(day, config),
                        "class_id": class_id,
                        "patient_id": next_patient_id if booked else None,
                        "offered_day": offered_day,
                        "offered_slot": offered_slot,
                        "tau_offered": tau_offered,
                        "booked": booked,
                        "balked": balked,
                        "no_offer": no_offer,
                        "not_booked": not booked,
                    }
                )

            if not booked or selection is None:
                continue

            appointment = Appointment(
                patient_id=next_patient_id,
                class_id=class_id,
                booking_day=day,
                booking_slot=None,
                appointment_day=offered_day,
                appointment_slot=offered_slot,
                tau_booked=tau_offered,
                tracked_cohort=_is_measured_day(day, config),
            )
            calendar[selection.day_offset][selection.slot_index] = appointment
            if appointment.tracked_cohort:
                cohort_records[appointment.patient_id] = {
                    "patient_id": appointment.patient_id,
                    "class_id": appointment.class_id,
                    "booking_day": appointment.booking_day,
                    "booking_slot": appointment.booking_slot,
                    "measured_day": _measured_day_index(day, config),
                    "appointment_day": appointment.appointment_day,
                    "appointment_slot": appointment.appointment_slot,
                    "tau_booked": appointment.tau_booked,
                    "outcome": None,
                    "resolution_day": None,
                    "resolution_slot": None,
                }
            next_patient_id += 1

        for slot, current_appointment in enumerate(calendar[0]):
            if current_appointment is None:
                if _is_measured_day(day, config):
                    slot_records.append(
                        {
                            "day": day,
                            "slot": slot,
                            "measured_day": _measured_day_index(day, config),
                            "occupied": False,
                            "class_id": None,
                            "tau_booked": None,
                            "outcome": "empty",
                        }
                    )
                continue

            no_show_probability = clamp_probability(
                class_lookup[current_appointment.class_id].no_show_probability(current_appointment.tau_booked)
            )
            outcome = "no_show" if rng.random() < no_show_probability else "served"
            if current_appointment.tracked_cohort:
                cohort_record = cohort_records[current_appointment.patient_id]
                if cohort_record["outcome"] is None:
                    cohort_record["outcome"] = outcome
                    cohort_record["resolution_day"] = day
                    cohort_record["resolution_slot"] = slot
            if _is_measured_day(day, config):
                slot_records.append(
                    {
                        "day": day,
                        "slot": slot,
                        "measured_day": _measured_day_index(day, config),
                        "occupied": True,
                        "class_id": current_appointment.class_id,
                        "tau_booked": current_appointment.tau_booked,
                        "outcome": outcome,
                    }
                )
            calendar[0][slot] = None

        calendar.pop(0)
        calendar.append([None for _ in range(config.slots_per_day)])

    for cohort_record in cohort_records.values():
        if cohort_record["outcome"] is None:
            cohort_record["outcome"] = "still_scheduled_end"

    arrival_log = _build_frame(arrival_records, MEASURED_ARRIVAL_COLUMNS)
    slot_log = _build_frame(slot_records, SLOT_LOG_COLUMNS)
    cohort_log = _build_frame(list(cohort_records.values()), COHORT_COLUMNS)
    state_log = _build_frame(state_records, STATE_COLUMNS)

    summary_by_class = _build_summary_by_class(arrival_log, cohort_log, class_configs, config)
    summary_aggregate = _build_aggregate_summary(summary_by_class)
    slot_summary_by_class, slot_summary_aggregate = _build_slot_summaries(slot_log, class_configs, config)
    delay_distribution_by_class, delay_distribution_aggregate = _build_delay_distributions(cohort_log, class_configs)
    daily_journal_by_class, daily_journal_aggregate = _build_daily_journals(
        arrival_log=arrival_log,
        cohort_log=cohort_log,
        slot_log=slot_log,
        state_log=state_log,
        class_configs=class_configs,
        config=config,
    )

    return SimulationResult(
        config=config,
        class_configs=class_configs,
        policy_name=type(policy).__name__,
        arrival_log=arrival_log,
        slot_log=slot_log,
        cohort_log=cohort_log,
        state_log=state_log,
        summary_by_class=summary_by_class,
        summary_aggregate=summary_aggregate,
        slot_summary_by_class=slot_summary_by_class,
        slot_summary_aggregate=slot_summary_aggregate,
        delay_distribution_by_class=delay_distribution_by_class,
        delay_distribution_aggregate=delay_distribution_aggregate,
        daily_journal_by_class=daily_journal_by_class,
        daily_journal_aggregate=daily_journal_aggregate,
    )


def _build_summary_by_class(
    arrival_log: pd.DataFrame,
    cohort_log: pd.DataFrame,
    class_configs: Sequence[PatientClassConfig],
    config: SimulationConfig,
) -> pd.DataFrame:
    """Assemble class-level booking, access, and attendance KPIs."""
    records: list[dict[str, Any]] = []
    for class_config in class_configs:
        class_id = class_config.class_id
        class_arrivals = arrival_log[arrival_log["class_id"] == class_id] if not arrival_log.empty else arrival_log
        class_cohort = cohort_log[cohort_log["class_id"] == class_id] if not cohort_log.empty else cohort_log
        delays = class_cohort["tau_booked"].dropna().astype(float) if not class_cohort.empty else pd.Series(dtype=float)
        served_delays = (
            class_cohort.loc[class_cohort["outcome"] == "served", "tau_booked"].dropna().astype(float)
            if not class_cohort.empty
            else pd.Series(dtype=float)
        )
        arrivals = int(len(class_arrivals))
        booked = int(len(class_cohort))
        balked = int(class_arrivals["balked"].sum()) if not class_arrivals.empty else 0
        canceled = int((class_cohort["outcome"] == "canceled").sum()) if not class_cohort.empty else 0
        no_shows = int((class_cohort["outcome"] == "no_show").sum()) if not class_cohort.empty else 0
        served = int((class_cohort["outcome"] == "served").sum()) if not class_cohort.empty else 0
        still_scheduled_end = (
            int((class_cohort["outcome"] == "still_scheduled_end").sum()) if not class_cohort.empty else 0
        )
        no_offer = int(class_arrivals["no_offer"].sum()) if not class_arrivals.empty else 0
        not_booked = int(class_arrivals["not_booked"].sum()) if not class_arrivals.empty else 0
        booked_within_access_target = (
            int((class_cohort["tau_booked"].astype(int) < config.access_target_days).sum()) if not class_cohort.empty else 0
        )

        records.append(
            {
                "class_id": class_id,
                "label": _label_for(class_configs, class_id),
                "arrivals": arrivals,
                "booked": booked,
                "balked": balked,
                "no_offer": no_offer,
                "not_booked": not_booked,
                "booked_within_access_target": booked_within_access_target,
                "canceled": canceled,
                "no_shows": no_shows,
                "served": served,
                "still_scheduled_end": still_scheduled_end,
                "mean_delay_booked": float(delays.mean()) if not delays.empty else 0.0,
                "mean_delay_served": float(served_delays.mean()) if not served_delays.empty else 0.0,
                "served_per_booked": _safe_ratio(served, booked),
                "booked_per_arrival": _safe_ratio(booked, arrivals),
                "booked_within_access_target_per_arrival": _safe_ratio(booked_within_access_target, arrivals),
                "booked_within_access_target_per_booked": _safe_ratio(booked_within_access_target, booked),
            }
        )

    if not records:
        return pd.DataFrame(
            columns=[
                "class_id",
                "label",
                "arrivals",
                "booked",
                "balked",
                "no_offer",
                "not_booked",
                "booked_within_access_target",
                "canceled",
                "no_shows",
                "served",
                "still_scheduled_end",
                "mean_delay_booked",
                "mean_delay_served",
                "served_per_booked",
                "booked_per_arrival",
                "booked_within_access_target_per_arrival",
                "booked_within_access_target_per_booked",
            ]
        )

    return pd.DataFrame.from_records(records)


def _build_aggregate_summary(summary_by_class: pd.DataFrame) -> pd.Series:
    """Collapse class-level KPIs into an aggregate summary row."""
    if summary_by_class.empty:
        return pd.Series(dtype=float)

    numeric_columns = [
        "arrivals",
        "booked",
        "balked",
        "no_offer",
        "not_booked",
        "booked_within_access_target",
        "canceled",
        "no_shows",
        "served",
        "still_scheduled_end",
    ]
    aggregate = summary_by_class[numeric_columns].sum()
    booked_weight = summary_by_class["booked"].sum()
    served_weight = summary_by_class["served"].sum()
    aggregate["mean_delay_booked"] = _safe_ratio(
        float((summary_by_class["mean_delay_booked"] * summary_by_class["booked"]).sum()),
        float(booked_weight),
    )
    aggregate["mean_delay_served"] = _safe_ratio(
        float((summary_by_class["mean_delay_served"] * summary_by_class["served"]).sum()),
        float(served_weight),
    )
    aggregate["served_per_booked"] = _safe_ratio(aggregate["served"], aggregate["booked"])
    aggregate["booked_per_arrival"] = _safe_ratio(aggregate["booked"], aggregate["arrivals"])
    aggregate["booked_within_access_target_per_arrival"] = _safe_ratio(
        aggregate["booked_within_access_target"],
        aggregate["arrivals"],
    )
    aggregate["booked_within_access_target_per_booked"] = _safe_ratio(
        aggregate["booked_within_access_target"],
        aggregate["booked"],
    )
    aggregate["class_id"] = "all"
    aggregate["label"] = "all"
    return aggregate


def _build_slot_summaries(
    slot_log: pd.DataFrame,
    class_configs: Sequence[PatientClassConfig],
    config: SimulationConfig,
) -> tuple[pd.DataFrame, pd.Series]:
    """Compute slot-based utilization summaries by class and in aggregate."""
    total_slots = config.measured_slot_count
    records: list[dict[str, Any]] = []
    for class_config in class_configs:
        class_id = class_config.class_id
        class_slots = slot_log[slot_log["class_id"] == class_id] if not slot_log.empty else slot_log
        booked_slots = int(class_slots["occupied"].eq(True).sum()) if not class_slots.empty else 0
        served_slots = int((class_slots["outcome"] == "served").sum()) if not class_slots.empty else 0
        no_show_slots = int((class_slots["outcome"] == "no_show").sum()) if not class_slots.empty else 0
        delays = class_slots["tau_booked"].dropna().astype(float) if not class_slots.empty else pd.Series(dtype=float)
        records.append(
            {
                "class_id": class_id,
                "label": _label_for(class_configs, class_id),
                "total_slots": total_slots,
                "booked_slots": booked_slots,
                "served_slots": served_slots,
                "no_show_slots": no_show_slots,
                "empty_slots": 0,
                "mean_delay_slots": float(delays.mean()) if not delays.empty else 0.0,
                "booked_slot_utilization": _safe_ratio(booked_slots, total_slots),
                "attended_slot_utilization": _safe_ratio(served_slots, total_slots),
            }
        )

    slot_summary_by_class = pd.DataFrame.from_records(records)
    aggregate = pd.Series(
        {
            "class_id": "all",
            "label": "all",
            "total_slots": total_slots,
            "booked_slots": int(slot_log["occupied"].eq(True).sum()) if not slot_log.empty else 0,
            "served_slots": int((slot_log["outcome"] == "served").sum()) if not slot_log.empty else 0,
            "no_show_slots": int((slot_log["outcome"] == "no_show").sum()) if not slot_log.empty else 0,
            "empty_slots": int((slot_log["outcome"] == "empty").sum()) if not slot_log.empty else total_slots,
            "mean_delay_slots": float(slot_log["tau_booked"].dropna().astype(float).mean())
            if not slot_log.empty and not slot_log["tau_booked"].dropna().empty
            else 0.0,
        }
    )
    aggregate["booked_slot_utilization"] = _safe_ratio(aggregate["booked_slots"], total_slots)
    aggregate["attended_slot_utilization"] = _safe_ratio(aggregate["served_slots"], total_slots)
    return slot_summary_by_class, aggregate


def _build_delay_distributions(
    cohort_log: pd.DataFrame,
    class_configs: Sequence[PatientClassConfig],
) -> tuple[dict[int, pd.Series], pd.Series]:
    """Count booked delays by class and for the full measured cohort."""
    by_class: dict[int, pd.Series] = {}
    for class_config in class_configs:
        class_id = class_config.class_id
        class_delays = (
            cohort_log.loc[cohort_log["class_id"] == class_id, "tau_booked"].value_counts().sort_index()
            if not cohort_log.empty
            else pd.Series(dtype=int)
        )
        by_class[class_id] = class_delays
    aggregate = cohort_log["tau_booked"].value_counts().sort_index() if not cohort_log.empty else pd.Series(dtype=int)
    return by_class, aggregate


def _build_daily_journals(
    *,
    arrival_log: pd.DataFrame,
    cohort_log: pd.DataFrame,
    slot_log: pd.DataFrame,
    state_log: pd.DataFrame,
    class_configs: Sequence[PatientClassConfig],
    config: SimulationConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build per-day operational journals from measured arrivals, cohorts, slots, and state."""
    by_class_records: list[dict[str, Any]] = []
    aggregate_records: list[dict[str, Any]] = []

    for measured_day in range(config.measure_days):
        absolute_day = config.burn_in_days + measured_day
        day_arrivals = arrival_log[arrival_log["measured_day"] == measured_day] if not arrival_log.empty else arrival_log
        day_cohort_bookings = cohort_log[cohort_log["measured_day"] == measured_day] if not cohort_log.empty else cohort_log
        day_slots = slot_log[slot_log["measured_day"] == measured_day] if not slot_log.empty else slot_log
        day_state = state_log[state_log["measured_day"] == measured_day] if not state_log.empty else state_log

        aggregate_new_booking_delays = (
            day_cohort_bookings["tau_booked"].dropna().astype(float)
            if not day_cohort_bookings.empty
            else pd.Series(dtype=float)
        )
        aggregate_record = {
            "day": absolute_day,
            "measured_day": measured_day,
            "label": "all",
            "scheduled_start_of_day": int(day_state["count"].sum()) if not day_state.empty else 0,
            "scheduled_for_today_start": int(
                day_state.loc[day_state["residual_delay"] == 0, "count"].sum()
            ) if not day_state.empty else 0,
            "arrivals": int(len(day_arrivals)),
            "booked": int(len(day_cohort_bookings)),
            "balked": int(day_arrivals["balked"].sum()) if not day_arrivals.empty else 0,
            "no_offer": int(day_arrivals["no_offer"].sum()) if not day_arrivals.empty else 0,
            "not_booked": int(day_arrivals["not_booked"].sum()) if not day_arrivals.empty else 0,
            "booked_within_access_target": int(
                (day_cohort_bookings["tau_booked"].astype(int) < config.access_target_days).sum()
            ) if not day_cohort_bookings.empty else 0,
            "canceled": int(
                ((cohort_log["outcome"] == "canceled") & (cohort_log["resolution_day"] == absolute_day)).sum()
            ) if not cohort_log.empty else 0,
            "no_shows": int((day_slots["outcome"] == "no_show").sum()) if not day_slots.empty else 0,
            "served": int((day_slots["outcome"] == "served").sum()) if not day_slots.empty else 0,
            "booked_slots": int(day_slots["occupied"].eq(True).sum()) if not day_slots.empty else 0,
            "served_slots": int((day_slots["outcome"] == "served").sum()) if not day_slots.empty else 0,
            "no_show_slots": int((day_slots["outcome"] == "no_show").sum()) if not day_slots.empty else 0,
            "empty_slots": int((day_slots["outcome"] == "empty").sum()) if not day_slots.empty else config.slots_per_day,
            "mean_tau_booked_new_bookings": float(aggregate_new_booking_delays.mean())
            if not aggregate_new_booking_delays.empty
            else 0.0,
        }
        aggregate_record["booked_per_arrival"] = _safe_ratio(aggregate_record["booked"], aggregate_record["arrivals"])
        aggregate_record["booked_within_access_target_per_arrival"] = _safe_ratio(
            aggregate_record["booked_within_access_target"],
            aggregate_record["arrivals"],
        )
        aggregate_record["booked_within_access_target_per_booked"] = _safe_ratio(
            aggregate_record["booked_within_access_target"],
            aggregate_record["booked"],
        )
        aggregate_record["served_per_booked"] = _safe_ratio(aggregate_record["served"], aggregate_record["booked"])
        aggregate_record["booked_slot_utilization"] = _safe_ratio(
            aggregate_record["booked_slots"],
            config.slots_per_day,
        )
        aggregate_record["attended_slot_utilization"] = _safe_ratio(
            aggregate_record["served_slots"],
            config.slots_per_day,
        )
        aggregate_records.append(aggregate_record)

        for class_config in class_configs:
            class_id = class_config.class_id
            class_day_arrivals = day_arrivals[day_arrivals["class_id"] == class_id] if not day_arrivals.empty else day_arrivals
            class_day_bookings = (
                day_cohort_bookings[day_cohort_bookings["class_id"] == class_id]
                if not day_cohort_bookings.empty
                else day_cohort_bookings
            )
            class_day_slots = day_slots[day_slots["class_id"] == class_id] if not day_slots.empty else day_slots
            class_day_state = day_state[day_state["class_id"] == class_id] if not day_state.empty else day_state
            new_booking_delays = (
                class_day_bookings["tau_booked"].dropna().astype(float)
                if not class_day_bookings.empty
                else pd.Series(dtype=float)
            )
            record = {
                "day": absolute_day,
                "measured_day": measured_day,
                "class_id": class_id,
                "label": _label_for(class_configs, class_id),
                "scheduled_start_of_day": int(class_day_state["count"].sum()) if not class_day_state.empty else 0,
                "scheduled_for_today_start": int(
                    class_day_state.loc[class_day_state["residual_delay"] == 0, "count"].sum()
                ) if not class_day_state.empty else 0,
                "arrivals": int(len(class_day_arrivals)),
                "booked": int(len(class_day_bookings)),
                "balked": int(class_day_arrivals["balked"].sum()) if not class_day_arrivals.empty else 0,
                "no_offer": int(class_day_arrivals["no_offer"].sum()) if not class_day_arrivals.empty else 0,
                "not_booked": int(class_day_arrivals["not_booked"].sum()) if not class_day_arrivals.empty else 0,
                "booked_within_access_target": int(
                    (class_day_bookings["tau_booked"].astype(int) < config.access_target_days).sum()
                ) if not class_day_bookings.empty else 0,
                "canceled": int(
                    (
                        (cohort_log["class_id"] == class_id)
                        & (cohort_log["outcome"] == "canceled")
                        & (cohort_log["resolution_day"] == absolute_day)
                    ).sum()
                ) if not cohort_log.empty else 0,
                "no_shows": int((class_day_slots["outcome"] == "no_show").sum()) if not class_day_slots.empty else 0,
                "served": int((class_day_slots["outcome"] == "served").sum()) if not class_day_slots.empty else 0,
                "booked_slots": int(class_day_slots["occupied"].eq(True).sum()) if not class_day_slots.empty else 0,
                "served_slots": int((class_day_slots["outcome"] == "served").sum()) if not class_day_slots.empty else 0,
                "no_show_slots": int((class_day_slots["outcome"] == "no_show").sum()) if not class_day_slots.empty else 0,
                "mean_tau_booked_new_bookings": float(new_booking_delays.mean()) if not new_booking_delays.empty else 0.0,
            }
            record["booked_per_arrival"] = _safe_ratio(record["booked"], record["arrivals"])
            record["booked_within_access_target_per_arrival"] = _safe_ratio(
                record["booked_within_access_target"],
                record["arrivals"],
            )
            record["booked_within_access_target_per_booked"] = _safe_ratio(
                record["booked_within_access_target"],
                record["booked"],
            )
            record["served_per_booked"] = _safe_ratio(record["served"], record["booked"])
            record["booked_slot_utilization"] = _safe_ratio(record["booked_slots"], config.slots_per_day)
            record["attended_slot_utilization"] = _safe_ratio(record["served_slots"], config.slots_per_day)
            by_class_records.append(record)

    return (
        _build_frame(by_class_records, DAILY_JOURNAL_BY_CLASS_COLUMNS),
        _build_frame(aggregate_records, DAILY_JOURNAL_AGGREGATE_COLUMNS),
    )
