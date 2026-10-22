# Checks run on this code edition

Validated on 22 October 2026 using Python 3.12.2 and the pinned dependencies,
with a C11 compiler on arm64 macOS. The code ZIP was extracted into a new
folder before the experimental workflow ran. Original raw data were not copied
into that folder.

Commands executed:

```bash
python run_project.py smoke
python run_project.py all
python run_project.py tables
python run_project.py production
```

The smoke ran eight model/seed combinations twice in fresh temporary folders.
All event arrays and sampled height counts agreed. Statistics, fitting and
plotting passed; its optional PDF step was skipped. The unit suite ran all
22 test methods successfully.

The full workflow completed 11 pilot/control chains, 50 primary runs, 100
independent ensemble chains and 20 confirmation runs. Analysis, sensitivity,
figures, tables and manifest verification all passed. The latest workspace
formatter for narrow confidence intervals was then synchronized and the table
generation rerun. Rechecking completed primary runs left their measured
production timing unchanged.

Comparison with the original retained experiments found:

- 4,765 event chunks identical by SHA-256.
- 543 initial-state, production-start and checkpoint files identical.
- All ten checked statistical JSON files identical, including fits, correlations,
  coupling, ensemble estimates, dependence and range sensitivity.
- All 11 plot files identical.
- 493 of 499 generated macro values identical. The six changes are new measured
  kernel, I/O, wall, compilation, warm-up and queue-speed timings.

The readable Python numerical modules, tests and original scripts have the same
syntax trees after excluding docstrings. The C main loop has the same tokens
after local identifier changes. The new workflow, examples and optional smoke
PDF flag are tested separately. The frozen JSON configurations are unchanged.

`reference_results/code_package_validation.json` records the commands and
measured stage times. `fresh_run_comparison.json` records the comparison counts;
`readability_check.json` lists the source-equivalence checks. Test and smoke
outputs are included alongside these records. The completed-run check output
is retained separately from the original workflow's production measurement.

PDF compilation was not rerun as part of this code handoff. Report sources are
included; the existing report PDF remains a separate deliverable. To compile
using new measurements, install the optional PDF tools and use the README command.
The core and statistical checks were run on this host; other platforms remain
untested.
