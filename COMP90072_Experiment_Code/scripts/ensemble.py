"""One state from each independent chain at matched input ages; never sites-as-N."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from sandpile.experiment import run_chain, read_events
from sandpile.io import atomic_json


def main():
    c = json.loads(Path("configs/full.json").read_text())["ensemble"]
    L = c["L"]
    root = Path("data/ensemble_v1")
    results = []
    for seed in range(c["seed_first"], c["seed_first"] + c["chains"]):
        path = root / f"L{L}_s{seed}"
        meta = run_chain(
            path,
            L=L,
            model="baseline",
            seed=seed,
            burn_grains=0,
            production_grains=max(c["sample_factors_L2"]) * L * L,
            stream=c["stream"],
        )
        d = read_events(path)
        observations = []
        for factor in c["sample_factors_L2"]:
            event = factor * L * L
            idx = np.flatnonzero(d["frequency_event"] == event)
            if len(idx) != 1:
                raise ArithmeticError("Missing ensemble checkpoint")
            p = d["frequencies"][idx[0]] / L**2
            observations.append(
                {
                    "grains": event,
                    "height": float(d["events"][event - 1, 4] / L**2),
                    "p3": float(p[3]),
                    "height_frequencies": p.tolist(),
                }
            )
        results.append({"seed": seed, "path": str(path), "observations": observations})
        atomic_json("analysis/ensemble_raw.json", results)
        if len(results) % 20 == 0:
            print("Independent ensemble chains completed", len(results), flush=True)


if __name__ == "__main__":
    main()
