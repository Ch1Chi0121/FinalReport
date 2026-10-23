"""Post-review fit-range diagnostic on existing primary data; no simulation."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sandpile.experiment import read_events
from sandpile.statistics import discrete_fit, mean_interval
from sandpile.io import atomic_json, check_chunk


def main():
    c = json.loads(Path("configs/post_review.json").read_text())[
        "upper_limit_sensitivity"
    ]
    values = []
    inputs = []
    for seed in c["seeds"]:
        path = Path(f"data/full_v1/{c['model']}_L{c['L']}_s{seed}")
        meta = json.loads((path / "metadata.json").read_text())
        if meta["status"] != "complete":
            raise ValueError("Incomplete primary run")
        for chunk in meta["chunks"]:
            if chunk["stage"] == "production":
                file = path / chunk["file"]
                check_chunk(path, chunk)
                inputs.append({"path": str(file), "bytes": chunk["bytes"]})
        values.append(read_events(path)["events"][:, 0])
    records = []
    for factor in c["xmax_factors_L2"]:
        xmax = int(factor * c["L"] ** 2)
        candidates = []
        for candidate in c["candidate_models"]:
            fits = [
                discrete_fit(x, c["xmin"], xmax, candidate, c["minimum_count"])
                for x in values
            ]
            if any(f["status"] != "ok" for f in fits):
                atomic_json("logs/upper_limit_fit_failure.json", fits)
                raise ArithmeticError("Upper-limit diagnostic fit did not converge")
            row = {
                "candidate": candidate,
                "L": c["L"],
                "xmin": c["xmin"],
                "xmax": xmax,
                "retained_total": sum(f["n"] for f in fits),
                "seed_fits": fits,
                "any_boundary_fit": any(f["at_boundary"] for f in fits),
                "status": "ok",
            }
            for field in ["alpha", "lambda", "KS"]:
                row[field] = mean_interval([f[field] for f in fits])
            candidates.append(row)
        power = next(r for r in candidates if r["candidate"] == "power")
        for row in candidates:
            assert row["retained_total"] == power["retained_total"]
            row["vs_power_log_score_per_retained"] = mean_interval(
                [
                    (f["log_likelihood"] - b["log_likelihood"]) / f["n"]
                    for f, b in zip(row["seed_fits"], power["seed_fits"])
                ]
            )
        records.extend(candidates)
    result = {
        "config": c,
        "inputs": inputs,
        "records": records,
        "command": "python3 scripts/upper_limit_sensitivity.py",
        "scope": "Post-review diagnostic, same five L=64 baseline primary chains; no new independent samples, no changes to primary fits, no calibrated model-selection claim.",
    }
    atomic_json("analysis/upper_limit_sensitivity.json", result)
    print(
        json.dumps(
            [
                {
                    k: r[k]
                    for k in [
                        "candidate",
                        "xmin",
                        "xmax",
                        "retained_total",
                        "alpha",
                        "KS",
                    ]
                }
                for r in records
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
