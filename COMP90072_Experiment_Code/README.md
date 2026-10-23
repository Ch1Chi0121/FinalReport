# COMP90072 sandpile experiments

This package contains the code for the baseline study and three comparisons:
spatially biased input, a cylinder with open top and bottom boundaries, and
four-grain batches matched to sequential single-grain additions. It includes
the pilot, production runs, independent ensemble, longer confirmation runs,
statistical analysis, figures and tables.

Start with the small examples if you want to understand the implementation.
Use `run_project.py` to run the experimental stages in order. The original raw
event files are kept in the full project archive; this package generates its
own data. Saved results under `reference_results/` are supplied for comparison.
They are never read as new simulation output.

## Install

Python 3.12.2 was used with the versions in `requirements.lock.txt`. A C11
compiler named `cc` is needed for the fast implementation. Python runs the
experiments and analysis; the C function performs the topplings.

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m pip check
```

On Windows, virtual-environment activation and the shared-library build need
adapting. This release was tested on arm64 macOS; it has not been tested on
Windows or Linux. The C library is built locally on first use, so no compiled
binary is distributed.

## Start small

```bash
python examples/single_avalanche.py
python examples/compare_batch.py
python run_project.py check
python run_project.py smoke
```

The first example reproduces the corrected handout calculation with the
reference scan, Python queue and C queue. The second compares the same four
input sites added together and one at a time. The test command checks local
rules, boundaries, batching, statistical routines and exact restart behaviour.
The smoke command runs all four models twice in temporary directories, compares
their arrays and checks fitting and plotting.

## Run the experiments

```bash
python run_project.py all
```

This runs tests, the timing benchmark, pilot, primary simulations, independent
ensemble, confirmation, analysis, fit-range sensitivity, figures, tables and a
file manifest. It stops on a failed command. Each stage has a text log under
`logs/` with its latest output. `logs/workflow.json` retains the commands and
elapsed times from every invocation.

| Stage | Design | Main output |
| --- | --- | --- |
| `pilot` | L=64, three initial states for each single-grain model; matched batch control | `data/pilot_v1/`, `analysis/pilot.json` |
| `production` | Baseline L=8,16,32,64; extensions L=32,64; five seeds; 200,000 measured grains per run | `data/full_v1/` |
| `ensemble` | 100 independent L=32 chains observed at five input ages | `data/ensemble_v1/`, `analysis/ensemble_raw.json` |
| `confirmation` | Uniform and biased L=32,64; five new seeds; 800,000 measured grains per run | `data/confirmation_v1/`, `analysis/confirmation.json` |
| `analysis` | Per-seed summaries, dependence, distributions, fits and coupled comparisons | `analysis/` |
| `sensitivity` | Three upper fitting limits on the same five L=64 baseline runs | `analysis/upper_limit_sensitivity.json` |
| `figures`, `tables` | PNG figures, CSV tables and JSON values | `results/` |

The primary design has 50 runs and 10 million measured grains. Batch runs reuse
baseline inputs, so their two million grains are paired comparisons. The
confirmation has 20 separate runs and 16 million measured grains; it remains
separate from the primary summaries. Parameters and random streams are in
`configs/`. Raw files can occupy much more space than this source package.

A single stage can be run directly:

```bash
python run_project.py production
python run_project.py analysis
python run_project.py figures
python examples/inspect_run.py data/full_v1/baseline_L8_s21001
```

Run `ensemble` before `analysis`. Plotting needs the pilot, primary analysis and
ensemble outputs; numerical tables also need the confirmation and sensitivity
results. Running `all` handles these dependencies.

Simulation stages reuse completed compatible runs and resume interrupted runs
from stable checkpoints. Each cohort keeps one readable copy of its simulation
sources in `simulation_sources.json`. Resumption compares those copies with the
current files. Use a fresh output directory after editing simulation sources.
This edition uses the v2 data format; do not mix it with older checkpoints.

## How the files fit together

| File | Read it for |
| --- | --- |
| `sandpile/model.py` | Lattice neighbours, sinks, distances, driving probabilities and sparse benchmarks |
| `sandpile/reference.py` | The simplest implementation: one legal toppling per scan |
| `sandpile/engine.py` | A readable Python queue using consecutive legal topplings |
| `sandpile/kernel.c` | The same active-site approach implemented for long runs |
| `sandpile/fast.py` | Validated NumPy/C interface and local C compilation |
| `sandpile/experiment.py` | Random streams, burn-in, measured events, paired batches and resumption |
| `sandpile/io.py` | Atomic files, source copies and NPZ checks |
| `sandpile/statistics.py` | Seed intervals, ACFs and normalized discrete likelihoods |
| `sandpile/analysis.py` | Measurement checks and the statistical comparisons |
| `sandpile/plots.py`, `tables.py` | Figure and table generation from saved results |
| `scripts/` | Individual experiment entry points |
| `tests/` | Independent checks, including an array-shift oracle |
| `examples/` | Small calculations and a reader for saved events |

Read `docs/code_guide.md` for the queue and checkpoint logic, and
`docs/data_schema.md` for array columns, units and conditioning. Conventional
symbols such as `h`, `u`, `S` and `D` denote heights, per-site
topplings, total topplings and boundary loss. The C kernel uses longer names
where the extra context helps follow its loop.

## Figures and tables

After the experiment and analysis stages, regenerate figures and tables with:

```bash
python run_project.py figures
python run_project.py tables
```

PNG figures are written to `results/figures/`. CSV tables, formatted values
and their source map are written to `results/tables/`. Running `all` includes
both stages.

`reference_results/` contains the retained statistical summaries, benchmark,
production timing and numerical source map for comparison. Their timings belong
to the original execution. Fresh calls write their own timings under `logs/`,
and the table generator uses those new measurements. The numerical source map
lists each generated numerical value and its analysis key. The original raw event
records are kept separately; running the experiments generates a new data set.

## Reproducibility

The numerical rules and frozen configurations are unchanged. This edition uses
simple file checks: saved source copies, chunk byte counts and the NPZ format's
built-in CRCs. The C library is rebuilt when its saved source copy differs.
The original execution snapshot remains in the full project.

Event data, input coordinates and height checkpoints are integer arrays. The
analysis checks completed budgets, archive integrity, mass conservation and a
finite-window potential identity. Tests compare independent implementations,
batching and interrupted/restarted runs. File checks detect ordinary damage;
they do not certify that nobody deliberately edited the data.

`analysis/results_index.json` lists input paths, file lengths, generation
commands and analysis keys for generated numerical values. Check it with:

```bash
python scripts/manifest.py --verify
```

`FILES.txt` lists the delivered files. `docs/validation.md` records the checks
run on this edition. Finite grids, five primary seeds and range-dependent fits
still limit scientific interpretation.

