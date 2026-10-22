# Data and API contract

Run commands from the project root. The raw schema is `sandpile-events-v2`.
Grids, events and counts use signed int64. The kernel interface converts source
indices to int64; compressed event chunks store them as int32 (all retained
experiments have at most 4,096 sites). No incomplete avalanche is stored as a
completed event. Matrix convention is Delta=-4I+B,
K=-Delta. All transfers are directional, with missing neighbours going to sinks.

## Run records

Each `data/<cohort>/<run>/metadata.json` contains model, L, seed, stream,
PCG64/SeedSequence entropy, burn and production grain budgets, initial state,
batch size, drive parameters, start/finish timestamps, completion status,
complete grain/event counts, measured kernel/wrapper and chunk-I/O time, and an
ordered list of chunk filenames, stages, counts and byte lengths.

The cohort's `simulation_sources.json` stores a copy of the files used to run
it. These are compared directly at resumption. Saved chunks are checked for
expected length and valid built-in NPZ CRCs. The result index stores file paths,
lengths, generating commands and report-number analysis keys.

`initial.npz` is the initial stable grid and generator state;
`production_start.npz` is the state after burn-in. `checkpoint.npz` holds stable
grid, stage, completed event count within stage, PCG64 JSON state and committed
chunk count. File replacement is atomic. Recovery rolls metadata back to that
checkpoint if interruption occurred between the chunk and checkpoint commits;
deterministic replay regenerates the uncommitted chunk. One writer per run is
required. Concurrent writers to the same output directory are unsupported.

Batch metadata points to its matched baseline directory. The complete ordered
future input sequence is read from those saved baseline chunks. Its own RNG
state is provenance scaffolding, not a second independent driving stream.

## Event chunk NPZ fields

| Array | Stored dtype | Shape / meaning |
|---|---|---|
| `events` | int64 | n x 6: S, A, D, ell, mass_after, min_source_boundary_distance |
| `sources` | int32 | n x m ordered flat site indices; repeated sites retained |
| `event_index` | int64 | n one-based event indices within this stage |
| `grains_per_event` | int64 | scalar m (one or four) |
| `frequencies` | int64 | k x 4 counts of heights 0,1,2,3 at stable checkpoints |
| `frequency_event` | int64 | k one-based event indices associated with frequencies |
| `grid_start`, `grid_end` | int64 | L x L stable chunk endpoints |

Site x maps to row `x // L`, column `x % L`, both zero-based. Event t corresponds
to m*t grains in its stage. Production checkpoints occur every 128 grains:
128 single-grain events or 32 batches. Stage is supplied by metadata and the
chunk filename; run ID, model/size/seed belong to the containing run. The arrays
do not repeat those constant fields millions of times.

S sums elementary topplings; A counts distinct toppled sites; D counts actual
sink transfers. Reach is zero when S=0, otherwise one plus the maximum over
toppled sites of distance to the nearest input source. Open distance is Manhattan;
cylinder distance wraps columns. The last column is the minimum source distance
to an open edge or, for the cylinder, to top/bottom only. Odometers are retained
in validation calls rather than for every production event.

## Python interfaces

- `Graph(rows, cols, boundary="open")` supports open rectangles and cylinders
  of width at least three. Geometry arrays are cached and read-only.
- `reference.stabilize(grid, graph, sources, schedule, rng)` and
  `engine.stabilize(grid, graph, sources)` return stable grid, per-site odometer,
  and a length-four int64 array [S,A,D,ell]. Sources are flat indices, with replacement. Inputs
  are copied. Random scheduling uses a separate caller-owned RNG.
- `fast.run(grid, graph, sources, ...)` accepts an n x m integer source
  matrix and returns stable grid, n x 6 event array, checkpoint frequencies and
  the last odometer. It checks every event's conservation bookkeeping using
  the recorded mass and sink loss. The C kernel independently checks actual
  grid mass through checkpoint histograms (every 128 input grains in production),
  and the wrapper sums the final grid at each chunk end. These checks do not
  independently rescan the actual grid after every production event. Single-event
  tests use stride=1; `tests/array_oracle.py` independently stabilizes via array
  shifts and checks actual array mass after every validation event.
  On safety failure it raises without changing the caller's grid.
- `experiment.run_chain(...)` runs or resumes a single configuration.
  `run_config(path)` applies a frozen JSON configuration.
- `experiment.read_events(path, stage="production")` reads only the named
  stage and concatenates the event/source/frequency arrays. Analysis first checks
  status, counts, archive integrity, balance and bounds.
- `statistics.discrete_fit` returns a parameter/diagnostic dictionary or an
  explicit sparse/optimizer-failure status. Only raw integer observations on
  inclusive finite support enter its likelihood. `histogram` returns observed
  integer support, normalized PMF and inclusive CCDF P(X>=x).

The exact function signatures and expected tuple order are documented in source.

## Derived evidence

- `summary.json`: all-event per-grain means and seed-level intervals;
  triggering, loss and zero masses; regular-checkpoint height frequencies.
- `benchmarks.json`: sparse predictions/residuals and potential-based bounds.
- `stationarity.json`, `acf.json`, `acf_*.npz`: four production windows and
  observable-specific dependence; ACF curves saved for the first seed per model/L.
- `distributions/*.npz`: exact PMFs/CCDFs conditional on S>0 (D=0 retained);
  positive-loss views are generated for figures. `binned_*.npz` uses count/bin-width display
  normalization. Observed maxima are distinct from fit/support bounds.
- `fits.json`: each L, observable, candidate and xmin factor; per-seed parameters,
  retained counts, intervals, convergence, KS and contiguous-block score sensitivity.
- `correlations.json`, `boundary.json`: all six correlations separately by L
  and loss probabilities stratified by fixed source distance and size bands.
- `coupling.json`: every batch S/D/mass equality, checkpoint/frequency agreement,
  and exact area-overlap summaries. Per-site identities also have independent tests.
- `ensemble_raw.json`, `ensemble.json`: independent chain snapshots and comparison
  with one time series, including block-length/bootstrap sensitivity.
- `extensions.json`: independent Welch contrasts. Batch rows are not treated as
  independent samples in this comparison.
- `confirmation.json`: separately configured longer follow-up of the primary
  height contrast; never substituted for or pooled into primary estimates.

All primary intervals use five independent seeds, not events or lattice sites
as independent replicates. Block intervals are finite dependence diagnostics;
no exact mixing or calibrated IID power-law test is inferred.
