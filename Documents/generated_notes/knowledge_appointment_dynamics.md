# Knowledge File: Appointment Scheduling Models and Dynamics

## Scope

This file synthesizes the queueing models and main dynamic insights from:

- `Documents/green_reducing.pdf`
- `Documents/optimal_choice_appointment_scheduling.pdf`
- `Documents/Panel size and overbooking-online.pdf`

Note:

- `Notebooks/simulation.ipynb` is empty and contained no usable model content.

## Executive Summary

All three documents study the same core phenomenon:

- Longer appointment backlogs create longer delays.
- Longer delays reduce patient show-up probabilities.
- Lower show-up probabilities reduce effective capacity.
- Reduced effective capacity can increase backlog even further.

That feedback loop is the central dynamic in all three papers.

The papers differ mainly in:

- which control lever is optimized
- how no-show slots are treated
- whether no-shows reschedule
- whether the objective is access/service level or throughput/net reward

The most important cross-paper insight is this:

- Average no-show level is not enough to determine the right decision.
- What matters more is delay sensitivity, meaning how fast show-up probability deteriorates as delay increases.

## Canonical Notation

To unify the papers, this file uses the following notation:

- `N`: panel size
- `lambda = N * lambda_0`: aggregate appointment-request rate
- `mu`: service rate or daily appointment capacity
- `K`: appointment-queue capacity or scheduling-window limit
- `j`: number of scheduled appointments already in system when a patient requests an appointment
- `p_j`: probability a patient shows up after seeing `j` appointments ahead
- `gamma(j) = 1 - p_j`: no-show probability
- `xi`: salvage probability/value from an otherwise empty slot via walk-ins or ancillary work
- `h`: penalty for rejecting or not scheduling a patient
- `r`: probability a no-show reschedules
- `rho = lambda / mu`: traffic intensity

In most formulations:

- `p_j` decreases with `j`
- delay in days is approximated by `floor(j / mu)` or `j / mu`

## Canonical Dynamic Template

At the highest level, the system evolves as follows:

1. Appointment requests arrive according to a Poisson process with rate `lambda`.
2. If the system uses a finite window `K` and `j >= K`, the request is rejected, diverted, or pushed into overtime.
3. If accepted, the patient is assigned an appointment slot; their future show-up probability is tied to the backlog they saw at booking time.
4. Service slots are processed at rate `mu` or every `1 / mu` time units.
5. At the appointment time:
   - with probability `p_j`, the patient shows and the slot creates full service reward
   - with probability `1 - p_j`, the patient is a no-show
6. A no-show slot is handled differently across papers:
   - Green and Savin: the slot is wasted, and the patient may reschedule with probability `r`
   - Liu and Liu-Ziya: the slot may still create partial value via walk-ins or ancillary tasks, captured by `xi`
7. Queue length changes, which changes future delays, which changes future show-up probabilities.

This is the main nonlinear feedback mechanism.

## Shared Structural Insight

All three papers use a stylized queue state to keep the model tractable, but the true system is richer than queue length alone.

In reality, a patient's no-show probability should depend on the delay they were promised at booking time, not only the queue length at service time. An exact Markov model would therefore need more state information, such as:

- the slot positions of booked patients
- how long each patient has already waited
- cancellation-created holes in the schedule
- patient preferences for later appointments

The papers intentionally compress this richer state into a smaller queueing model so they can derive structure and usable managerial rules.

## Model 1: Green and Savin (2008)

### Purpose

Determine what panel sizes are compatible with advanced access or same-day access in the presence of delay-dependent no-shows.

### Core Model

- Queue type: `M/D/1/K` and `M/M/1/K`
- Decision focus: panel size `N`
- Arrival rate: `lambda_0 * N`
- Service time: deterministic slot length `T` in the main model, exponential in the alternate model
- Finite queue capacity `K`
- If the system is full, the patient is lost to the provider

### No-show Dynamics

Green and Savin explicitly model no-show probability as increasing with backlog:

- `gamma(k) = gamma_max - (gamma_max - gamma_0) * exp(-k / C)`

where:

- `gamma_0` is the minimum no-show rate
- `gamma_max` is the saturation no-show rate
- `C` is backlog sensitivity

The key empirical shape is:

- nonzero no-show rate even for same-day appointments
- monotone increase with delay
- saturation at a maximum

### Important Modeling Choice

When a patient no-shows:

- the service slot is still consumed
- after that wasted slot, the patient may rejoin the queue with probability `r`

This is the strongest positive feedback mechanism across the three papers:

- backlog increases no-shows
- no-shows waste capacity
- some no-shows create new future demand through rescheduling
- future backlog rises again

### Main Dynamic Insight

This paper shows a tipping-point effect:

- for moderate panel sizes, backlog and access look manageable
- after a threshold, same-day access collapses quickly
- the collapse is sharper than in a model without no-shows

The reason is the feedback loop above.

### Operational Meaning

This model is best thought of as an access-feasibility model, not a throughput-maximization model.

It answers:

