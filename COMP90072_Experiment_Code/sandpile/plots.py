"""Figures from analysis artifacts and retained production events."""
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("tmp/matplotlib").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import FixedLocator, ScalarFormatter, NullLocator
import numpy as np
from .experiment import read_events
from .model import Graph, driving
from .statistics import histogram, fitted_pmf, mean_interval

OUT = Path("results/figures")
AN = Path("analysis")
COLORS = {
    "baseline": "#235789",
    "biased": "#ad3d45",
    "cylinder": "#2b8667",
    "batch": "#8b5aa6",
}
SIZECOLORS = ["#cc8a23", "#318b80", "#4067ab", "#863f72"]
LABEL = {
    "baseline": "Uniform, open",
    "biased": "Biased, open",
    "cylinder": "Uniform, cylinder",
    "batch": "Batch m=4",
}
SYMBOL = {
    "S": "Topplings $S$",
    "A": "Area $A$",
    "D": "Loss $D$",
    "ell": "Reach $\\ell$",
}


def load(name):
    return json.loads((AN / f"{name}.json").read_text())


def save(fig, name):
    """Save one experiment figure at a fixed resolution and close its Matplotlib state."""
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=260, facecolor="white")
    plt.close(fig)


def style():
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.labelsize": 10,
            "axes.titlesize": 11,
            "legend.fontsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.18,
            "grid.linewidth": 0.5,
            "figure.constrained_layout.use": True,
            "lines.linewidth": 1.5,
        }
    )


def condition(model, L):
    return next(
        x for x in load("summary")["conditions"] if x["model"] == model and x["L"] == L
    )


def errorbar(ax, x, ci, **kwargs):
    ax.errorbar(
        x,
        ci["mean"],
        yerr=[[ci["mean"] - ci["low"]], [ci["high"] - ci["mean"]]],
        capsize=3,
        **kwargs,
    )


def inclusive_ccdf(ax, x, probability, **kwargs):
    """Plot P(X >= x): between support points use the next point's height.

    For support [1, 3], the probability at threshold 2 is P(X >= 3),
    not P(X >= 1). Matplotlib's 'pre' convention preserves this meaning.
    """
    return ax.step(x, probability, where="pre", **kwargs)


def ccdf(ax, model, L, name, **kwargs):
    with np.load(AN / "distributions" / f"{model}_L{L}_{name}.npz") as d:
        x = d["x"]
        p = d["ccdf"]
        keep = x > 0
        inclusive_ccdf(ax, x[keep], p[keep], **kwargs)
    ax.set(
        xscale="log", yscale="log", xlabel=SYMBOL[name], ylabel="$P(X\\geq x\\mid S>0)$"
    )
    ax.set_ylim(1e-6, 1.1)


def pooled(model, L):
    """Read the five runs for a display; statistical intervals remain seed-based."""
    c = json.loads(Path("configs/full.json").read_text())
    return np.concatenate(
        [
            read_events(Path(c["output"]) / f"{model}_L{L}_s{s}")["events"]
            for s in c["seeds"]
        ]
    )


def pilot_figure():
    """Show early transients and later windows from the three pilot starts."""
    pilot = load("pilot")
    fig, axes = plt.subplots(2, 3, figsize=(7, 4.2))
    starts = {"empty": "#235789", "random": "#c07a1c", "three": "#2b8667"}
    for col, model in enumerate(["baseline", "biased", "cylinder"]):
        for row in [r for r in pilot if r["model"] == model]:
            e = read_events(row["path"])["events"]
            n = min(len(e), 12 * 64**2) // 512
            axes[0, col].plot(
                (np.arange(n) + 0.5) * 512 / 64**2,
                e[: n * 512, 4].reshape(n, 512).mean(axis=1) / 64**2,
                color=starts[row["initial"]],
                label=row["initial"],
            )
            late = row["windows"][1:]
            axes[1, col].plot(
                [(w["start_grains"] + w["end_grains"]) / 2 / 64**2 for w in late],
                [w["height"] for w in late],
                "o-",
                ms=3,
                color=starts[row["initial"]],
            )
        axes[0, col].set(
            title=LABEL[model],
            xlabel="Input grains / $L^2$",
            ylabel="Mean height",
            ylim=(0, 3.05),
        )
        axes[1, col].set(xlabel="Input grains / $L^2$", ylabel="Window mean height")
        axes[1, col].axvline(
            40 if model == "biased" else 20,
            color="black",
            ls=":",
            label="Frozen burn-in",
        )
    axes[0, 0].legend(loc="lower right")
    save(fig, "pilot")


