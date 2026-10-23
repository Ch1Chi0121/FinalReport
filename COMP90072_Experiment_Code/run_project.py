"""Run the experiment stages in order, recording each command and its outcome."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from sandpile.io import atomic_json, environment, now

ROOT = Path(__file__).resolve().parent
STAGES = {
    "check": ["-m", "unittest", "discover", "-s", "tests", "-v"],
    "benchmark": ["scripts/benchmark.py"],
    "pilot": ["scripts/pilot.py"],
    "production": ["-m", "sandpile.experiment", "configs/full.json"],
    "ensemble": ["scripts/ensemble.py"],
    "confirmation": ["scripts/confirmation.py"],
    "analysis": ["-m", "sandpile.analysis", "configs/full.json"],
    "sensitivity": ["scripts/upper_limit_sensitivity.py"],
    "figures": ["-m", "sandpile.plots"],
    "tables": ["-m", "sandpile.tables"],
    "manifest": ["scripts/manifest.py"],
}


def primary_complete():
    """Check status only; run_config still verifies source/config compatibility."""
    config = json.loads((ROOT / "configs/full.json").read_text())
    for model, sizes in config["conditions"].items():
        for size in sizes:
            for seed in config["seeds"]:
                path = (
                    ROOT / config["output"] / f"{model}_L{size}_s{seed}/metadata.json"
                )
                if (
                    not path.exists()
                    or json.loads(path.read_text())["status"] != "complete"
                ):
                    return False
    return True


def run_stage(stage, arguments):
    """Stop at the first failure and leave raw checkpoints available for resumption."""
    log = ROOT / "logs" / f"workflow_{stage}.txt"
    command = [sys.executable, *arguments]
    started = now()
    timer = time.perf_counter()
    was_complete = primary_complete() if stage == "production" else False
    print(f"{stage}: {' '.join(command)}", flush=True)
    status = "failed"
    try:
        with log.open("w") as stream:
            subprocess.run(
                command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True
            )
        status = "passed"
    finally:
        elapsed = time.perf_counter() - timer
        record = {
            "stage": stage,
            "command": command,
            "started_utc": started,
            "finished_utc": now(),
            "wall_seconds": elapsed,
            "status": status,
            "log": str(log.relative_to(ROOT)),
        }
        history_path = ROOT / "logs/workflow.json"
        history = json.loads(history_path.read_text()) if history_path.exists() else []
        history.append(record)
        atomic_json(history_path, history)
        if stage == "production" and not was_complete:
            # Accumulate calls that did work. Rechecking complete runs must not
            # replace a production measurement with the much shorter check time.
            timing_path = ROOT / "logs/production_timing.json"
            timing = (
                json.loads(timing_path.read_text())
                if timing_path.exists()
                else {"calls": []}
            )
            timing["calls"].append(record)
            timing["wall_seconds"] = sum(
                call["wall_seconds"] for call in timing["calls"]
            )
            timing[
                "scope"
            ] = "Measured production calls through run_project.py, including interrupted calls."
            atomic_json(timing_path, timing)
    print(f"{stage}: passed in {elapsed:.2f} s; {log.relative_to(ROOT)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage",
        choices=["all", "smoke", *STAGES],
        help="all runs the full experimental pipeline",
    )
    args = parser.parse_args()
    (ROOT / "logs").mkdir(exist_ok=True)
    atomic_json(ROOT / "logs/environment.json", environment())

    if args.stage == "all":
        for stage, arguments in STAGES.items():
            run_stage(stage, arguments)
        run_stage("verify", ["scripts/manifest.py", "--verify"])
    elif args.stage == "smoke":
        run_stage("smoke", ["scripts/smoke.py"])
    else:
        run_stage(args.stage, STAGES[args.stage])


if __name__ == "__main__":
    main()
