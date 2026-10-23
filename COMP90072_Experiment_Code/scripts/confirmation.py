"""Prespecified follow-up after a small nominal discrepancy; equal new budgets."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sandpile.experiment import run_config, read_events
from sandpile.analysis import metrics_for_run, independent_difference
from sandpile.statistics import mean_interval
from sandpile.io import atomic_json, now


def main():
    config_file = "configs/confirmation.json"
    c = json.loads(Path(config_file).read_text())
    start = time.perf_counter()
    run_config(config_file)
    rows = []
    runs = []
    for model, sizes in c["conditions"].items():
        for L in sizes:
            vals = []
            for seed in c["seeds"]:
                path = Path(c["output"]) / f"{model}_L{L}_s{seed}"
                d = read_events(path)
                v = metrics_for_run(d["events"], d["frequencies"], L, 1)
                vals.append(v)
                runs.append(
                    {
                        "model": model,
                        "L": L,
                        "seed": seed,
                        "path": str(path),
                        "values": v,
                    }
                )
            rows.append(
                {
                    "model": model,
                    "L": L,
                    "metrics": {
                        k: mean_interval([v[k] for v in vals]) for k in vals[0]
                    },
                }
            )
    differences = []
    for L in [32, 64]:
        differences.append(
            {
                "L": L,
                "height": independent_difference(
                    [
                        x["values"]["height"]
                        for x in runs
                        if x["L"] == L and x["model"] == "biased"
                    ],
                    [
                        x["values"]["height"]
                        for x in runs
                        if x["L"] == L and x["model"] == "baseline"
                    ],
                ),
            }
        )
    atomic_json(
        "analysis/confirmation.json",
        {
            "utc": now(),
            "seconds_this_call": time.perf_counter() - start,
            "config": c,
            "conditions": rows,
            "runs": runs,
            "differences": differences,
        },
    )
    print(json.dumps(differences, indent=2))


if __name__ == "__main__":
    main()