def baseline_figure():
    fig, axes = plt.subplots(1, 3, figsize=(7, 2.9))
    sizes = [8, 16, 32, 64]
    for L, color in zip(sizes, SIZECOLORS):
        c = condition("baseline", L)
        errorbar(axes[0], L, c["metrics"]["height"], fmt="o", color=color)
        offset = (sizes.index(L) - 1.5) * 0.16
        for k in range(4):
            errorbar(
                axes[1],
                k + offset,
                c["metrics"][f"p{k}"],
                fmt="o",
                color=color,
                label=f"L={L}" if k == 0 else None,
                ms=4,
            )
        errorbar(axes[2], L, c["metrics"]["S_grain"], fmt="o", color=color)
    axes[0].axhline(17 / 8, color=".3", ls="--", label="$17/8$ limit")
    axes[0].set(xlabel="$L$", ylabel="Mean height", xscale="log", ylim=(1.95, 2.14))
    axes[0].legend(loc="lower right")
    axes[1].set(xticks=range(4), xlabel="Stable height", ylabel="Checkpoint frequency")
    axes[1].legend(loc="upper left")
    axes[2].plot(
        sizes,
        [condition("baseline", L)["S_prediction_grain"] for L in sizes],
        "--",
        color=".3",
        label="Sparse prediction",
    )
    axes[2].set(xlabel="$L$", ylabel="Mean $S$ per grain", xscale="log", yscale="log")
    axes[2].legend()
    for ax in [axes[0], axes[2]]:
        ax.xaxis.set_major_locator(FixedLocator(sizes))
        ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.xaxis.set_minor_locator(NullLocator())
    save(fig, "baseline")


def sampling_figure():
    e = load("ensemble")
    fig, axes = plt.subplots(2, 2, figsize=(7, 3.7))
    for col, name in enumerate(["height", "p3"]):
        for j, b in enumerate([4096, 8192, 16384]):
            time = next(
                r
                for r in e["time_block_sensitivity"]
                if r["observable"] == name and r["block_grains"] == b
            )
            errorbar(axes[0, col], j, time["time"], fmt="o", color=COLORS["baseline"])
        errorbar(axes[0, col], 3, e["ages"][-1][name], fmt="s", color=COLORS["biased"])
        axes[0, col].set(
            xticks=range(4),
            xticklabels=["4096", "8192", "16384", "Ensemble"],
            xlabel="Time block (grains) or 100 chains",
            ylabel="Mean height" if name == "height" else "Fraction at height 3",
        )
    # Explicit setters keep scientific symbols out of dynamic keyword construction.
    axes[0, 1].set_ylabel("Fraction at height 3")
    for L, color in [(32, COLORS["baseline"]), (64, COLORS["biased"])]:
        for col, obs in enumerate(["height", "S"]):
            with np.load(AN / f"acf_baseline_L{L}_{obs}.npz") as d:
                first = 1 if obs == "S" else 0
                axes[1, col].plot(
                    d["lag_grains"][first:],
                    d["rho"][first:],
                    color=color,
                    label=f"L={L}",
                )
            axes[1, col].set(
                xlim=(0, 1600 if obs == "height" else 40),
                xlabel="Lag (grains)",
                ylabel=f"ACF: {obs}",
            )
            axes[1, col].axhline(0, color=".4", lw=0.6)
            axes[1, col].legend()
    save(fig, "sampling")


