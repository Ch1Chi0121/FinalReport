"""Index result files, their generation commands and the report's numerical sources."""

import argparse
import json
from pathlib import Path
import re
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sandpile.io import atomic_json, check_chunk, now


def report_source(path, seen=None):
    """Expand the active LaTeX inputs once to find numerical macro uses."""
    path = Path(path).resolve()
    seen = set() if seen is None else seen
    if path in seen:
        return ""
    seen.add(path)

    def expand(match):
        child = path.parent / match.group(1)
        if not child.suffix:
            child = child.with_suffix(".tex")
        return report_source(child, seen)

    return re.sub(r"\\(?:input|include)\{([^}]+)\}", expand, path.read_text())


def main():
    runs = []
    for path in sorted(Path("data").glob("*_v1/*/metadata.json")):
        metadata = json.loads(path.read_text())
        if metadata["status"] != "complete":
            raise ValueError(f"Incomplete run: {path}")
        for chunk in metadata["chunks"]:
            check_chunk(path.parent, chunk)
        runs.append({"metadata": str(path), "config": metadata["config"]})

    files = []
    for folder in [
        "data",
        "analysis",
        "report",
        "sandpile",
        "scripts",
        "tests",
        "configs",
    ]:
        for path in sorted(Path(folder).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.name == "report_manifest.json" or path.suffix in {
                ".pyc",
                ".aux",
                ".bbl",
                ".blg",
                ".log",
                ".out",
                ".toc",
                ".xdv",
            }:
                continue
            files.append({"path": str(path), "bytes": path.stat().st_size})

    sources = json.loads(Path("report/generated/number_sources.json").read_text())
    used = set(re.findall(r"\\R\{([^}]+)\}", report_source("report/main.tex")))
    if used - sources.keys():
        raise ValueError(f"Undefined report values: {used - sources.keys()}")
    commands = {
        "primary analysis": "python -m sandpile.analysis configs/full.json",
        "sensitivity": "python scripts/upper_limit_sensitivity.py",
        "figures": "python -m sandpile.plots",
        "tables and numbers": "python -m sandpile.report_artifacts",
        "PDF": "python scripts/build_report.py",
    }
    atomic_json(
        "analysis/report_manifest.json",
        {
            "created_utc": now(),
            "runs": runs,
            "files": files,
            "commands": commands,
            "report_numbers": {key: sources[key] for key in sorted(used)},
            "checks": "File presence/length and built-in NPZ CRCs; numerical checks run in the analysis.",
        },
    )
    print(
        f"Indexed {len(runs)} runs, {len(files)} files and {len(used)} report values."
    )


def verify():
    """Check indexed file lengths and the integrity of saved NPZ archives."""
    index = json.loads(Path("analysis/report_manifest.json").read_text())
    for row in index["files"]:
        path = Path(row["path"])
        if not path.is_file() or path.stat().st_size != row["bytes"]:
            raise ArithmeticError(
                f"Indexed file is missing or has changed length: {path}"
            )
        if path.suffix == ".npz":
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None:
                    raise ArithmeticError(f"Damaged NPZ archive: {path}")
    print(f"Checked {len(index['files'])} file lengths and NPZ archives.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    if parser.parse_args().verify:
        verify()
    else:
        main()
