"""Identical workloads, full warm-up and accumulated timing samples."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from sandpile import engine, reference, fast
from sandpile.model import Graph
from sandpile.io import atomic_json, environment


def main():
    settings = json.loads(Path("configs/post_review.json").read_text())["benchmark"]
    compiler = fast.build(force=True)
    g = Graph(16, 16)
    initial = np.full((16, 16), 3, dtype=np.int64)
    sources = np.random.default_rng(91021).integers(g.n, size=(2000, 1))
    start = time.perf_counter()
    fast.run(initial, g, sources[:1], stride=2)
    warmup_seconds = time.perf_counter() - start
    timing = {}
    outputs = {}
    engine_warmups = {}
    for name, method in [
        ("scan_python", reference.stabilize),
        ("queue_python", engine.stabilize),
        ("queue_c_single_calls", fast.stabilize),
        ("queue_c_stream", None),
    ]:

        def workload():
            h = initial.copy()
            if method:
                events = []
                for src in sources:
                    h, _, obs = method(h, g, src)
                    events.append(obs)
                values = np.array(events)
            else:
                h, obs, _, _ = fast.run(h, g, sources, stride=len(sources) + 1)
                values = obs[:, :4]
            return h, values

        start = time.perf_counter()
        for _ in range(settings["full_workload_warmups_per_engine"]):
            outputs[name] = workload()
        engine_warmups[name] = time.perf_counter() - start
        durations = []
        sample_durations = []
        workload_counts = []
        for repeat in range(settings["repetitions"]):
            count = 0
            start = time.perf_counter()
            while True:
                result = workload()
                count += 1
                elapsed = time.perf_counter() - start
                if elapsed >= settings["minimum_sample_seconds"]:
                    break
            sample_durations.append(elapsed)
            workload_counts.append(count)
            durations.append(elapsed / count)
            for actual, expected in zip(result, outputs[name]):
                np.testing.assert_array_equal(actual, expected)
        timing[name] = {
            "seconds": durations,
            "median": float(np.median(durations)),
            "min": min(durations),
            "max": max(durations),
            "iqr": float(np.subtract(*np.percentile(durations, [75, 25]))),
            "accumulated_seconds": sample_durations,
            "complete_workloads_per_sample": workload_counts,
        }
    first = outputs["scan_python"]
    for value in outputs.values():
        for a, b in zip(first, value):
            np.testing.assert_array_equal(a, b)
    result = {
        "L": 16,
        "events": len(sources),
        "seed": 91021,
        "initial": "all three",
        "elementary_topplings": int(first[1][:, 0].sum()),
        "timings": timing,
        "compiler": compiler,
        "load_and_warmup_seconds": warmup_seconds,
        "settings": settings,
        "full_workload_warmup_seconds": engine_warmups,
        "environment": environment(),
        "identical_outputs": True,
        "scope": "Same complete source stream and S/A/D/ell; every workload resets the all-three grid. C stream also records masses. Each engine has a complete-workload warm-up, then five samples accumulating at least 0.2 s each; reported times divide by completed workloads. Timer/loop overhead included. Compilation, warm-up, input generation and I/O excluded.",
    }
    atomic_json("logs/benchmark.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