def distribution_figures():
    """Plot inclusive CCDFs and supplementary PMFs from integer distributions."""
    fig, axes = plt.subplots(2, 2, figsize=(7, 3.7))
    pmf_fig, pmf_axes = plt.subplots(2, 2, figsize=(7, 3.7))
    for ax, pa, name in zip(axes.ravel(), pmf_axes.ravel(), SYMBOL):
        for L, color in zip([8, 16, 32, 64], SIZECOLORS):
            ccdf(ax, "baseline", L, name, color=color, label=f"L={L}")
            with np.load(AN / "distributions" / f"baseline_L{L}_{name}.npz") as d:
                x, p = d["x"], d["pmf"]
                keep = x > 0
                edges = np.unique(
                    np.r_[
                        0.5,
                        np.ceil(np.geomspace(1, x.max() + 1, 32)) - 0.5,
                        x.max() + 0.5,
                    ]
                )
                mass, _ = np.histogram(x[keep], bins=edges, weights=p[keep])
                density = mass / np.diff(edges)
                centers = np.sqrt(np.maximum(edges[:-1], 0.5) * edges[1:])
                use = density > 0
                pa.plot(
                    centers[use], density[use], ".-", color=color, label=f"L={L}", ms=3
                )
                np.savez_compressed(
                    AN / "distributions" / f"binned_L{L}_{name}.npz",
                    edges=edges,
                    density=density,
                )
            pa.set(
                xscale="log",
                yscale="log",
                xlabel=SYMBOL[name],
                ylabel="Probability / bin width",
            )
        ax.legend()
        pa.legend()
    save(fig, "distributions")
    save(pmf_fig, "supplement_pmf")


def fit_figure():
    """Display pooled observations and the mean of separately fitted seed PMFs."""
    fits = load("fits")
    fig, axes = plt.subplots(2, 2, figsize=(7, 3.7))
    for ax, name in zip(axes.ravel(), SYMBOL):
        records = [
            r
            for r in fits
            if r["L"] == 64 and r["observable"] == name and r["xmin_factor"] == 1
        ]
        base = records[0]
        with np.load(AN / "distributions" / f"baseline_L64_{name}.npz") as d:
            keep = (d["x"] >= base["xmin"]) & (d["x"] <= base["xmax"])
            x, p = d["x"][keep], d["pmf"][keep]
            p = p / p.sum()
            inclusive_ccdf(
                ax, x, np.cumsum(p[::-1])[::-1], color="black", label="Observed", lw=2
            )
        for record, color, ls, label in zip(
            records,
            ["#ad3d45", "#2b8667", "#235789"],
            ["--", "-.", ":"],
            ["Power", "Cutoff power", "Exponential"],
        ):
            if record["status"] != "ok":
                continue
            masses = []
            for f in record["seed_fits"]:
                x, p = fitted_pmf(f)
                masses.append(p)
            mean_p = np.mean(masses, axis=0)
            inclusive_ccdf(
                ax, x, np.cumsum(mean_p[::-1])[::-1], color=color, ls=ls, label=label
            )
        ax.set(
            xscale="log",
            yscale="log",
            xlabel=SYMBOL[name],
            ylabel="CCDF on fitted support",
            ylim=(1e-6, 1.1),
        )
        ax.set_xlim(
            base["xmin"], min(base["xmax"], max(base["observed_max"], base["xmin"] + 1))
        )
        ax.legend()
    save(fig, "fits")


