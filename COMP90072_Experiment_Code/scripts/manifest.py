"""Create a compact dependency manifest with hashes and tested generation commands."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sandpile.io import atomic_json, sha256, now


def report_source(path, seen=None):
    """Read the teacher-template input tree for numeric-macro provenance."""
    seen = set() if seen is None else seen
    path = Path(path).resolve()
    if path in seen:
        return ""
    seen.add(path)
    source = path.read_text()

    def expand(match):
        child = path.parent / match.group(1)
        if not child.suffix:
            child = child.with_suffix(".tex")
        return report_source(child, seen)

    return re.sub(r"\\(?:input|include)\{([^}]+)\}", expand, source)


def main():
    inputs = []
    for path in sorted(Path("data").glob("*_v1/*/metadata.json")):
        meta = json.loads(path.read_text())
        if meta["status"] != "complete":
            raise RuntimeError(f"Incomplete run in retained data: {path}")
        inputs.append({"id": str(path), "sha256": sha256(path), "kind": "run metadata"})
        for chunk in meta["chunks"]:
            p = path.parent / chunk["file"]
            if sha256(p) != chunk["sha256"]:
                raise ArithmeticError(f"Raw hash mismatch: {p}")
            inputs.append(
                {
                    "id": str(p),
                    "sha256": chunk["sha256"],
                    "kind": "event chunk",
                    "stage": chunk["stage"],
                }
            )
        for name in ["initial.npz", "production_start.npz", "checkpoint.npz"]:
            p = path.parent / name
            inputs.append({"id": str(p), "sha256": sha256(p), "kind": name})
    for pattern in [
        "configs/*.json",
        "sandpile/*.py",
        "sandpile/*.c",
        "scripts/*.py",
        "tests/*.py",
        "review_tools/*.py",
        "report/*.tex",
        "report/biblio.bib",
        "report/LICENSE",
        "report/README.txt",
        "report/figures/uom_banner.pdf",
        "requirements*.txt",
        "README.md",
        "PROJECT_STATUS.md",
        "docs/*.md",
    ]:
        for p in sorted(Path(".").glob(pattern)):
            inputs.append(
                {"id": str(p), "sha256": sha256(p), "kind": "configuration/source"}
            )
    for p in [
        Path("logs/benchmark.json"),
        Path("logs/production_timing.json"),
        Path("logs/environment.json"),
        Path("logs/validation_final.txt"),
        Path("logs/smoke.json"),
        Path("logs/pdf_build.json"),
        Path("logs/dependency_check.txt"),
        Path("logs/final_environment.json"),
    ]:
        if p.exists():
            inputs.append(
                {
                    "id": str(p),
                    "sha256": sha256(p),
                    "kind": "executed validation/timing",
                }
            )
    for pattern in [
        "logs/pro_review*.json",
        "logs/pre_review_manifest.json",
        "logs/independent_replay.*",
        "logs/benchmark_original.json",
        "logs/benchmark_post_review.txt",
    ]:
        for p in sorted(Path(".").glob(pattern)):
            inputs.append(
                {"id": str(p), "sha256": sha256(p), "kind": "post-review validation"}
            )
    for pattern in [
        "logs/template_*.json",
        "logs/validation_template.txt",
        "logs/smoke_template_stdout.txt",
        "logs/template_handoff_compile.txt",
        "logs/draft_pagination_*.json",
        "logs/draft_pagination_plots.txt",
        "logs/validation_draft_pagination.txt",
    ]:
        for p in sorted(Path(".").glob(pattern)):
            inputs.append(
                {
                    "id": str(p),
                    "sha256": sha256(p),
                    "kind": "template migration validation",
                }
            )
    artifacts = []
    for p in sorted(Path("analysis").glob("*.json")):
        if p.name == "report_manifest.json":
            continue
        if p.name in ["pilot.json"]:
            command = "python3 scripts/pilot.py"
            cohort = "pilot_v1"
        elif p.name == "confirmation.json":
            command = "python3 scripts/confirmation.py"
            cohort = "confirmation_v1"
        elif p.name == "ensemble_raw.json":
            command = "python3 scripts/ensemble.py"
            cohort = "ensemble_v1"
        elif p.name == "upper_limit_sensitivity.json":
            command = "python3 scripts/upper_limit_sensitivity.py"
            cohort = "full_v1"
        else:
            command = "python3 -m sandpile.analysis configs/full.json"
            cohort = "full_v1"
        artifacts.append(
            {
                "output": str(p),
                "sha256": sha256(p),
                "command": command,
                "input_ids": [
                    x["id"]
                    for x in inputs
                    if (
                        f"data/{cohort}/" in x["id"]
                        or p.name == "ensemble.json"
                        and "data/ensemble_v1/" in x["id"]
                    )
                    and x["kind"] in ["run metadata", "event chunk"]
                ],
                "settings": (
                    "configs/post_review.json.upper_limit_sensitivity; post-review diagnostic, primary fits unchanged"
                    if p.name == "upper_limit_sensitivity.json"
                    else "configs/full.json.analysis; report Section 4.4; filters recorded in each artifact"
                ),
            }
        )
    plot_dependencies = {
        "pilot": ["analysis/pilot.json", "data/pilot_v1/*/production_*.npz"],
        "baseline": ["analysis/summary.json"],
        "sampling": ["analysis/ensemble.json", "analysis/acf_baseline_*.npz"],
        "distributions": ["analysis/distributions/baseline_*.npz"],
        "fits": ["analysis/fits.json", "data/full_v1/baseline_L64_*/production_*.npz"],
        "correlations": [
            "analysis/correlations.json",
            "analysis/boundary.json",
            "data/full_v1/baseline_L64_*/production_*.npz",
        ],
        "driving": [
            "analysis/extensions.json",
            "analysis/distributions/biased_*.npz",
            "analysis/distributions/baseline_*.npz",
        ],
        "cylinder": [
            "analysis/summary.json",
            "analysis/distributions/cylinder_*.npz",
            "analysis/distributions/baseline_*.npz",
        ],
        "batch": [
            "analysis/coupling.json",
            "data/full_v1/batch_L64_*/production_*.npz",
            "data/full_v1/baseline_L64_*/production_*.npz",
        ],
        "performance_table": ["logs/benchmark.json"],
        "baseline_table": ["analysis/summary.json"],
        "extensions_table": ["analysis/summary.json"],
        "fits_table": ["analysis/fits.json"],
        "summary": ["analysis/summary.json"],
        "supplement_pmf": ["analysis/distributions/binned_*.npz"],
        "supplement_size_loss": ["data/full_v1/baseline_L64_*/production_*.npz"],
    }
    for p in sorted(Path("report/generated").glob("*")):
        if not p.is_file():
            continue
        command = (
            "python3 -m sandpile.plots"
            if p.suffix == ".png"
            else "python3 -m sandpile.report_artifacts"
        )
        artifacts.append(
            {
                "output": str(p),
                "sha256": sha256(p),
                "command": command,
                "dependencies": plot_dependencies.get(
                    p.stem,
                    [
                        "analysis/*.json",
                        "logs/benchmark.json",
                        "logs/production_timing.json",
                        "report/generated/number_sources.json",
                    ],
                ),
                "input_ids": [
                    x["id"]
                    for x in inputs
                    if (
                        "data/pilot_v1/" in x["id"]
                        if p.stem == "pilot"
                        else "data/full_v1/" in x["id"]
                        or "data/ensemble_v1/" in x["id"]
                        or "data/confirmation_v1/" in x["id"]
                    )
                    and x["kind"] in ["run metadata", "event chunk"]
                ],
                "filters": "Each figure caption and the generating function in sandpile/plots.py specify sample and model; S>0 retains D=0 unless D>0 is explicit.",
            }
        )
    for p in sorted(Path("analysis").rglob("*.npz")):
        artifacts.append(
            {
                "output": str(p),
                "sha256": sha256(p),
                "command": "python3 -m sandpile.plots"
                if p.name.startswith("binned")
                else "python3 -m sandpile.analysis configs/full.json",
                "dependencies": "matching full_v1 model/size raw chunks; settings in configs/full.json",
            }
        )
    for pdf in [Path("report/main.pdf"), Path("report/final_report.pdf")]:
        if not pdf.exists():
            continue
        artifacts.append(
            {
                "output": str(pdf),
                "sha256": sha256(pdf),
                "command": "python3 scripts/build_report.py",
                "dependencies": [
                    "report/main.tex",
                    "report/preamble.tex",
                    "report/cover.tex",
                    "report/abstract.tex",
                    "report/chapter*.tex",
                    "report/biblio.bib",
                    "report/figures/uom_banner.pdf",
                    "report/generated/*",
                ],
            }
        )
    tex = report_source("report/main.tex")
    numbers = json.loads(Path("report/generated/number_sources.json").read_text())
    used = sorted(set(re.findall(r"\\R\{([^}]+)\}", tex)))
    missing = set(used) - numbers.keys()
    if missing:
        raise ArithmeticError(f"Undefined numeric macros: {missing}")
    atomic_json(
        "analysis/report_manifest.json",
        {
            "schema": "report-provenance-v1",
            "utc": now(),
            "inputs": inputs,
            "artifacts": artifacts,
            "report_numbers": {k: numbers[k] for k in used},
            "raw_data_policy": "No pilot, smoke or confirmation data substituted for frozen primary production.",
            "stationarity_conditions": "Core finite-graph proofs and sparse benchmarks distinguished from observed means.",
            "numeric_constants": "Model thresholds/geometry, handout test and cylinder closed form are derived or specified constants; see tests and equations, not Monte Carlo estimates.",
        },
    )
    print(
        f"Manifest: {len(inputs)} hashed inputs, {len(artifacts)} artifacts, {len(used)} report numeric macros."
    )


def verify():
    """Verify the delivered dependency/output snapshot without rewriting it."""
    manifest = json.loads(Path("analysis/report_manifest.json").read_text())
    count = 0
    for group, field in [("inputs", "id"), ("artifacts", "output")]:
        for row in manifest[group]:
            path = Path(row[field])
            if not path.is_file() or sha256(path) != row["sha256"]:
                raise ArithmeticError(f"Manifest mismatch: {path}")
            count += 1
    print(f"Verified {count} input/artifact hashes; no mismatches.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify",
        action="store_true",
        help="check an existing manifest without rewriting it",
    )
    if parser.parse_args().verify:
        verify()
    else:
        main()
