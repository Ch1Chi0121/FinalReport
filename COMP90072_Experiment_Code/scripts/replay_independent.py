"""Independently replay the four retained first L=64 production chunks.

The oracle lives in tests/ and shares no geometry, metrics, or kernel with the
simulator. This is a validation sample, not a replay of every production event.
"""
import json
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
import numpy as np
from array_oracle import stabilize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--samples-root",
        type=Path,
        help="review_evidence/raw_samples in the compact review package",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("logs/independent_replay.json")
    )
    args = parser.parse_args()
    records = []
    for model in ["baseline", "biased", "cylinder", "batch"]:
        path = (
            args.samples_root / model / "production_000000000.npz"
            if args.samples_root
            else Path(f"data/full_v1/{model}_L64_s21001/production_000000000.npz")
        )
        with np.load(path) as data:
            grid = data["grid_start"].copy()
            checkpoints = dict(
                zip(data["frequency_event"].tolist(), data["frequencies"])
            )
            for index, sites, expected in zip(
                data["event_index"], data["sources"], data["events"]
            ):
                grid, _, observed = stabilize(grid, sites, model == "cylinder")
                np.testing.assert_array_equal(observed, expected)
                if int(index) in checkpoints:
                    np.testing.assert_array_equal(
                        np.bincount(grid.ravel(), minlength=4), checkpoints[int(index)]
                    )
            np.testing.assert_array_equal(grid, data["grid_end"])
            records.append(
                {
                    "model": model,
                    "path": str(path),
                    "events": len(data["events"]),
                    "grains": int(data["sources"].size),
                    "checkpoint_frequencies": len(checkpoints),
                    "exact_event_and_final_grid_match": True,
                    "actual_mass_checked_each_event": True,
                }
            )
        print(model, "independent replay passed", flush=True)
    result = {
        "command": "python3 scripts/replay_independent.py"
        + (" --samples-root " + str(args.samples_root) if args.samples_root else ""),
        "records": records,
        "events": sum(r["events"] for r in records),
        "executed_grains": sum(r["grains"] for r in records),
        "scope": "First production chunk of each model at L=64, seed 21001. Batch grains are paired baseline inputs, not independent replication.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
