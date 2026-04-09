# Project Journal

## Purpose

This is the running project journal for the appointment-simulation work.

Going forward, after each completed task I should:

- evaluate what remains to do
- update this journal if the task changes project status, assumptions, or priorities
- make a git commit for the completed work

## Current State

As of 2026-04-08, the project includes:

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
- daily pre-appointment cancellation described by `\phi_i(\tau)`
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

1. The metrics section now matches the implemented simulator distinction between `balked`, `no_offer`, and `not_booked`.
2. The note now has a clearer front-end reader guide and a more hierarchical section structure.
3. A possible remaining document-level improvement would be to decide whether the formulation note should stay purely technical or absorb a compact scope/status section for supervisor-facing use.

## Most Recent Completed Task

- Rebuilt [behavior_functions.ipynb](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Notebooks/behavior_functions.ipynb) as a note-aligned model notebook, with explicit sections for the core objects `t`, `Y_t(r,m)`, `X_{i,r}^D`, `\tau`, and the three behavior families.
- Rebuilt [simulation.ipynb](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Notebooks/simulation.ipynb) as a clean FCFS results notebook with a baseline run, a day-start state snapshot, baseline plots, and a total-`lambda` sensitivity sweep.
- Added [presets.py](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/appointment_simulation/presets.py) to keep the notebooks simple: it exposes two realistic options for balking, cancellation, and no-show behavior for both classes, plus compact helpers for building the two-class scenario and displaying the selected setup.
- Extended [test_simulation.py](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/tests/test_simulation.py) so the note-aligned presets and notebook-facing summary helpers are covered by automated tests.
- Executed both notebooks end to end with `nbconvert` and re-ran the full test suite successfully.
- Increased the effective cell height in the colored calendar tables of [first_two_class_simulation_note.tex](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.tex) by combining a larger `\arraystretch`, a small `\extrarowheight`, and a dedicated `\calendarentry{...}` strut macro.
- Recompiled [first_two_class_simulation_note.pdf](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.pdf) to check that the table contents no longer sit too tightly against the colored cell borders.
- Removed paragraph indentation in [first_two_class_simulation_note.tex](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.tex) and switched the note to a small positive paragraph spacing so blocks of text remain visually distinguishable without the traditional first-line indent.
- Recompiled [first_two_class_simulation_note.pdf](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.pdf) after the paragraph-style change to confirm the note still reads cleanly.
- Standardized bullet and numbered-list indentation in [first_two_class_simulation_note.tex](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.tex) with global `enumitem` settings so the visual alignment is now consistent across callout boxes, numbered steps, and references.
- Removed a few local `leftmargin=*` overrides that were creating uneven list offsets in different parts of the note.
- Recompiled [first_two_class_simulation_note.pdf](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.pdf) after the list-formatting cleanup. The remaining LaTeX warning is still the minor calendar-table layout warning, not a list-formatting issue.
- Reordered [first_two_class_simulation_note.tex](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.tex) so it now reads as a standalone starting point for the first simulation: model at a glance, core formulation, dynamics, worked example, performance measures, literature positioning, and implementation notes.
- Added a front-end `Model at a Glance` summary and compressed the old notation critique into a shorter `Notation Choice` subsection.
- Moved the example material into a single dedicated `Worked Example` section and combined the calendar view, the detailed state `Y_t(r,m)`, the derived state `X_{i,r}^{D}`, and the booking-decision interpretation in one place.
- Split the former mixed literature/code section into [Relation to the Literature](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.tex) and [Implementation Notes and Current Limits](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.tex).
- Renamed the measures block so it now reads simply as `Performance Measures`, with a short operational interpretation paragraph instead of a broader title that the section did not fully support.
- Recompiled [first_two_class_simulation_note.pdf](/Users/alexandresepulvedadedietrich/Documents/School/Columbia/Research/Documents/generated_notes/first_two_class_simulation_note.pdf) after the structural reordering. A small LaTeX layout warning remains in the generic schematic calendar example, but the document compiles correctly.

## Updated Task Assessment

1. Add explicit overbooking logic and its metrics.
2. Add reminder / confirmation interventions as parameterized behavior changes.
3. Add a payer-mix and margin layer for financial analysis.
4. Introduce a cleaner mapping from panel size `N` to the total arrival rate `\lambda` and class mix `p`, or equivalently to class-specific rates `\lambda_i`.
5. Calibrate assumptions once scheduling-process details and Columbia Doctors data are available.
