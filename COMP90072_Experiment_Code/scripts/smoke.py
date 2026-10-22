"""Fresh end-to-end reproducibility check on all models, with no production input."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MPLCONFIGDIR", str(Path("tmp/matplotlib").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sandpile import fast
from sandpile.experiment import run_config, read_events
from sandpile.analysis import metrics_for_run
from sandpile.statistics import histogram, discrete_fit
from sandpile.io import atomic_json, sha256, now
from build_report import tectonic_executable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="check simulations, statistics and plotting without a TeX installation",
    )
    args = parser.parse_args()
    pdf_hash = None
    start = time.perf_counter()
    cfg = json.loads(Path("configs/smoke.json").read_text())
    build = fast.build(force=True)
    checked = []
    with tempfile.TemporaryDirectory(prefix="comp90072_clean_smoke_") as folder:
        root = Path(folder)
        for version in ["one", "two"]:
            cfg["output"] = str(root / version)
            path = root / f"{version}.json"
            path.write_text(json.dumps(cfg))
            run_config(path)
        rows = []
        for model in cfg["conditions"]:
            for seed in cfg["seeds"]:
                run = f"{model}_L8_s{seed}"
                a = read_events(root / "one" / run)
                b = read_events(root / "two" / run)
                for key in a:
                    np.testing.assert_array_equal(a[key], b[key])
                vals = metrics_for_run(
                    a["events"], a["frequencies"], 8, 4 if model == "batch" else 1
                )
                x, p, c = histogram(a["events"][:, 0])
                np.testing.assert_allclose(p.sum(), 1)
                fit = discrete_fit(
                    a["events"][:, 0], 1, 64, "cutoff", minimum_count=100
                )
                if fit["status"] != "ok":
                    raise ArithmeticError("Smoke fit failed")
                checked.append(run)
                rows.append({"run": run, "summary": vals, "fit": fit})
        plt.figure(figsize=(5, 3))
        plt.bar(range(len(rows)), [r["summary"]["S_grain"] for r in rows])
        plt.xlabel("Smoke run index")
        plt.ylabel("Mean S per grain")
        plt.title("SMOKE ONLY: not production evidence")
        plt.tight_layout()
        plt.savefig(root / "smoke.png", dpi=150)
        plt.close()
        if not args.skip_pdf:
            tex = r"""\documentclass[11pt]{article}
    \usepackage[T1]{fontenc}
    \usepackage{graphicx}
    \begin{document}
    \section*{Clean reproducibility smoke check}
    Eight fresh runs cover uniform input, full-support bias, cylindrical boundaries,
    and matched four-grain batches. A second fresh execution agrees exactly in all
    event arrays and checkpoint frequencies. This page is not production evidence.
    \begin{center}\includegraphics[width=.9\linewidth]{smoke.png}\end{center}
    \end{document}
    """
            (root / "smoke.tex").write_text(tex)
            result = subprocess.run(
                [tectonic_executable(), "-X", "compile", "smoke.tex"],
                cwd=root,
                text=True,
                capture_output=True,
            )
            Path("logs/smoke_latex.txt").write_text(result.stdout + result.stderr)
            result.check_returncode()
            pdf_hash = sha256(root / "smoke.pdf")

    atomic_json(
        "logs/smoke.json",
        {
            "utc": now(),
            "status": "passed",
            "seconds": time.perf_counter() - start,
            "command": "python3 scripts/smoke.py"
            + (" --skip-pdf" if args.skip_pdf else ""),
            "fresh_runs_per_execution": len(checked),
            "executions": 2,
            "identical_arrays": True,
            "models": checked,
            "compiler": build,
            "summary_and_fit_checks": rows,
            "temporary_pdf_compiled_sha256": pdf_hash,
            "pdf_compiled": not args.skip_pdf,
            "temporary_outputs": "removed after successful comparison; primary raw data untouched",
        },
    )
    print(
        "Clean smoke passed: all models, two fresh executions, statistics and plot."
        + (" PDF skipped by request." if args.skip_pdf else " PDF compiled.")
    )


if __name__ == "__main__":
    main()
