"""Export experiment summaries as CSV tables and JSON values."""
import csv
import json
from pathlib import Path
from .io import atomic_json

OUT = Path("results/tables")
SHORT = {"baseline": "base", "biased": "bias", "cylinder": "cyl", "batch": "batch"}


def read(name):
    return json.loads(Path(f"analysis/{name}.json").read_text())


def pm(ci, digits=4):
    return f"{ci['mean']:.{digits}f} +/- {(ci['high']-ci['low'])/2:.{digits}f}"


def interval_precision(ci, digits):
    """Show a nonzero interval width without altering the stored endpoints."""
    original = digits
    while ci["low"] < ci["high"] and float(f"{ci['low']:.{digits}f}") == float(
        f"{ci['high']:.{digits}f}"
    ):
        digits += 1
    # One guard decimal avoids making a narrow interval look only one unit wide.
    return digits + 1 if digits > original else digits


def interval(ci, digits=5):
    digits = interval_precision(ci, digits)
    return f"[{ci['low']:.{digits}f}, {ci['high']:.{digits}f}]"


def main():
    """Export tables, full-precision summary rows and formatted numerical values.

    number_sources.json records each value and its analysis key. Narrow intervals
    retain enough decimal places to show their nonzero width. Runtime values read
    measured logs; primary and confirmation results remain separate inputs.
    """
    OUT.mkdir(exist_ok=True, parents=True)
    summary = read("summary")
    values = {}
    sources = {}

    def add(key, value, source):
        values[key] = str(value)
        sources[key] = source

    def table(name, headers, rows):
        with (OUT / f"{name}.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(rows)

    for c in summary["conditions"]:
        prefix = SHORT[c["model"]] + str(c["L"])
        for metric, ci in c["metrics"].items():
            decimals = (
                5
                if metric in ["height", "p0", "p1", "p2", "p3"]
                else 4
                if metric.startswith("p_") or metric.startswith("D_grain")
                else 3
            )
            add(
                prefix + metric,
                f"{ci['mean']:.{decimals}f}",
                f"summary.conditions[{c['model']},{c['L']}].metrics.{metric}",
            )
            add(
                prefix + metric + "CI",
                interval(ci, decimals),
                f"summary.conditions[{c['model']},{c['L']}].metrics.{metric}",
            )
        add(
            prefix + "prediction",
            f"{c['S_prediction_grain']:.3f}",
            "summary.S_prediction_grain",
        )
        add(
            prefix + "avalancheN",
            f"{round(c['events']*c['metrics']['p_trigger']['mean']):,}",
            "summary.events * metrics.p_trigger",
        )
    add(
        "productionGrains",
        f"{summary['total_production_grains']:,}",
        "summary.total_production_grains",
    )
    add(
        "productionEvents",
        f"{summary['total_production_events']:,}",
        "summary.total_production_events",
    )
    add(
        "kernelSeconds",
        f"{summary['kernel_seconds_including_burn']:.2f}",
        "summary.kernel_seconds_including_burn",
    )
    add("ioSeconds", f"{summary['chunk_io_seconds']:.2f}", "summary.chunk_io_seconds")
    timing = json.loads(Path("logs/production_timing.json").read_text())
    add(
        "productionWall",
        f"{timing['wall_seconds']:.2f}",
        "logs/production_timing.json.wall_seconds",
    )
    benchmark = json.loads(Path("logs/benchmark.json").read_text())
    rows = []
    labels = {
        "scan_python": "Elementary scan, Python",
        "queue_python": "Bulk queue, Python",
        "queue_c_single_calls": "C queue, one event per call",
        "queue_c_stream": "C queue, full input sequence",
    }
    reference = benchmark["timings"]["scan_python"]["median"]
    for name, timing in benchmark["timings"].items():
        rows.append(
            [
                labels[name],
                f"{timing['median']*1000:.3f}",
                f"[{timing['min']*1000:.3f}, {timing['max']*1000:.3f}]",
                f"{reference/timing['median']:.1f}",
            ]
        )
    table(
        "performance_table",
        ["Implementation", "Median (ms)", "Range (ms)", "Speed ratio"],
        rows,
    )
    for key, value in {
        "benchmarkEvents": benchmark["events"],
        "benchmarkTopples": benchmark["elementary_topplings"],
        "compileSeconds": f"{benchmark['compiler']['seconds']:.3f}",
        "warmupSeconds": f"{benchmark['load_and_warmup_seconds']:.3f}",
        "queueSpeed": f"{reference/benchmark['timings']['queue_python']['median']:.1f}",
    }.items():
        add(key, value, "logs/benchmark.json")
    rows = []
    for c in summary["conditions"]:
        if c["model"] != "baseline":
            continue
        v = c["metrics"]
        rows.append(
            [
                str(c["L"]),
                pm(v["height"], 5),
                f"{c['S_prediction_grain']:.3f}",
                pm(v["S_grain"], 3),
                f"{v['p_zero']['mean']:.4f}",
                f"{v['p_zero_loss_given_avalanche']['mean']:.4f}",
                f"{v['p_loss']['mean']:.4f}",
            ]
        )
    table(
        "baseline_table",
        [
            "L",
            "Mean height",
            "Pred. S",
            "Measured S",
            "P(S=0)",
            "P(D=0 |  S>0)",
            "P(D>0)",
        ],
        rows,
    )
    rows = []
    fits = read("fits")
    for obs in ["S", "A", "D", "ell"]:
        for candidate in ["power", "cutoff", "exponential"]:
            r = next(
                f
                for f in fits
                if f["L"] == 64
                and f["observable"] == obs
                and f["xmin_factor"] == 1
                and f["candidate"] == candidate
            )
            if r["status"] != "ok":
                raise ValueError("Selected fit has not passed optimizer check")
            prefix = "fit" + obs + candidate
            for field in ["alpha", "lambda", "KS"]:
                for suffix, val in [
                    ("", f"{r[field]['mean']:.4f}"),
                    ("CI", interval(r[field], 4)),
                ]:
                    add(prefix + field + suffix, val, f"fits.{obs}.{candidate}.{field}")
            add(
                prefix + "N",
                f"{r['retained_total']:,}",
                f"fits.{obs}.{candidate}.retained_total",
            )
            add(
                prefix + "max",
                r["observed_max"],
                f"fits.{obs}.{candidate}.observed_max",
            )
            if "vs_power_log_score_per_retained" in r:
                add(
                    prefix + "score",
                    f"{r['vs_power_log_score_per_retained']['mean']:.4f}",
                    f"fits.{obs}.{candidate}.vs_power_log_score_per_retained",
                )
            tag = f"{obs}: [{r['xmin']},{r['xmax']}]"
            lam = (
                "--"
                if candidate == "power"
                else pm(r["lambda"], 6 if obs in ["S", "A"] else 4)
            )
            alpha = "--" if candidate == "exponential" else pm(r["alpha"], 4)
            rows.append(
                [
                    tag,
                    {"power": "Power", "cutoff": "Cutoff", "exponential": "Exp."}[
                        candidate
                    ],
                    f"{r['retained_total']:,}",
                    alpha,
                    lam,
                    f"{r['KS']['mean']:.4f}",
                ]
            )
    table(
        "fits_table",
        ["Quantity: support", "Model", "Retained n", "alpha", "lambda", "KS"],
        rows,
    )
    rows = []
    for L in [32, 64]:
        for model in ["baseline", "biased", "cylinder", "batch"]:
            c = next(
                c for c in summary["conditions"] if c["L"] == L and c["model"] == model
            )
            v = c["metrics"]
            rows.append(
                [
                    str(L),
                    {
                        "baseline": "Open/uniform",
                        "biased": "Open/biased",
                        "cylinder": "Cylinder",
                        "batch": "Batch, m=4",
                    }[model],
                    pm(v["height"], 5),
                    pm(v["S_grain"], 2),
                    f"{v['p_trigger']['mean']:.4f}",
                    f"{v['p_loss']['mean']:.4f}",
                    f"{v['D_positive']['mean']:.3f}",
                ]
            )
    table(
        "extensions_table",
        [
            "L",
            "Condition",
            "Mean height",
            "S/grain",
            "P(S>0)",
            "P(D>0)",
            "E[D |  D>0]",
        ],
        rows,
    )
    # Full machine-readable tables retain all precision and intervals.
    with open(OUT / "summary.csv", "w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["model", "L", "metric", "mean", "low95", "high95", "n_seeds"])
        for c in summary["conditions"]:
            for metric, ci in c["metrics"].items():
                writer.writerow(
                    [
                        c["model"],
                        c["L"],
                        metric,
                        ci["mean"],
                        ci["low"],
                        ci["high"],
                        ci["n"],
                    ]
                )
    correlations = read("correlations")
    for row in correlations:
        if row["L"] == 64:
            key = "rho" + "".join(row["pair"])
            digits = interval_precision(row["interval"], 4)
            add(
                key,
                f"{row['interval']['mean']:.{digits}f}",
                "correlations.L64." + "-".join(row["pair"]),
            )
            add(
                key + "CI",
                interval(row["interval"], 4),
                "correlations.L64." + "-".join(row["pair"]),
            )
    ensemble = read("ensemble")
    for obs in ["height", "p3"]:
        time = next(
            x
            for x in ensemble["time_block_sensitivity"]
            if x["observable"] == obs and x["block_grains"] == 8192
        )["time"]
        for prefix, ci in [("time", time), ("ensemble", ensemble["ages"][-1][obs])]:
            add(prefix + obs, f"{ci['mean']:.5f}", f"ensemble.{prefix}.{obs}")
            add(prefix + obs + "CI", interval(ci, 5), f"ensemble.{prefix}.{obs}")
    for row in read("extensions"):
        prefix = SHORT[row["model"]] + str(row["L"]) + "heightDifference"
        add(prefix, f"{row['metrics']['height']['mean']:.6f}", "extensions.height")
        add(prefix + "CI", interval(row["metrics"]["height"], 6), "extensions.height")
    confirmation = read("confirmation")
    for row in confirmation["differences"]:
        add(
            "confirm" + str(row["L"]),
            f"{row['height']['mean']:.6f}",
            "confirmation.differences",
        )
        add(
            "confirm" + str(row["L"]) + "CI",
            interval(row["height"], 6),
            "confirmation.differences",
        )
    coupling = read("coupling")
    add(
        "matchedBatches", f"{sum(c['batches'] for c in coupling):,}", "coupling.batches"
    )
    for L in [32, 64]:
        r = [x for x in coupling if x["L"] == L]
        add(
            "overlap" + str(L),
            f"{sum(x['overlap_events'] for x in r)/sum(x['batches'] for x in r)*100:.2f}",
            "coupling.overlap_events/batches",
        )
        add(
            "overcount" + str(L),
            f"{sum(x['mean_area_sum_minus_union'] for x in r)/len(r):.2f}",
            "coupling.mean_area_sum_minus_union",
        )
    for obs in ["S", "A", "D", "ell"]:
        selected = [
            r
            for r in fits
            if r["L"] == 64 and r["observable"] == obs and r["candidate"] == "power"
        ]
        add(
            "sensitivity" + obs,
            f"{min(r['alpha']['mean'] for r in selected):.3f}--{max(r['alpha']['mean'] for r in selected):.3f}",
            "fits.xmin_sensitivity",
        )
    upper = read("upper_limit_sensitivity")["records"]
    for candidate in ["power", "cutoff"]:
        selected = sorted(
            [r for r in upper if r["candidate"] == candidate], key=lambda r: r["xmax"]
        )
        add(
            "upper" + candidate + "KS",
            ", ".join(f"{r['KS']['mean']:.4f}" for r in selected),
            f"upper_limit_sensitivity.records[{candidate}].KS.mean, ordered by xmax",
        )
    selected = sorted(
        [r for r in upper if r["candidate"] == "power"], key=lambda r: r["xmax"]
    )
    add(
        "upperPowerAlpha",
        f"{min(r['alpha']['mean'] for r in selected):.3f}--{max(r['alpha']['mean'] for r in selected):.3f}",
        "upper_limit_sensitivity.records[power].alpha.mean range",
    )
    add(
        "upperRetained",
        ", ".join(f"{r['retained_total']:,}" for r in selected),
        "upper_limit_sensitivity.records[power].retained_total, ordered by xmax",
    )
    atomic_json(OUT / "values.json", values)
    atomic_json(
        OUT / "number_sources.json",
        {k: {"value": values[k], "analysis_key": sources[k]} for k in values},
    )
    print("Generated", len(values), "numerical values and CSV tables")


if __name__ == "__main__":
    main()
