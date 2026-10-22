# COMP90072 sandpile experiments

This package contains the code for the baseline study and three comparisons:
spatially biased input, a cylinder with open top and bottom boundaries, and
four-grain batches matched to sequential single-grain additions. It includes
the pilot, production runs, independent ensemble, longer confirmation runs,
statistical analysis, figures, tables and report sources.

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
their arrays and checks fitting and plotting. It does not require LaTeX.

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
| `figures`, `tables` | Figures, LaTeX tables, CSV values and numerical macros | `report/generated/` |

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
from stable checkpoints. Editing a simulation source file, including its comments
or formatting, changes the stored source fingerprint. Use a fresh output
directory after such an edit. Do not copy the original archive's checkpoints
into this reformatted version. Its event-generation rules are unchanged, but
its source fingerprint is intentionally different.

## How the files fit together

| File | Read it for |
| --- | --- |
| `sandpile/model.py` | Lattice neighbours, sinks, distances, driving probabilities and sparse benchmarks |
| `sandpile/reference.py` | The simplest implementation: one legal toppling per scan |
| `sandpile/engine.py` | A readable Python queue using consecutive legal topplings |
| `sandpile/kernel.c` | The same active-site approach implemented for long runs |
| `sandpile/fast.py` | Validated NumPy/C interface and local C compilation |
| `sandpile/experiment.py` | Random streams, burn-in, measured events, paired batches and resumption |
| `sandpile/io.py` | Atomic file writes, hashes and environment records |
| `sandpile/statistics.py` | Seed intervals, ACFs and normalized discrete likelihoods |
| `sandpile/analysis.py` | Measurement checks and the statistical comparisons |
| `sandpile/plots.py`, `report_artifacts.py` | Figure and table generation from saved results |
| `scripts/` | Individual experiment and build entry points |
| `tests/` | Independent checks, including an array-shift oracle |
| `examples/` | Small calculations and a reader for saved events |

Read `docs/code_guide.md` for the queue and checkpoint logic, and
`docs/data_schema.md` for array columns, units and conditioning. Conventional
symbols such as `h`, `u`, `S` and `D` follow the report: heights, per-site
topplings, total topplings and boundary loss. The C kernel uses longer names
where the extra context helps follow its loop.

## Figures and the report

The default workflow creates figures and tables without a TeX installation.
To compile the supplied report source as well:

```bash
python run_project.py all --pdf
```

Or, after the data and generated files exist:

```bash
python scripts/build_report.py --tectonic /absolute/path/to/tectonic
```

PDF compilation requires Tectonic 0.17.0 and `pdfinfo` on PATH. Tectonic may
need network access to fetch fonts on its first run. The build checks references,
missing characters, overflow and the 20-page physical limit. New measurements,
especially timings, can change line breaks; inspect the newly compiled PDF.
`report/LICENSE` preserves the teacher template's licence.

`reference_results/` contains the retained statistical summaries, benchmark,
production timing and numerical source map for comparison. Their timings belong
to the original execution. Fresh calls write their own timings under `logs/`,
and the table generator uses those new measurements. The numerical source map
lists each original displayed value and its analysis key. The PDF and large raw
event records are supplied separately in the full project; this is a code package.

## Reproducibility

The numerical code is reformatted and annotated for this handoff. The Python
syntax trees are compared after excluding docstrings, and the C loop is checked
after local-variable renaming. Frozen configuration files are copied unchanged.
`reference_results/readability_check.json` records this comparison. The workflow
wrapper, examples and optional PDF switch are new conveniences.

For a generated run, event data, input coordinates and height checkpoints are
integer arrays. Metadata stores the generator state and hashes of complete
chunks. The analysis checks raw hashes, mass conservation and a finite-window
potential identity before using those events. Timing measurements are separate
from the integer reproducibility checks.

After generating results, verify their snapshot with:

```bash
python scripts/manifest.py --verify
```

The package's own `FILES.sha256` lists the delivered files. `docs/validation.md`
records the commands actually run on this edition. Finite grid sizes, five
primary seeds and range-dependent marginal fits still limit the conclusions;
cleaner code does not change those limits.

To rebuild this source ZIP after editing it:

```bash
python tools/package_code.py . --output ../COMP90072_Experiment_Code.zip
```