- how large can the panel be before backlog becomes inconsistent with short waits?

It does not answer:

- what panel size maximizes revenue or throughput?

### Key Findings

- No-shows can create the paradox of long patient waits and lower physician utilization at the same time.
- In their MRI-style example, physician utilization rises with backlog only up to a point, then falls because more slots are wasted.
- Sustainable panel size for same-day access is materially smaller once delay-dependent no-shows are included.
- Rescheduling probability `r` strongly reduces feasible panel size.

### Approximation Quality

- `M/D/1/K` tracks a no-preference simulation very closely.
- `M/M/1/K` is more conservative and can help bound performance in moderate no-show settings.
- When patient preferences for later appointments are added, the exact numbers move, but the core threshold behavior remains.

## Model 2: Liu (2015) Optimal Appointment Scheduling Window

### Purpose

Choose the optimal appointment scheduling window, represented by queue capacity `K`, when patient no-show behavior depends on delay.

### Core Model

- Queue type: analytical `M/M/1/K`, numerically checked against `M/D/1/K`
- Decision focus: scheduling-window size `K`
- Demand rate `lambda` and service rate `mu` are treated as fixed in the base problem
- A patient who sees `j` appointments ahead shows with probability `p_j`
- Rejected patients incur penalty `h`
- Empty or no-show slots may still generate value `xi` through ancillary tasks

The paper defines an effective value per scheduled slot:

- `q_j = p_j + (1 - p_j) * xi = xi + (1 - xi) * p_j`

So `q_j` is the probability or value that a scheduled slot is not wasted.

### Objective

Maximize long-run average net reward:

- reward from patients who show
- plus ancillary-task value from otherwise empty time
- minus rejection or overtime penalty for patients beyond the allowed window

### Main Trade-off

Large `K`:

- fewer rejected patients
- longer delays
- more no-shows

Small `K`:

- shorter delays
- higher show-up rates
- more rejected demand

This paper formalizes that trade-off directly.

### Structural Results

The reward function is quasi-concave in `K`, so the optimal window behaves like a weakly unimodal choice rather than a wildly irregular one.

Comparative statics:

- `K*` decreases as demand increases
- `K*` increases as service rate increases
- `K*` increases as rejection penalty `h` increases
- `K*` increases as ancillary value `xi` increases

### Most Important Insight

Pointwise improvement in show-up probabilities does not imply a larger optimal window.

What matters is whether patients become less sensitive to incremental delay.

The paper's sufficient condition says that if the drop in show-up probability from one additional delay increment becomes smaller under the new system, then the optimal window weakly increases.

Managerial interpretation:

- reminder systems or other interventions should not be evaluated only by average no-show reduction
- they should also be evaluated by whether they flatten the damage caused by extra waiting

### When Window Control Matters

This paper finds that optimizing `K` helps most when:

- demand is high
- other operational levers are unavailable

When panel size and overbooking are already optimized, window control adds little. In that setting, scheduling-window control acts mostly as a substitute for those levers, not a complement.

### Extension with Heterogeneous Patients

The paper also studies two patient types with possibly different show-up curves.

A robust ordering result emerges:

- if type 1 has higher show-up probability than type 2 at every backlog level, there exists an optimal policy with `K_1 >= K_2`

This is stronger than the homogeneous case because the provider can condition on patient type directly.

## Model 3: Liu and Ziya (2014) Panel Size and Overbooking

### Purpose

Choose:

- panel size, or equivalently appointment-request rate `lambda`
- service rate `mu`, interpreted as overbooking level

to maximize throughput or net reward under delay-dependent no-shows.

### Core Model Without Overbooking

- Queue type: analytical `M/M/1`, checked against `M/D/1`
- Decision focus: `lambda` for fixed `mu`
- Show-up probability decreases with queue length: `p_j`
- A no-show slot can still be filled by a walk-in with probability `xi`

The throughput-like reward can be written using:

- `q_j = p_j + (1 - p_j) * xi`

### Key Result Without Overbooking

For fixed `mu`, the long-run reward is strictly concave in `lambda`, so there is a unique optimal arrival rate and therefore a unique optimal panel size.

Important implications:

- the optimal panel does not necessarily saturate capacity
- even without an explicit service-level constraint, the best system can operate with `rho < 1` if delay sharply harms attendance
- walk-in probability `xi` has no effect on the optimal panel size when overbooking is not allowed

### Comparative Static for Better Show-up Behavior

As in the Liu scheduling-window paper, the direction of the panel-size change cannot be inferred from pointwise higher show-up probabilities alone.

The correct driver is again delay sensitivity:

- if a new intervention makes attendance less sensitive to incremental delay, optimal panel size increases
- otherwise panel size may rise or fall

### Overbooking Extension

The paper then chooses both `lambda` and `mu`.

Overbooking is modeled through a convex cost function `omega(mu)` with:

- regular capacity `M`
- no extra cost up to `M`
- increasing convex cost above `M`

Net reward:

