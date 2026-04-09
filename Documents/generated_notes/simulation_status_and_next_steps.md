# Simulation Status and Next Steps

## Purpose

This note checks the current simulation work against the scope described in the supervisor email and records what is implemented today, what is only partially covered, and what should be built next.

The relevant current artifacts are:

- [appointment_simulation](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/appointment_simulation)
- [simulation.ipynb](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Notebooks/simulation.ipynb)
- [first_two_class_simulation_note.tex](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.tex)
- [first_two_class_simulation_note.pdf](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.pdf)

## Bottom Line

The current simulator is now compliant with the **initial model** described in the email at the level of a first operational prototype:

- two patient types arriving to a booking system
- delay-sensitive booking behavior
- delay-sensitive no-show behavior
- daily pre-appointment cancellation described by `\phi_i(\tau)`
- FCFS allocation
- a class-reservation policy
- a class-specific booking-window policy
- sensitivity-analysis support
- daily access and utilization reporting

It is **not yet fully compliant** with the broader Phase 1 ambitions in the email, because the following components are still absent:

- overbooking logic
- reminder/confirmation interventions
- payer-mix and financial-margin modeling
- calibration to Columbia Doctors data
- explicit process-mapping inputs from real scheduling workflows

## Compliance Check

| Email requirement | Status | Notes |
| --- | --- | --- |
| Two types of patients arrive to call center to book | Implemented | The engine supports two classes now and is already general enough for more than two. |
| Scheduling-delay sensitivity for booking | Implemented | `b_i(\tau)` is the class-specific booking-decline function. |
| Scheduling-delay sensitivity for no-shows | Implemented | `\xi_i(\tau)` uses the original offered delay, which is the correct formulation for this problem. |
| Cancellations matter operationally | Implemented | Patients face daily pre-appointment cancellation risk and reopened future slots return to the calendar. |
| FCFS scheduling policy | Implemented | This remains the baseline policy. |
| Reserve `x%` / `100-x%` capacity by type | Implemented | Added a strict reserved-capacity policy. Shares are converted to daily slot counts. |
| Max booking window `k_1`, `k_2` by type | Implemented | Added a class-specific booking-window policy. |
| Add more scheduling policies later | Implemented structurally | The simulator uses a policy interface and can accept additional slot-selection rules. |
| Add more customer types later | Implemented structurally | The core is not hard-coded to two types. |
| Access metric such as `P(time to appointment < 30 days)` | Implemented | Added configurable access-target reporting based on `\tau < T_access`. |
| Provider utilization and empty-slot metrics | Implemented | Booked-slot utilization, attended-slot utilization, no-show slots, and empty slots are reported. |
| Financial performance by payer mix | Not yet implemented | No revenue, cost, or payer-class layer exists yet. |
| Overbooking policies | Not yet implemented | Not yet modeled. |
| Reminder protocols | Not yet implemented | No reminder-triggered behavior changes yet. |
| Ground-truth booking rules from workflow mapping | Not yet implemented | The current rules are stylized, not calibrated to site operations. |
| Data calibration to Columbia Doctors | Not yet implemented | The engine is ready for calibration once data are available. |

## What We Have Today

### Core model

The current engine is a rolling-horizon discrete-event appointment simulation with:

- default horizon `H = 15` days
- default daily capacity `S = 25` slots
- slot-by-slot event progression
- class-specific Poisson arrivals
- explicit slot-level calendar state
- explicit storage of the original offered delay `\tau`

The current front-end arrival parameterization is:

\[
\lambda_1 = p\lambda,
\qquad
\lambda_2 = (1-p)\lambda,
\]

where `\lambda` is the total expected arrival rate per slot and `p` is the class-1 arrival share.

The class-specific behavior object remains:

\[
B_i = \{b_i(\tau), \phi_i(\tau,r), \xi_i(\tau)\}.
\]

Here `\phi_i(\tau,r)` is the daily pre-appointment cancellation probability for a class-`i`
patient who booked with original delay `\tau` and is currently `r` days away from service.
In the current implementation, the note-aligned default is the simple direct form
\[
\phi_i(\tau,r)=
\begin{cases}
0, & r=0,\\
\min\{a_i+b_i\tau,\phi_{i,\max}\}\dfrac{r}{\tau}, & 1\le r\le \tau,
\end{cases}
\]
so that patients booked far in advance start more cancellation-prone, but their daily
cancellation probability falls as the appointment approaches. The code still accepts the earlier
scalar cancellation parameterization for backward compatibility.

### Current policy set

The codebase now includes the following policy examples:

- `FCFSPolicy`
- `LatestAvailablePolicy`
- `ReservedCapacityPolicy`
- `ClassWindowPolicy`

The two new policies correspond directly to the examples listed in the email's initial-model paragraph.

### Current KPI set

At the aggregate and class-specific levels, the simulator currently reports:

- arrivals
- booked
- balked
- no-offer
- not-booked
- canceled
- no-shows
- served
- mean booked delay
- mean served delay
- `served / booked`
- `booked / arrival`
- `P(\tau < T_access \mid arrival)`
- `P(\tau < T_access \mid booked)`
- booked-slot utilization
- attended-slot utilization
- empty slots

