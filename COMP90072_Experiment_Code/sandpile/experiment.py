"""Checkpointed event execution. No analysis or figure generation happens here."""
import json
from pathlib import Path
import time
import numpy as np
from . import fast
from .model import Graph, driving
from .io import atomic_json, atomic_npz, core_hash, now, sha256

MODEL_ID = {"baseline": 0, "biased": 1, "cylinder": 2, "batch": 3}


def read_events(path, stage="production"):
    """Concatenate retained complete chunks in event order, without re-simulating."""
    path = Path(path)
    meta = json.loads((path / "metadata.json").read_text())
    selected = [x for x in meta["chunks"] if x["stage"] == stage]
    if not selected:
        raise ValueError(f"No {stage} data at {path}")
    arrays = {k: [] for k in ["events", "sources", "frequency_event", "frequencies"]}
    for entry in selected:
        with np.load(path / entry["file"]) as data:
            for k in arrays:
                arrays[k].append(data[k])
    return {k: np.concatenate(v, axis=0) for k, v in arrays.items()}


def run_chain(
    path,
    *,
    L,
    model,
    seed,
    burn_grains,
    production_grains,
    chunk_grains=8192,
    sample_grains=128,
    initial="empty",
    stream=210,
    stop_after_chunks=None,
    matched_path=None,
):
    """Run a chain, or resume it from its last committed stable state.

    L, model, seed and stream identify the experiment. All budget arguments count
    grains; the internal done counter counts events in the current stage. With four
    grains per batch, the conversion is therefore done * 4.

    The stages are burn, production and complete. Each committed chunk contains
    whole avalanches, its stable endpoints and all input sites. The checkpoint also
    holds the PCG64 state, which restores future inputs exactly after interruption.

    For a batch control, matched_path points to a completed baseline. Its burn-end
    grid and saved production inputs are reused. No separate batch burn-in or new
    input stream is introduced. stop_after_chunks is used by restart tests.
    Returns the run metadata; a completed compatible run is reused.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    graph = Graph(L, L, "cylinder" if model == "cylinder" else "open")
    m = 4 if model == "batch" else 1
    eta = 0.9 if model == "biased" else 0
    if any(
        v % m for v in [burn_grains, production_grains, chunk_grains, sample_grains]
    ):
        raise ValueError("Grain clocks must be divisible by batch magnitude")
    if model == "batch" and (matched_path is None or burn_grains):
        raise ValueError("Batch requires matched baseline and no separate burn-in")
    config = dict(
        L=L,
        model=model,
        seed=seed,
        burn_grains=burn_grains,
        production_grains=production_grains,
        chunk_grains=chunk_grains,
        sample_grains=sample_grains,
        initial=initial,
        stream=stream,
        matched_path=str(matched_path) if matched_path else None,
    )
    metadata_path = path / "metadata.json"
    checkpoint_path = path / "checkpoint.npz"
    rng = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([stream, seed, L, MODEL_ID[model]]))
    )
    paired_chunks = []
    if matched_path:
        matched_path = Path(matched_path)
        parent = json.loads((matched_path / "metadata.json").read_text())
        if parent["status"] != "complete":
            raise ValueError("Matched baseline incomplete")
        paired_chunks = [x for x in parent["chunks"] if x["stage"] == "production"]
    # Resume only the exact configuration and source version stored with this run.
    if checkpoint_path.exists():
        meta = json.loads(metadata_path.read_text())
        if meta["config"] != config or meta["core_hash"] != core_hash():
            raise ValueError("Refusing incompatible checkpoint; use a new data version")
        if meta["status"] == "complete":
            return meta
        with np.load(checkpoint_path) as checkpoint:
            h = checkpoint["grid"].copy()
            stage = str(checkpoint["stage"])
            done = int(checkpoint["done"])
            rng.bit_generator.state = json.loads(str(checkpoint["rng"]))
            committed = int(checkpoint["committed"])
        # Metadata commit precedes checkpoint; recover any uncommitted chunk.
        meta["chunks"] = meta["chunks"][:committed]
    else:
        if matched_path:
            with np.load(matched_path / "production_start.npz") as data:
                h = data["grid"].copy()
        elif initial == "empty":
            h = np.zeros((L, L), dtype=np.int64)
        elif initial == "three":
            h = np.full((L, L), 3, dtype=np.int64)
        elif initial == "random":
            h = np.random.default_rng(
                np.random.SeedSequence([stream + 1, seed, L])
            ).integers(4, size=(L, L))
        else:
            raise ValueError("Unknown initial state")
        stage = "burn" if burn_grains else "production"
        done = 0
        meta = {
            "schema": "sandpile-events-v1",
            "config": config,
            "core_hash": core_hash(),
            "status": "running",
            "started_utc": now(),
            "rng": "PCG64/SeedSequence",
            "rng_entropy": [stream, seed, L, MODEL_ID[model]],
            "m": m,
            "eta": eta,
            "sigma": L / 8,
            "event_columns": [
                "S",
                "A",
                "D",
                "ell",
                "mass_after",
                "min_source_boundary_distance",
            ],
            "source_encoding": "flat row-major; full ordered list including duplicates",
            "chunks": [],
            "simulation_seconds": 0.0,
            "io_seconds": 0.0,
            "coupled_control": bool(matched_path),
        }
        atomic_npz(
            path / "initial.npz", grid=h, rng=json.dumps(rng.bit_generator.state)
        )
        if stage == "production":
            atomic_npz(
                path / "production_start.npz",
                grid=h,
                rng=json.dumps(rng.bit_generator.state),
            )
        atomic_json(metadata_path, meta)
        atomic_npz(
            checkpoint_path,
            grid=h,
            stage=stage,
            done=done,
            rng=json.dumps(rng.bit_generator.state),
            committed=0,
        )
    q = driving(graph, eta)
    chunks_this_call = 0
    # done resets at the burn/production boundary; RNG state continues.
    while True:
        target = (burn_grains if stage == "burn" else production_grains) // m
        if done == target:
            if stage == "burn":
                stage = "production"
                done = 0
                atomic_npz(
                    path / "production_start.npz",
                    grid=h,
                    rng=json.dumps(rng.bit_generator.state),
                )
                atomic_npz(
                    checkpoint_path,
                    grid=h,
                    stage=stage,
                    done=done,
                    rng=json.dumps(rng.bit_generator.state),
                    committed=len(meta["chunks"]),
                )
                continue
            meta["status"] = "complete"
            meta["finished_utc"] = now()
            meta["completed_production_events"] = done
            meta["completed_production_grains"] = done * m
            meta["completed_burn_grains"] = burn_grains
            atomic_json(metadata_path, meta)
            return meta
        count = min(chunk_grains // m, target - done)
        # Each group of four saved baseline inputs is one batch event.
        if matched_path:
            chunk_no = done * m // chunk_grains
            with np.load(matched_path / paired_chunks[chunk_no]["file"]) as data:
                sources = data["sources"].reshape(-1, m).copy()
                paired = data["events"]
                expected_grid = data["grid_end"].copy()
            if len(sources) != count:
                raise ValueError("Mismatched chunk grain budget")
        elif eta:
            sources = rng.choice(graph.n, size=(count, m), p=q)
        else:
            sources = rng.integers(graph.n, size=(count, m), dtype=np.int64)
        started = time.perf_counter()
        try:
            new_grid, events, freq, _ = fast.run(
                h, graph, sources, offset=done, stride=sample_grains // m
            )
        except Exception as exc:
            atomic_json(
                path / "failure.json",
                {
                    "stage": stage,
                    "done": done,
                    "error": repr(exc),
                    "resume": "rerun identical run_chain call",
                },
            )
            raise
        meta["simulation_seconds"] += time.perf_counter() - started
        if matched_path:
            if not np.array_equal(
                events[:, 0], paired[:, 0].reshape(-1, m).sum(axis=1)
            ):
                raise ArithmeticError("Batch S differs from grouped sequential S")
            if not np.array_equal(
                events[:, 2], paired[:, 2].reshape(-1, m).sum(axis=1)
            ):
                raise ArithmeticError("Batch D differs from grouped sequential D")
            if not np.array_equal(
                events[:, 4], paired[m - 1 :: m, 4]
            ) or not np.array_equal(new_grid, expected_grid):
                raise ArithmeticError("Batch/sequential stable states differ")
        started = time.perf_counter()
        # Commit data, then metadata, then checkpoint. Recovery trusts the last
        # checkpoint count if a process stopped between the final two writes.
        name = f"{stage}_{done:09d}.npz"
        stride = sample_grains // m
        checkpoints = np.arange((done // stride + 1) * stride, done + count + 1, stride)
        atomic_npz(
            path / name,
            events=events,
            sources=sources.astype(np.int32),
            frequency_event=checkpoints,
            frequencies=freq,
            grid_start=h,
            grid_end=new_grid,
            event_index=np.arange(done + 1, done + count + 1),
            grains_per_event=m,
        )
        meta["chunks"].append(
            {
                "file": name,
                "sha256": sha256(path / name),
                "stage": stage,
                "event_start": done + 1,
                "events": count,
                "grains": count * m,
            }
        )
        done += count
        h = new_grid
        meta["io_seconds"] += time.perf_counter() - started
        meta["updated_utc"] = now()
        atomic_json(metadata_path, meta)
        atomic_npz(
            checkpoint_path,
            grid=h,
            stage=stage,
            done=done,
            rng=json.dumps(rng.bit_generator.state),
            committed=len(meta["chunks"]),
        )
        chunks_this_call += 1
        if stop_after_chunks and chunks_this_call >= stop_after_chunks:
            return meta


def run_config(config_file):
    """Execute the declarative condition list, skipping verified completed runs."""
    config = json.loads(Path(config_file).read_text())
    root = Path(config["output"])
    for model, sizes in config["conditions"].items():
        for L in sizes:
            for seed in config["seeds"]:
                name = f"{model}_L{L}_s{seed}"
                burn = (
                    0
                    if model == "batch"
                    else int(config["burn_factors"][model] * L * L)
                )
                args = dict(
                    L=L,
                    model=model,
                    seed=seed,
                    burn_grains=burn,
                    production_grains=config["production_grains"],
                    chunk_grains=config["chunk_grains"],
                    sample_grains=config["sample_grains"],
                    stream=config["stream"],
                )
                if model == "batch":
                    args["matched_path"] = root / f"baseline_L{L}_s{seed}"
                start = time.perf_counter()
                meta = run_chain(root / name, **args)
                print(
                    name,
                    meta["status"],
                    f"{meta['completed_production_grains']} grains",
                    f"call {time.perf_counter()-start:.2f}s",
                    flush=True,
                )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    run_config(parser.parse_args().config)