- throughput from filled slots
- plus walk-in salvage
- minus overbooking cost

### Effective Utilization View

The paper rewrites throughput as:

- `T(lambda, mu) = mu * Lambda(rho)`

where `Lambda(rho)` is effective server utilization after accounting for no-shows and walk-in salvage.

This creates a clean economic interpretation:

- increase `mu` until marginal capacity cost equals effective revenue generation from extra capacity

### Main Structural Results with Overbooking

- If show-up probabilities improve pointwise, optimal `mu*` increases.
- Optimal `lambda*` is not guaranteed to increase.
- If show-up probabilities improve and also become less delay-sensitive, then `lambda*`, `mu*`, and `rho*` all increase.
- Relaxing the waiting-time target increases optimal traffic intensity `rho*`, but optimal `lambda*` and `mu*` can each move non-monotonically.
- When walk-in probability `xi` increases, optimal `lambda*`, `mu*`, and `rho*` all increase.

### Numerical and Simulation Findings

The analytical insights survive under:

- `M/D/1` service instead of `M/M/1`
- patient balking
- patient cancellation

with an important qualifier:

- in the simulation, cancellations did not reschedule, so higher cancellation reduced effective load and could increase the optimal panel size

That is directionally different from Green and Savin, where no-shows can re-enter the system and therefore amplify congestion.

### Comparison to Open Access

Using the same MRI-style no-show curve as Green and Savin:

- throughput-maximizing panel size is around 2459 to 2471
- Green and Savin's advanced-access-compatible estimates are lower, about 2205 to 2368

This difference is expected because:

- open access prioritizes short delay and same-day service
- throughput maximization tolerates longer delays
- Green and Savin assume rescheduling after no-show, which increases effective workload

## Cross-Paper Synthesis

### 1. All three papers optimize different levers in the same nonlinear system

- Green and Savin: optimize panel size under an access target
- Liu and Ziya: optimize panel size and overbooking
- Liu: optimize appointment-window length

### 2. Delay sensitivity is the dominant state-to-reward transmission mechanism

The optimization is driven not only by the level of `p_j`, but by the slope of `p_j` as backlog grows.

Why:

- all three problems ask whether one more unit of backlog is worth accepting
- the answer depends on how much that marginal backlog harms future attendance

### 3. The treatment of no-show slots changes the dynamics materially

Green and Savin:

- no-show consumes a slot
- may generate future demand through rescheduling
- strongest congestion feedback

Liu and Liu-Ziya:

- no-show can be partly salvaged through walk-ins or ancillary work
- no rescheduling in the base models
- weaker feedback from one missed appointment

### 4. Access optimization and throughput optimization lead to different "optimal" systems

Open access prefers:

- smaller panel
- shorter backlog
- lower same-day failure risk

Throughput or reward optimization can prefer:

- larger panel
- longer average delays
- lower same-day access

This is not a contradiction. It is a change in objective.

### 5. Window limits are mainly useful when other levers are constrained

If a clinic cannot:

- reduce panel size
- increase or change capacity
- overbook strategically

then a scheduling window is a powerful indirect way to control delay and no-shows.

If panel size and overbooking are already optimized, the marginal value of an additional window limit is small.

### 6. Positive feedback is the core risk

The most dangerous regime is:

- demand rises
- backlog grows
- show-up worsens
- effective capacity falls
- backlog grows faster

This creates sharp transitions rather than smooth deterioration.

## Reusable Mental Model

For future work, these papers can be unified into the following mental model:

- Demand pressure is controlled by panel size.
- Capacity pressure is controlled by service rate or overbooking.
- Delay pressure is controlled by the appointment window.
- No-show damage is controlled by the delay-sensitivity curve.
- Slot salvage is controlled by walk-ins, ancillary tasks, or preference flexibility.
- Congestion amplification is controlled by whether no-shows reschedule.

In a single sentence:

- panel size changes how much load enters the system
- overbooking changes how fast slots are processed
- window size changes how much delay is allowed to accumulate
- the no-show curve determines how dangerous each extra unit of delay becomes

## Guidance for Building Future Models or Simulations

If this literature is used as a base for a new model, the first design choice should be whether the objective is:

- access quality
- throughput
- net reward
- fairness across patient segments

The second design choice should be whether to include the following state enrichments:

- patient-specific promised delay at booking time
- cancellations and resulting holes
- patient preference for later appointments
- explicit rescheduling after no-show
- heterogeneous patient classes
- dynamic, state-dependent admission rules instead of static `N`, `mu`, or `K`

Minimal stylized state:

- queue length `j`

More realistic state:

- booked slots
- hole positions
- patient class mix
- age or promised delay of each booked appointment

## Bottom Line

The documents collectively support the following high-confidence conclusion:

- The operational problem is not "how do I reduce no-shows?"
- It is "how do I control a feedback system in which delay creates no-shows and no-shows reshape future delay?"

Across all three papers, the best decisions are determined less by average attendance and more by how delay-sensitive attendance is, combined with which levers the provider is actually allowed to move.
