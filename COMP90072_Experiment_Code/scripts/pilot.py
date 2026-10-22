"""Independent largest-size pilot, start sensitivity and observable-specific ACF."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from sandpile.experiment import run_chain, read_events
from sandpile.statistics import autocorrelation
from sandpile.model import Graph, driving, benchmark
from sandpile.io import atomic_json


def main():
    c = json.loads(Path("configs/pilot.json").read_text())
    root = Path(c["output"])
    results = []
    start_time = time.perf_counter()
    L = c["L"]
    for model in c["models"]:
        for initial, seed in zip(c["starts"], c["seeds"]):
            path = root / f"{model}_{initial}_L{L}"
            meta = run_chain(
                path,
                L=L,
                model=model,
                seed=seed,
                burn_grains=0,
                production_grains=c["grain_factors"][model] * L * L,
                initial=initial,
                stream=c["stream"],
                chunk_grains=c["chunk_grains"],
                sample_grains=c["sample_grains"],
            )
            d = read_events(path)
            e = d["events"]
            f = d["frequencies"] / L**2
            windows = []
            width = 10 * L * L
            for first in range(0, len(e), width):
                x = e[first : first + width]
                freq = f[
                    (d["frequency_event"] > first)
                    & (d["frequency_event"] <= first + width)
                ]
                windows.append(
                    {
                        "start_grains": first,
                        "end_grains": first + len(x),
                        "height": float(x[:, 4].mean() / L**2),
                        "mean_S": float(x[:, 0].mean()),
                        "mean_D": float(x[:, 2].mean()),
                        "p_loss": float((x[:, 2] > 0).mean()),
                        "height_frequencies": freq.mean(axis=0).tolist(),
                    }
                )
            last = e[-4 * width :]
            acf = {}
            for name, x in [
                ("height", last[:, 4]),
                ("S", last[:, 0]),
                ("D", last[:, 2]),
                ("loss_indicator", last[:, 2] > 0),
            ]:
                _, tau = autocorrelation(x, 8192)
                acf[name] = tau
            last_freq = f[-4 * width // c["sample_grains"] :]
            for k in range(4):
                acf[f"frequency_{k}_grains"] = (
                    autocorrelation(last_freq[:, k], 512)[1] * c["sample_grains"]
                )
            graph = Graph(L, L, "cylinder" if model == "cylinder" else "open")
            prediction = benchmark(
                graph, driving(graph, 0.9 if model == "biased" else 0)
            )["mean_S"]
            result = {
                "model": model,
                "initial": initial,
                "seed": seed,
                "L": L,
                "path": str(path),
                "windows": windows,
                "tau_grains": acf,
                "mean_S_prediction": prediction,
                "simulation_seconds": meta["simulation_seconds"],
                "io_seconds": meta["io_seconds"],
                "bytes": sum(p.stat().st_size for p in path.glob("*.npz")),
            }
            results.append(result)
            atomic_json("analysis/pilot.json", results)
            print(
                model,
                initial,
                "windows",
                [round(w["height"], 5) for w in windows],
                "tau",
                acf,
                flush=True,
            )
    print("pilot wall seconds", time.perf_counter() - start_time, flush=True)
    control = root / "batch_control_L64"
    run_chain(
        control,
        L=L,
        model="baseline",
        seed=11004,
        burn_grains=20 * L * L,
        production_grains=20 * L * L,
        stream=110,
    )
    run_chain(
        root / "batch_L64",
        L=L,
        model="batch",
        seed=11004,
        burn_grains=0,
        production_grains=20 * L * L,
        stream=110,
        matched_path=control,
    )


if __name__ == "__main__":
    main()