def correlation_figure():
    """Show seed-average ranks, pooled joint counts and size/boundary strata."""
    fig, axes = plt.subplots(2, 2, figsize=(7, 4.2))
    names = ["S", "A", "D", "ell"]
    matrix = np.eye(4)
    for row in load("correlations"):
        if row["L"] == 64:
            i, j = [names.index(n) for n in row["pair"]]
            matrix[i, j] = matrix[j, i] = row["interval"]["mean"]
    axes[0, 0].imshow(matrix, vmin=0, vmax=1, cmap="Blues", aspect="auto")
    for i in range(4):
        for j in range(4):
            axes[0, 0].text(
                j,
                i,
                f"{matrix[i,j]:.3f}",
                ha="center",
                va="center",
                color="white" if matrix[i, j] > 0.7 else "black",
            )
    axes[0, 0].set(
        xticks=range(4),
        yticks=range(4),
        xticklabels=["S", "A", "D", "$\\ell$"],
        yticklabels=["S", "A", "D", "$\\ell$"],
        title="Spearman, $S>0$ (includes $D=0$)",
    )
    e = pooled("baseline", 64)
    e = e[e[:, 0] > 0]
    for ax, i, j in [(axes[0, 1], 0, 1), (axes[1, 0], 1, 3)]:
        hb = ax.hexbin(
            np.log10(e[:, i]),
            np.log10(e[:, j]),
            gridsize=48,
            mincnt=1,
            bins="log",
            cmap="viridis",
        )
        fig.colorbar(hb, ax=ax, label="Events / hexagon", fraction=0.045, pad=0.02)
        ax.set(
            xlabel=f"log10 {names[i]}",
            ylabel="log10 reach" if j == 3 else f"log10 {names[j]}",
        )
    rows = [r for r in load("boundary") if r["L"] == 64]
    bands = [(0, 4), (4, 16), (16, 32)]
    sizes = [1, 16, 128, 1024]
    for (lo, hi), color in zip(bands, ["#c07a1c", "#235789", "#2b8667"]):
        means = []
        errors = []
        for sz in sizes:
            vals = [
                r["p_loss"]
                for r in rows
                if r["boundary_low"] == lo
                and r["size_low"] == sz
                and r["p_loss"] is not None
            ]
            ci = mean_interval(vals)
            means.append(ci["mean"])
            errors.append(ci["high"] - ci["mean"])
        axes[1, 1].errorbar(
            range(4),
            means,
            yerr=errors,
            fmt="o-",
            capsize=2,
            color=color,
            label=f"{lo} <= b < {hi}",
        )
    axes[1, 1].set(
        xticks=range(4),
        xticklabels=["1-15", "16-127", "128-1023", "1024+"],
        xlabel="Topplings S band",
        ylabel="$P(D>0\\mid S,b)$",
        ylim=(-0.025, 1.05),
    )
    axes[1, 1].legend(fontsize=8)
    save(fig, "correlations")
    # Additional joint plot preserves zero loss on an explicit log1p scale.
    fig, ax = plt.subplots(figsize=(5, 3.8))
    hb = ax.hexbin(
        np.log10(e[:, 0]),
        np.log10(1 + e[:, 2]),
        gridsize=55,
        mincnt=1,
        bins="log",
        cmap="viridis",
    )
    fig.colorbar(hb, ax=ax, label="Events / hexagon")
    ax.set(
        xlabel="log10 S",
        ylabel="log10(1 + D)",
        title="$L=64$, all nonzero avalanches, zero loss retained",
    )
    save(fig, "supplement_size_loss")


def driving_figure():
    fig, axes = plt.subplots(2, 2, figsize=(7, 3.7))
    q = driving(Graph(64, 64), 0.9).reshape(64, 64)
    im = axes[0, 0].imshow(q * 64**2, cmap="magma", origin="lower")
    axes[0, 0].set(
        xlabel="Column", ylabel="Row", title="Input probability / uniform probability"
    )
    fig.colorbar(im, ax=axes[0, 0], label="$q(x)L^2$", shrink=0.85)
    for L, color, offset in [(32, SIZECOLORS[2], -0.07), (64, SIZECOLORS[3], 0.07)]:
        record = next(
            r for r in load("extensions") if r["model"] == "biased" and r["L"] == L
        )
        for k in range(4):
            ci = {
                key: value * 1000
                for key, value in record["metrics"][f"p{k}"].items()
                if key in ["mean", "low", "high"]
            }
            errorbar(
                axes[0, 1],
                k + offset,
                ci,
                fmt="o",
                color=color,
                label=f"L={L}" if k == 0 else None,
            )
    axes[0, 1].axhline(0, color=".2", ls="--")
    axes[0, 1].set(
        xticks=range(4),
        xlabel="Stable height",
        ylabel="Biased - uniform frequency ($10^{-3}$)",
    )
    axes[0, 1].legend()
    for model in ["baseline", "biased"]:
        ccdf(axes[1, 0], model, 64, "S", color=COLORS[model], label=LABEL[model])
        with np.load(AN / "distributions" / f"{model}_L64_D.npz") as d:
            keep = d["x"] > 0
            x = d["x"][keep]
            cc = d["ccdf"][keep]
            cc /= cc[0]
            inclusive_ccdf(axes[1, 1], x, cc, color=COLORS[model], label=LABEL[model])
    axes[1, 0].legend()
    axes[1, 1].legend()
    axes[1, 1].set(
        xscale="log",
        yscale="log",
        xlabel="Loss D",
        ylabel="$P(D\\geq d\\mid D>0)$",
        ylim=(1e-6, 1.1),
    )
    save(fig, "driving")