Important interpretation:

- `balked` now means the patient was offered a slot and declined it
- `no_offer` means no eligible slot was available under the active policy
- `not_booked = balked + no_offer`

That split is important because the email explicitly distinguishes delay-sensitive patient behavior from operational booking constraints.

### Daily journal

The simulator now exposes a per-day journal in two forms:

- `result.daily_journal_by_class`
- `result.daily_journal_aggregate`

This is the best current answer to “what do we have today, day by day?”

The aggregate daily journal includes:

- `scheduled_start_of_day`
- `scheduled_for_today_start`
- `arrivals`
- `booked`
- `balked`
- `no_offer`
- `not_booked`
- `booked_within_access_target`
- `canceled`
- `no_shows`
- `served`
- `booked_slots`
- `served_slots`
- `no_show_slots`
- `empty_slots`
- `mean_tau_booked_new_bookings`
- `booked_per_arrival`
- `booked_within_access_target_per_arrival`
- `booked_within_access_target_per_booked`
- `served_per_booked`
- `booked_slot_utilization`
- `attended_slot_utilization`

The class-level daily journal includes the same booking and service fields, except that empty slots remain an aggregate concept.

One nuance:

- cohort summaries and the daily `canceled` counts are currently tied to tracked measured-window bookings
- slot utilization and empty-slot outcomes already reflect the realized operational effect on the measured days

So the access and utilization views are already operationally useful, even before full calibration.

## Interpretation Relative to the Email

### What is already strong enough for “quick insights”

The current simulator is already good enough for quick sensitivity studies on:

- how load affects average delay
- how delay-sensitive no-show changes realized capacity
- how class-specific booking windows affect access
- how strict slot reservation changes type-specific access
- how empty slots emerge through cancellation and no-show behavior

This matches the part of the email that emphasizes immediate operational insight before full estimation and optimization.

### What is still only a proxy

The supervisor email is framed partly in terms of **panel size `N`**.
The current simulator does not yet model panel size directly.
Instead, the current front-end experiments vary total arrival pressure through `\lambda` and allocate that demand across the two classes with a fixed share `p`.

For the current prototype, this is acceptable.
Operationally, it means:

- today we are sweeping demand pressure through `\lambda` while holding `p` fixed
- later we should map either `\lambda = N \nu` at the aggregate level or `\lambda_i = N_i \nu_i` at the class level, where `\nu_i` is request intensity per panel member

That is the right next step once calibration data are available.

## Recommended Next Steps

### 1. Finish the “initial model” notebook story

The notebook should remain the main quick-insight artifact.
It should emphasize four comparison policies:

- FCFS
- reserved capacity
- class-specific booking windows
- one deliberately poor policy for contrast

This is now feasible with the implemented policy layer.

### 2. Add an explicit overbooking layer

This is the next major modeling gap relative to the email.
The clean first extension is:

- allow policy-dependent daily capacity above nominal `S`
- assign an overtime or overbooking cost
- measure whether added booked capacity is actually realized after no-shows and cancellations

This would connect the simulator more directly to Liu and Ziya.

### 3. Add a reminder / confirmation intervention layer

The email explicitly mentions reminder protocols.
The simplest first extension is not a detailed messaging workflow.
It is a behavioral intervention layer that changes one or more of:

- `\phi_i`
- `\xi_i(\tau)`
- possibly `b_i(\tau)`

This would let the working group test reminder strategies before modeling the exact operational process.

### 4. Add a payer-mix and margin layer

This is the main missing piece for the “financial health” objective.
The clean structure is:

- reinterpret or expand patient classes to include payer type
- attach revenue, variable cost, and downstream value assumptions to attended visits
- optionally assign different no-show/cancellation behavior by payer class

Then margins can be reported alongside access and utilization.

### 5. Map panel size to arrivals

To connect to the email more directly, the next calibration layer should introduce:

- panel size `N` and, if needed, class-specific panels `N_i`
- per-member request intensity `\nu_i`
- `\lambda = N \nu` together with a class-mix rule, or directly `\lambda_i = N_i \nu_i`

This will make panel-size experiments explicit instead of using `\lambda` as a direct proxy for demand pressure.

### 6. Calibrate to process mapping and real data

Once ground-truth workflow information and data arrive, the first calibration targets should be:

- arrival intensity by class
- booking-window acceptance behavior
- cancellation rates and timing
- no-show curves by specialty or department
- current booking constraints
- reminder protocol effects

That is the point where the simulator should stop being a stylized sensitivity model and become a department-specific operational model.

## Recommended Short Message to the Working Group

If we want a concise operational status message, the best summary is:

“Today we have a working two-class appointment simulation with delay-sensitive booking, cancellation, and no-show behavior on an explicit calendar. It supports FCFS, strict capacity reservation, and class-specific booking-window rules, and it reports daily access and utilization journals. The main next steps are overbooking, reminder effects, payer-mix margins, and calibration to actual scheduling workflows and Columbia Doctors data.”
