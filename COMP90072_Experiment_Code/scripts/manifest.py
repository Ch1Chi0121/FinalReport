"""Index experiment files, generation commands and numerical source keys."""

import argparse
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sandpile.io import atomic_json, check_chunk, now


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
        "results",
        "sandpile",
        "scripts",
        "tests",
        "configs",
    ]:
        for path in sorted(Path(folder).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.name == "results_index.json" or path.suffix == ".pyc":
                continue
            files.append({"path": str(path), "bytes": path.stat().st_size})

    sources = json.loads(Path("results/tables/number_sources.json").read_text())
    commands = {
        "primary analysis": "python -m sandpile.analysis configs/full.json",
        "sensitivity": "python scripts/upper_limit_sensitivity.py",
        "figures": "python -m sandpile.plots",
        "tables and numbers": "python -m sandpile.tables",
    }
    atomic_json(
        "analysis/results_index.json",
        {
            "created_utc": now(),
            "runs": runs,
            "files": files,
            "commands": commands,
            "numerical_sources": sources,
            "checks": "File presence/length and built-in NPZ CRCs; numerical checks run in the analysis.",
        },
    )
    print(
        f"Indexed {len(runs)} runs, {len(files)} files and {len(sources)} numerical values."
    )


def verify():
    """Check indexed file lengths and the integrity of saved NPZ archives."""
    index = json.loads(Path("analysis/results_index.json").read_text())
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
