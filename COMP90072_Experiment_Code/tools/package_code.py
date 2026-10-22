"""Package a source handoff, excluding generated runs and local environments."""

import argparse
import hashlib
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


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="root of the readable code handoff")
    parser.add_argument(
        "--output", type=Path, required=True, help="ZIP outside the source directory"
    )
    args = parser.parse_args()
    source = args.source.resolve()
    target = args.output.resolve()
    if target.is_relative_to(source):
        raise ValueError("Write the archive outside its source directory")
    files = []
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if not path.is_file() or any(part in EXCLUDED for part in relative.parts):
            continue
        if relative.as_posix().startswith("report/generated/"):
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
        if relative.as_posix() != "FILES.sha256":
            files.append(path)
    files.sort()
    checksums = source / "FILES.sha256"
    checksums.write_text(
        "".join(
            f"{digest(path)}  {path.relative_to(source).as_posix()}\n" for path in files
        )
    )
    files.append(checksums)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files):
            name = "COMP90072_Experiment_Code/" + path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ArithmeticError("ZIP CRC failed")
        for path in files:
            name = "COMP90072_Experiment_Code/" + path.relative_to(source).as_posix()
            if hashlib.sha256(archive.read(name)).hexdigest() != digest(path):
                raise ArithmeticError(f"Archive copy differs: {path}")
    metadata = {
        "path": str(args.output),
        "bytes": target.stat().st_size,
        "sha256": digest(target),
        "files": len(files),
        "zip_crc": "passed",
        "raw_event_files_included": False,
        "per_file_hashes_checked": True,
    }
    target.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )
    target.with_suffix(".zip.sha256").write_text(
        metadata["sha256"] + "  " + target.name + "\n"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
