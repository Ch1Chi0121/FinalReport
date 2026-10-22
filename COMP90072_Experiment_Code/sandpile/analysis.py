"""Production-only statistical analysis; raw data are immutable inputs.

Run `python3 -m sandpile.analysis configs/full.json`. Tables and figures consume
these JSON/NPZ artifacts, without rerunning the stochastic experiment.
"""
import argparse
import itertools
import json
from pathlib import Path
import time
import numpy as np
from scipy.stats import spearmanr, t
from .experiment import read_events
from .io import atomic_json, atomic_npz, sha256, now
from .model import Graph, driving, benchmark
from .statistics import (
    mean_interval,
    autocorrelation,
    block_means,
    histogram,
    discrete_fit,
    log_scores,
)

NAMES = ["S", "A", "D", "ell"]


def metrics_for_run(events, frequencies, L, m):
    """Summarize one independent run before combining seeds.

    All input events enter height, toppling and loss means, including zeros. Avalanche
    probabilities condition on S>0 only where their names say so; D_positive conditions
    on D>0. Height frequencies come from regularly sampled stable checkpoints.
    """
    avalanche = events[:, 0] > 0
    loss = events[:, 2] > 0
    result = {
        "height": float(events[:, 4].mean() / L**2),
        "S_event": float(events[:, 0].mean()),
        "S_grain": float(events[:, 0].mean() / m),
        "A_event": float(events[:, 1].mean()),
        "D_event": float(events[:, 2].mean()),
        "D_grain": float(events[:, 2].mean() / m),
        "ell_event": float(events[:, 3].mean()),
        "p_zero": float((~avalanche).mean()),
        "p_trigger": float(avalanche.mean()),
        "p_loss": float(loss.mean()),
        "p_zero_loss_given_avalanche": float((events[avalanche, 2] == 0).mean()),
        "D_positive": float(events[loss, 2].mean()),
    }
    for i in range(4):
        result[f"p{i}"] = float(frequencies[:, i].mean() / L**2)
    return result


def independent_difference(a, b):
    """Welch interval for an independent extension minus baseline contrast."""
    a, b = np.asarray(a), np.asarray(b)
    va = a.var(ddof=1) / len(a)
    vb = b.var(ddof=1) / len(b)
    se = np.sqrt(va + vb)
    df = (va + vb) ** 2 / (va**2 / (len(a) - 1) + vb**2 / (len(b) - 1))
    center = float(a.mean() - b.mean())
    half = float(t.ppf(0.975, df) * se)
    return {
        "mean": center,
        "low": center - half,
        "high": center + half,
        "df": float(df),
    }


