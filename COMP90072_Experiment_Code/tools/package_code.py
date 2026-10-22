"""Package the source tree without generated runs, binaries or environments."""

import argparse
import json
from pathlib import Path
import zipfile

EXCLUDED = {
    ".venv",
    "__pycache__",
    "build",
    "tmp",
    "data",
    "analysis",
    "logs",
    "output",
    ".git",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, target = args.source.resolve(), args.output.resolve()
    if target.is_relative_to(source):
        raise ValueError("Write the ZIP outside the source folder")
    files = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if not path.is_file() or any(part in EXCLUDED for part in relative.parts):
            continue
        if (
            relative.as_posix().startswith("report/generated/")
            or relative.as_posix() == "FILES.txt"
        ):
            continue
        if path.suffix in {
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
        files.append(path)
    listing = source / "FILES.txt"
    listing.write_text(
        "".join(
            f"{p.relative_to(source).as_posix()} ({p.stat().st_size} bytes)\n"
            for p in files
        )
    )
    files.append(listing)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(
                path, "COMP90072_Experiment_Code/" + path.relative_to(source).as_posix()
            )
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ArithmeticError("Damaged ZIP")
        for path in files:
            name = "COMP90072_Experiment_Code/" + path.relative_to(source).as_posix()
            if archive.read(name) != path.read_bytes():
                raise ArithmeticError(f"ZIP content differs: {name}")
    record = {
        "path": str(args.output),
        "bytes": target.stat().st_size,
        "files": len(files),
        "zip_crc": "passed",
        "file_copies": "matched",
    }
    target.with_suffix(".metadata.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