def cylinder_figure():
    fig, axes = plt.subplots(2, 2, figsize=(7, 3.7))
    for col, name in enumerate(["S", "A"]):
        for model in ["baseline", "cylinder"]:
            for L, ls in [(32, "--"), (64, "-")]:
                ccdf(
                    axes[0, col],
                    model,
                    L,
                    name,
                    color=COLORS[model],
                    ls=ls,
                    label=f"{'Open' if model=='baseline' else 'Cylinder'}, L={L}",
                )
        axes[0, col].legend(fontsize=8)
    for model, offset in [("baseline", -0.1), ("cylinder", 0.1)]:
        for k, L in enumerate([32, 64]):
            errorbar(
                axes[1, 0],
                k + offset,
                condition(model, L)["metrics"]["height"],
                fmt="o",
                color=COLORS[model],
                label=LABEL[model] if k == 0 else None,
            )
        with np.load(AN / "distributions" / f"{model}_L64_D.npz") as d:
            keep = d["x"] > 0
            x = d["x"][keep]
            cc = d["ccdf"][keep]
            cc /= cc[0]
            inclusive_ccdf(axes[1, 1], x, cc, color=COLORS[model], label=LABEL[model])
    axes[1, 0].set(
        xticks=[0, 1],
        xticklabels=["32", "64"],
        xlabel="$L$",
        ylabel="Mean stable height",
    )
    axes[1, 0].legend()
    axes[1, 1].set(
        xscale="log",
        yscale="log",
        xlabel="Loss D",
        ylabel="$P(D\\geq d\\mid D>0)$",
        ylim=(1e-6, 1.1),
    )
    axes[1, 1].legend()
    save(fig, "cylinder")


def batch_figure():
    """Compare original events, batches and grouped sequential controls."""
    fig, axes = plt.subplots(2, 2, figsize=(7, 3.7))
    base = pooled("baseline", 64)
    batch = pooled("batch", 64)
    grouped = base[:, :4].reshape(-1, 4, 4).sum(axis=1)
    for ax, name, j in [
        (axes[0, 0], "S", 0),
        (axes[0, 1], "D", 2),
        (axes[1, 0], "A", 1),
    ]:
        for e, label, color, ls in [
            (base, "Single grain", COLORS["baseline"], "-"),
            (batch, "Batch m=4", COLORS["batch"], "-"),
            (
                grouped,
                "Sum of four sequential" if name == "A" else "Grouped sequential",
                "#c07a1c",
                "--",
            ),
        ]:
            x, _, c = histogram(e[e[:, 0] > 0, j])
            keep = x > 0
            inclusive_ccdf(ax, x[keep], c[keep], label=label, color=color, ls=ls)
        ax.set(
            xscale="log",
            yscale="log",
            xlabel=SYMBOL[name],
            ylabel="$P(X\\geq x\\mid S>0)$",
            ylim=(1e-6, 1.1),
        )
        ax.legend(fontsize=8)
    for model, offset in [("baseline", -0.12), ("batch", 0.12)]:
        for i, metric in enumerate(["p_trigger", "p_loss"]):
            errorbar(
                axes[1, 1],
                i + offset,
                condition(model, 64)["metrics"][metric],
                fmt="o",
                color=COLORS[model],
                label=LABEL[model] if i == 0 else None,
            )
    axes[1, 1].set(
        xticks=[0, 1],
        xticklabels=["S > 0", "D > 0"],
        ylabel="Probability per event",
        ylim=(0, 1),
    )
    axes[1, 1].legend()
    save(fig, "batch")


def main():
    style()
    for f in [
        pilot_figure,
        baseline_figure,
        sampling_figure,
        distribution_figures,
        fit_figure,
        correlation_figure,
        driving_figure,
        cylinder_figure,
        batch_figure,
    ]:
        f()
        print(f.__name__, flush=True)


if __name__ == "__main__":
    main()