def analyse(config_file):
    """Validate primary raw records and produce the report's analysis files.

    For each condition, check chunk hashes, mass, the finite-window potential identity
    and observable bounds. Compute per-seed summaries first, then seed intervals.
    Baseline distributions keep zero-loss avalanches; positive-loss fits exclude D=0.
    Batch controls are compared pathwise with grouped baseline records.

    JSON summaries, integer PMFs/CCDFs and ACF arrays are written under analysis/.
    The independent ensemble must already exist; run scripts/ensemble.py first.
    """
    start = time.perf_counter()
    config = json.loads(Path(config_file).read_text())
    if config["schema"] != "full-v1":
        raise ValueError("Main analyses require frozen full production config")
    root = Path(config["output"])
    out = Path("analysis")
    out.mkdir(exist_ok=True)
    dist_dir = out / "distributions"
    dist_dir.mkdir(exist_ok=True)
    settings = config["analysis"]
    all_runs = []
    conditions = []
    windows = []
    correlations = []
    boundary = []
    acfs = []
    fits = []
    inputs = []
    benchmarks = []
    coupling = []
    for model, sizes in config["conditions"].items():
        for L in sizes:
            m = 4 if model == "batch" else 1
            graph = Graph(L, L, "cylinder" if model == "cylinder" else "open")
            theory = benchmark(
                graph, driving(graph, 0.9 if model == "biased" else 0), m
            )
            benchmarks.append(
                {
                    "model": model,
                    "L": L,
                    "mean_S_event": theory["mean_S"],
                    "mean_S_grain": theory["mean_S"] / m,
                    "residual": theory["residual"],
                    "S_physical_upper_bound": theory["S_bound"],
                }
            )
            runs = []
            datasets = []
            seed_corr = []
            for seed in config["seeds"]:
                path = root / f"{model}_L{L}_s{seed}"
                meta = json.loads((path / "metadata.json").read_text())
                if (
                    meta["status"] != "complete"
                    or meta["completed_production_grains"]
                    != config["production_grains"]
                ):
                    raise ValueError(f"Incomplete production: {path}")
                for chunk in meta["chunks"]:
                    if sha256(path / chunk["file"]) != chunk["sha256"]:
                        raise ArithmeticError("Raw chunk hash mismatch")
                    inputs.append(
                        {
                            "id": str(path / chunk["file"]),
                            "sha256": chunk["sha256"],
                            "model": model,
                            "L": L,
                            "seed": seed,
                            "stage": chunk["stage"],
                        }
                    )
                d = read_events(path)
                datasets.append(d)
                e = d["events"]
                with np.load(path / "production_start.npz") as data:
                    h0 = data["grid"]
                with np.load(path / "checkpoint.npz") as data:
                    h1 = data["grid"]
                expected = e.shape[0] * m - int(h1.sum() - h0.sum())
                if int(e[:, 2].sum()) != expected:
                    raise ArithmeticError("Window mass balance failed")
                potential_error = float(
                    e[:, 0].sum()
                    - theory["potential"][d["sources"]].sum()
                    - theory["potential"] @ (h0 - h1).ravel()
                )
                if abs(potential_error) > 1e-4:
                    raise ArithmeticError("Integrated potential identity failed")
                if np.any(e[:, 0] > theory["S_bound"]) or np.any(
                    e[:, 2] > 3 * L * L + m
                ):
                    raise ArithmeticError("Physical support violation")
                max_reach = L + (L // 2) if model == "cylinder" else 2 * L - 1
                if np.any(e[:, 3] > max_reach) or np.any(e[e[:, 0] == 0, :4]):
                    raise ArithmeticError("Reach/zero-event violation")
                values = metrics_for_run(e, d["frequencies"], L, m)
                record = {
                    "model": model,
                    "L": L,
                    "seed": seed,
                    "path": str(path),
                    "m": m,
                    "events": len(e),
                    "grains": len(e) * m,
                    "values": values,
                    "mass_start": int(h0.sum()),
                    "mass_end": int(h1.sum()),
                    "potential_identity_error": potential_error,
                    "simulation_seconds": meta["simulation_seconds"],
                    "io_seconds": meta["io_seconds"],
                }
                runs.append(record)
                all_runs.append(record)
                for w, indices in enumerate(np.array_split(np.arange(len(e)), 4)):
                    lo, hi = int(indices[0]), int(indices[-1]) + 1
                    fm = (d["frequency_event"] > lo) & (d["frequency_event"] <= hi)
                    windows.append(
                        {
                            "model": model,
                            "L": L,
                            "seed": seed,
                            "window": w + 1,
                            "first_event": lo + 1,
                            "last_event": hi,
                            "values": metrics_for_run(
                                e[lo:hi], d["frequencies"][fm], L, m
                            ),
                        }
                    )
                dependence = {}
                for name, x in [
                    ("height", e[:, 4]),
                    ("S", e[:, 0]),
                    ("D", e[:, 2]),
                    ("loss_indicator", e[:, 2] > 0),
                ]:
                    rho, tau = autocorrelation(x, settings["acf_max_lag_grains"] // m)
                    dependence[name] = {
                        "tau_events": tau,
                        "tau_grains": tau * m,
                        "rho_lag1": float(rho[1]) if len(rho) > 1 else None,
                    }
                    if seed == config["seeds"][0]:
                        atomic_npz(
                            out / f"acf_{model}_L{L}_{name}.npz",
                            lag_grains=np.arange(len(rho)) * m,
                            rho=rho,
                        )
                for k in range(4):
                    _, tau = autocorrelation(d["frequencies"][:, k], 512)
                    dependence[f"p{k}"] = {
                        "tau_samples": tau,
                        "tau_grains": tau * config["sample_grains"],
                    }
                acfs.append(
                    {"model": model, "L": L, "seed": seed, "observables": dependence}
                )
                if model == "baseline":
                    avalanche = e[e[:, 0] > 0, :4]
                    coeff = spearmanr(avalanche, axis=0).statistic
                    seed_corr.append(coeff)
                    # A descriptive boundary stratification within fixed size bands.
                    bins = np.array(settings["boundary_bins_fraction_L"]) * L
                    for band in range(len(bins) - 1):
                        bm = (e[:, 5] >= bins[band]) & (e[:, 5] < bins[band + 1])
                        for left, right in zip(
                            settings["size_strata"][:-1], settings["size_strata"][1:]
                        ):
                            keep = bm & (e[:, 0] >= left) & (e[:, 0] < right)
                            boundary.append(
                                {
                                    "L": L,
                                    "seed": seed,
                                    "boundary_low": float(bins[band]),
                                    "boundary_high_exclusive": float(bins[band + 1]),
                                    "size_low": left,
                                    "size_high_exclusive": right,
                                    "n": int(keep.sum()),
                                    "p_loss": float((e[keep, 2] > 0).mean())
                                    if keep.any()
                                    else None,
                                }
                            )
                if model == "batch":
                    parent = root / f"baseline_L{L}_s{seed}"
                    baseline = read_events(parent)
                    grouped = (
                        baseline["events"][:, [0, 2]].reshape(-1, 4, 2).sum(axis=1)
                    )
                    if not np.array_equal(grouped, e[:, [0, 2]]):
                        raise ArithmeticError("Coupling failed")
                    np.testing.assert_array_equal(
                        baseline["sources"].ravel(), d["sources"].ravel()
                    )
                    np.testing.assert_array_equal(
                        baseline["frequencies"], d["frequencies"]
                    )
                    sum_area = baseline["events"][:, 1].reshape(-1, 4).sum(axis=1)
                    if np.any(e[:, 1] > sum_area):
                        raise ArithmeticError("Batch union area exceeds sum")
                    coupling.append(
                        {
                            "L": L,
                            "seed": seed,
                            "batches": len(e),
                            "grains": len(e) * 4,
                            "max_S_difference": int(
                                np.max(np.abs(grouped[:, 0] - e[:, 0]))
                            ),
                            "max_D_difference": int(
                                np.max(np.abs(grouped[:, 1] - e[:, 2]))
                            ),
                            "overlap_events": int((sum_area > e[:, 1]).sum()),
                            "mean_area_sum_minus_union": float(
                                (sum_area - e[:, 1]).mean()
                            ),
                            "height_frequency_checkpoints_equal": True,
                        }
                    )
            aggregate = {
                key: mean_interval([r["values"][key] for r in runs])
                for key in runs[0]["values"]
            }
            conditions.append(
                {
                    "model": model,
                    "L": L,
                    "m": m,
                    "seeds": len(runs),
                    "events": sum(r["events"] for r in runs),
                    "grains": sum(r["grains"] for r in runs),
                    "metrics": aggregate,
                    "S_prediction_event": theory["mean_S"],
                    "S_prediction_grain": theory["mean_S"] / m,
                }
            )
            if model == "baseline":
                for i, j in itertools.combinations(range(4), 2):
                    correlations.append(
                        {
                            "L": L,
                            "pair": [NAMES[i], NAMES[j]],
                            "sample": "S>0, retains D=0",
                            "interval": mean_interval([c[i, j] for c in seed_corr]),
                            "seed_estimates": [float(c[i, j]) for c in seed_corr],
                        }
                    )
            for column, name in enumerate(NAMES):
                values = np.concatenate(
                    [d["events"][d["events"][:, 0] > 0, column] for d in datasets]
                )
                x, pmf, ccdf = histogram(values)
                atomic_npz(
                    dist_dir / f"{model}_L{L}_{name}.npz",
                    x=x,
                    pmf=pmf,
                    ccdf=ccdf,
                    n=len(values),
                    sample="S>0; D=0 retained",
                )
                if model != "baseline":
                    continue
                xmax = {"S": L * L, "A": L * L, "D": 3 * L * L + 1, "ell": 2 * L - 1}[
                    name
                ]
                default = settings["fit_xmin"][name]
                for factor in settings["fit_xmin_sensitivity"]:
                    xmin = max(1, int(default * factor))
                    if xmin >= xmax:
                        continue
                    for candidate in settings["candidate_models"]:
                        estimates = [
                            discrete_fit(
                                d["events"][:, column],
                                xmin,
                                xmax,
                                candidate,
                                settings["fit_minimum_count"],
                            )
                            for d in datasets
                        ]
                        item = {
                            "L": L,
                            "observable": name,
                            "candidate": candidate,
                            "xmin_factor": factor,
                            "xmin": xmin,
                            "xmax": xmax,
                            "upper_limit_type": "chosen intermediate truncation"
                            if name == "S"
                            else "physical bound",
                            "sample": "D>0" if name == "D" else "S>0",
                            "observed_max": int(values.max()),
                            "physical_upper_bound": theory["S_bound"]
                            if name == "S"
                            else xmax,
                            "retained_total": sum(v["n"] for v in estimates),
                            "seed_fits": estimates,
                            "status": "ok"
                            if all(x["status"] == "ok" for x in estimates)
                            else "incomplete_fit",
                        }
                        if item["status"] == "ok":
                            item.update(
                                {
                                    "alpha": mean_interval(
                                        [f["alpha"] for f in estimates]
                                    ),
                                    "lambda": mean_interval(
                                        [f["lambda"] for f in estimates]
                                    ),
                                    "KS": mean_interval([f["KS"] for f in estimates]),
                                    "log_likelihood_per_retained": mean_interval(
                                        [
                                            f["log_likelihood"] / f["n"]
                                            for f in estimates
                                        ]
                                    ),
                                    "any_boundary_fit": any(
                                        f["at_boundary"] for f in estimates
                                    ),
                                }
                            )
                        fits.append(item)
                # Dependence-aware descriptive score contrast using fitted marginals.
                base = next(
                    f
                    for f in fits
                    if f["L"] == L
                    and f["observable"] == name
                    and f["xmin_factor"] == 1
                    and f["candidate"] == "power"
                )
                for alternative in ["cutoff", "exponential"]:
                    alt = next(
                        f
                        for f in fits
                        if f["L"] == L
                        and f["observable"] == name
                        and f["xmin_factor"] == 1
                        and f["candidate"] == alternative
                    )
                    if alt["status"] != "ok" or base["status"] != "ok":
                        continue
                    changes = []
                    block_sensitivity = {
                        str(b): [] for b in settings["block_sensitivity"]
                    }
                    for d, bfit, afit in zip(
                        datasets, base["seed_fits"], alt["seed_fits"]
                    ):
                        bs, keep = log_scores(d["events"][:, column], bfit)
                        as_, _ = log_scores(d["events"][:, column], afit)
                        diff = as_ - bs
                        changes.append(float(diff.sum() / keep.sum()))
                        for b in settings["block_sensitivity"]:
                            n = len(diff) // b
                            nums = diff[: n * b].reshape(n, b).sum(axis=1)
                            dens = keep[: n * b].reshape(n, b).sum(axis=1)
                            block_sensitivity[str(b)].append(mean_interval(nums / dens))
                    alt["vs_power_log_score_per_retained"] = mean_interval(changes)
                    alt["log_score_block_sensitivity"] = block_sensitivity
            print("analysed", model, L, flush=True)
    summary = {
        "schema": "analysis-v1",
        "conditions": conditions,
        "runs": all_runs,
        "total_production_grains": sum(r["grains"] for r in all_runs),
        "total_production_events": sum(r["events"] for r in all_runs),
        "kernel_seconds_including_burn": sum(r["simulation_seconds"] for r in all_runs),
        "chunk_io_seconds": sum(r["io_seconds"] for r in all_runs),
    }
    atomic_json(out / "summary.json", summary)
    atomic_json(out / "stationarity.json", windows)
    atomic_json(out / "acf.json", acfs)
    atomic_json(out / "correlations.json", correlations)
    atomic_json(out / "boundary.json", boundary)
    atomic_json(out / "fits.json", fits)
    atomic_json(out / "benchmarks.json", benchmarks)
    atomic_json(out / "coupling.json", coupling)
    contrasts = []
    for model in ["biased", "cylinder"]:
        for L in config["conditions"][model]:
            a = [r for r in all_runs if r["model"] == model and r["L"] == L]
            b = [r for r in all_runs if r["model"] == "baseline" and r["L"] == L]
            contrasts.append(
                {
                    "model": model,
                    "L": L,
                    "difference": "extension minus baseline; independent-seed Welch interval",
                    "metrics": {
                        key: independent_difference(
                            [r["values"][key] for r in a], [r["values"][key] for r in b]
                        )
                        for key in a[0]["values"]
                    },
                }
            )
    atomic_json(out / "extensions.json", contrasts)
    analyse_ensemble(config)
    atomic_json(out / "raw_inputs.json", inputs)
    atomic_json(
        out / "analysis_run.json",
        {
            "utc": now(),
            "seconds": time.perf_counter() - start,
            "command": f"python3 -m sandpile.analysis {config_file}",
            "config_sha256": sha256(config_file),
            "settings": settings,
            "fit_status_counts": {
                s: sum(f["status"] == s for f in fits)
                for s in {f["status"] for f in fits}
            },
        },
    )


def analyse_ensemble(config):
    """Compare a blocked time average with states from independent chains.

    A chain, rather than an individual lattice site, is the ensemble replicate.
    Only complete time blocks enter the blocked estimates; their unused remainder
    is recorded for each block length.
    """
    L = config["ensemble"]["L"]
    seed = config["seeds"][0]
    path = Path(config["output"]) / f"baseline_L{L}_s{seed}"
    d = read_events(path)
    ensemble = json.loads(Path("analysis/ensemble_raw.json").read_text())
    ages = []
    for idx, factor in enumerate(config["ensemble"]["sample_factors_L2"]):
        ages.append(
            {
                "grains": factor * L * L,
                "height": mean_interval(
                    [r["observations"][idx]["height"] for r in ensemble]
                ),
                "p3": mean_interval([r["observations"][idx]["p3"] for r in ensemble]),
            }
        )
    results = []
    rng = np.random.default_rng(config["analysis"]["resampling_stream"])
    for grains in config["analysis"]["block_sensitivity"]:
        for name, x, stride in [
            ("height", d["events"][:, 4] / L**2, 1),
            ("p3", d["frequencies"][:, 3] / L**2, config["sample_grains"]),
        ]:
            block = grains // stride
            means = block_means(x, block)
            estimate = mean_interval(means)
            boot = np.array(
                [
                    rng.choice(means, size=len(means), replace=True).mean()
                    for _ in range(config["analysis"]["bootstrap_repetitions"])
                ]
            )
            results.append(
                {
                    "observable": name,
                    "block_grains": grains,
                    "time": estimate,
                    "bootstrap_95": np.quantile(boot, [0.025, 0.975]).tolist(),
                    "complete_blocks": len(means),
                    "retained_grains": len(means) * grains,
                    "remainder_grains": config["production_grains"]
                    - len(means) * grains,
                }
            )
    atomic_json(
        "analysis/ensemble.json",
        {
            "L": L,
            "time_seed": seed,
            "independent_chains": len(ensemble),
            "ages": ages,
            "time_block_sensitivity": results,
            "bootstrap": "200 nonoverlapping contiguous-block resamples, PCG64 seed 410; sensitivity, not exact calibration",
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", nargs="?", default="configs/full.json")
    analyse(parser.parse_args().config)
