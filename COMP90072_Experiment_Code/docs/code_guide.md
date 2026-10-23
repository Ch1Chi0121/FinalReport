# Reading the implementation

## One avalanche

Start with `examples/single_avalanche.py`, then read `reference.stabilize`.
The reference scans the grid, chooses an unstable site, removes four grains
and transfers one in each axial direction. Missing neighbours are sinks. The
odometer `u` records each elementary toppling. The returned `S`, `A`, `D` and
reach are calculated from that odometer.

`engine.stabilize` visits only active sites. At a site of height h, it performs
h // 4 consecutive legal topplings. The remainder is below four, and each
neighbour receives h // 4 grains. Neighbours that become unstable enter the
queue. A Boolean flag prevents duplicate pending entries. A site can return
to the queue later when another neighbour sends it more grains.

Bulk toppling follows the finite-graph stabilization theorem. The reference and queue still produce the same final grid and
complete odometer. Their independent scheduling is useful for detecting errors.

## What the C kernel adds

`kernel.c` uses the same queue idea, with a circular array and one spare slot.
A per-site event stamp avoids clearing the whole odometer for every avalanche.
The first visit in an event resets that site's count and increases the area;
further visits only add topplings. Reach is updated on the first visit too,
since it depends on which sites toppled, rather than how often they toppled.

For batches, each site is measured from its nearest input source. Cylinder
reach wraps horizontally. The neighbour table already encodes wraps and sink
links, so the transfer loop uses the same four directions for both graphs.

`fast.run` copies and validates inputs before calling C. If the kernel fails,
the caller's stable grid is unchanged. Event balance uses recorded input and
loss. Stable-height histograms independently rescan actual mass at checkpoints,
and the wrapper sums the grid at the end of every chunk. The tests use an
independent array-shift oracle to check actual mass after every validation event.

## Events, grains and checkpoints

A single-grain event adds one grain; a batch event adds four. Budgets and
checkpoint spacing in the JSON files count grains. `run_chain` converts these
to event counts at the boundary of the execution loop. Thus a 128-grain
checkpoint interval means 128 baseline events or 32 batch events.

Each completed chunk is written before its metadata, and metadata is written
before the checkpoint. The checkpoint's committed-chunk count is authoritative.
If a process stops after metadata replacement but before checkpoint replacement,
resumption discards that uncommitted metadata entry and deterministically
replays the chunk from the saved grid and PCG64 state. The interruption test
injects a failure at precisely this point. One process must own each run folder.

A matched batch run starts from its baseline's post-burn grid. It reads the
baseline's next four source coordinates, preserving repeats, and adds them
before relaxing. Every chunk checks grouped sequential S and D against the
batch values, together with mass and chunk-end grids. Area is a union of
visited sites, so adding four sequential areas can overcount shared sites.

## Statistical units

The primary confidence intervals use one estimate per independent seed. A
million successive events are not treated as a million independent replicates.
The time/ensemble comparison has a separate blocked time estimate and one
state per independent ensemble chain. Main avalanche distributions condition
on S > 0 and retain D = 0. Positive-loss fitting conditions on D > 0.

Discrete fits normalize over every integer in the chosen inclusive support.
The plotted bins are displays of data, not observations used by the optimizer.
The cutoff likelihood is optimized from several starts, then checked using a
projected gradient. KS distances and in-sample score differences are descriptive;
the code does not turn them into IID goodness-of-fit p-values.

## Changing an experiment

Use the frozen files under `configs/` to reproduce the submitted design. To
explore another choice, copy a config and change its output directory as well
as the parameter. A one-off production config can be passed directly to
`python -m sandpile.experiment path/to/config.json`.

The analysis and summary tables are written for this project's selected sizes,
models and fitting ranges. Changing those choices may require adapting the
analysis or table selection. Run the small tests before starting a new cohort.
