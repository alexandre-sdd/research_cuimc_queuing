# Project Journal

## Purpose

This is the running project journal for the appointment-simulation work.

Going forward, after each completed task I should:

- evaluate what remains to do
- update this journal if the task changes project status, assumptions, or priorities
- make a git commit for the completed work

## Current State

As of 2026-04-07, the project includes:

- a reusable simulation package in [appointment_simulation](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/appointment_simulation)
- a formal note in [first_two_class_simulation_note.tex](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.tex)
- a compiled PDF in [first_two_class_simulation_note.pdf](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.pdf)
- a literature synthesis in [knowledge_appointment_dynamics.md](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/knowledge_appointment_dynamics.md)
- a status memo in [simulation_status_and_next_steps.md](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/simulation_status_and_next_steps.md)
- a behavior-only notebook in [behavior_functions.ipynb](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Notebooks/behavior_functions.ipynb)
- a FCFS-only simulation-results notebook in [simulation.ipynb](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Notebooks/simulation.ipynb)
- a policy-comparison notebook in [policy_comparisons.ipynb](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Notebooks/policy_comparisons.ipynb)

## Implemented Model Features

- two patient classes
- rolling 15-day horizon and 25 slots per day by default
- slot-level calendar simulation
- offered delay `\tau` separated from residual-delay state `r`
- delay-sensitive balking
- delay-sensitive no-show
- explicit pre-appointment cancellation
- FCFS policy
- latest-available policy
- reserved-capacity policy
- class-specific booking-window policy
- aggregate summaries, class summaries, and daily journals
- access-target reporting and utilization reporting

## Immediate Next Tasks

These are the highest-priority next steps based on the current scope.

1. Add explicit overbooking logic and its metrics.
2. Add reminder / confirmation interventions as parameterized behavior changes.
3. Add a payer-mix and margin layer for financial analysis.
4. Introduce a cleaner mapping from panel size `N` to the total arrival rate `\lambda` and class mix `p`, or equivalently to class-specific rates `\lambda_i`.
5. Calibrate assumptions once scheduling-process details and Columbia Doctors data are available.

## Document Review Follow-Up

The standalone review of the initial formulation note identified three document-level follow-ups:

1. Update the metrics section so it matches the implemented simulator distinction between `balked`, `no_offer`, and `not_booked`.
2. Add a short front-end reader guide or abstract that states clearly what the note is, what it is not, and who should read which sections.
3. Add an explicit scope/status section so a supervisor can immediately see what is already in the simulator versus what remains future work.

## Most Recent Completed Task

- Added a worked example to [first_two_class_simulation_note.tex](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.tex) to make the modeling objects `Y_t(r,m)` and `X_{i,r}^D` concrete.
- The example now shows one small calendar snapshot, the induced day-start counts, and the way one patient's residual delay `r` changes over time while the behavioral delay `\tau` remains fixed.
- This improves the note's readability for both contributors and supervisors without changing the simulator logic or current task priorities.
- Recompiled [first_two_class_simulation_note.pdf](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.pdf) successfully after the documentation change.

Commit:

- to be recorded in git history for the Y/X worked example update
