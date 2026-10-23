# Verification

Run from the package root:

```bash
python run_project.py check
python run_project.py smoke
python run_project.py all
python scripts/manifest.py --verify
```

`check` tests the local rules, independent implementations, recurrent-state
invariance, cylinder geometry, biased driving, matched batches, statistical
routines and exact restart behaviour. The 24 tests include changed-source
rejection and damaged-NPZ detection.

`smoke` runs all four models twice using fresh temporary outputs. It checks
identical arrays, statistical summaries, a discrete fit and a Matplotlib plot.
It does not use saved primary data.

`all` runs the experiment stages and analyses in dependency order, exports PNG,
CSV and JSON results, then creates and verifies `analysis/results_index.json`.
Completed compatible chains are reused; interrupted chains resume from stable
checkpoints. Per-stage output is in `logs/workflow_*.txt` and invocation records
are in `logs/workflow.json`.

The recorded environment is Python 3.12.2 with pinned dependencies and a C11
compiler on arm64 macOS. Other operating systems have not been tested.
`reference_results/validation.json` records the executed release checks and
comparison with the retained experiment results.

## Executed release check: 23 October 2026

The 24-test suite and the complete workflow passed in a fresh code directory
using copies of 181 completed compatible experiment runs. Simulation stages
reused those completed chains. Analysis, sensitivity, plotting, CSV/JSON export
and result indexing were executed again. The fresh two-execution smoke also
passed independently of those saved runs.

All 4,765 event chunks and 543 initial/start/checkpoint files remain identical.
The statistical results and all eleven PNGs agree with the preceding validated
execution; comparison of confirmation results excludes its new execution time
and timestamp. The full-precision summary CSV also matches. Formatted numerical
values agree apart from newly measured benchmark times. The CSV exports have
consistent columns and all numerical values retain their analysis source keys.
