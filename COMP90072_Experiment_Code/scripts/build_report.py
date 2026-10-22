"""Compile the multi-file report, fail on missing references, overflow or >20 pages."""
import argparse
import json
from pathlib import Path
import re
import shutil
import os
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sandpile.io import atomic_json, sha256, now

ROOT = Path(__file__).resolve().parents[1]


def tectonic_executable(explicit=None):
    candidates = [
        explicit,
        os.environ.get("CODEX_TECTONIC_PATH"),
        shutil.which("tectonic"),
        "/Applications/ChatGPT.app/Contents/Resources/tectonic/tectonic",
        "/private/tmp/comp90072-tectonic/tectonic",
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return str(Path(path).resolve())
    raise FileNotFoundError(
        "Install Tectonic 0.17.0 or pass --tectonic /absolute/path/to/tectonic"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tectonic")
    args = parser.parse_args()
    command = [
        tectonic_executable(args.tectonic),
        "-X",
        "compile",
        "--keep-logs",
        "--keep-intermediates",
        "main.tex",
    ]
    result = subprocess.run(
        command, cwd=ROOT / "report", text=True, capture_output=True
    )
    (ROOT / "logs/latex_final.txt").write_text(result.stdout + result.stderr)
    result.check_returncode()
    log = (ROOT / "report/main.log").read_text()
    problems = [
        line
        for line in log.splitlines()
        if re.search(
            r"Overfull|Undefined control|undefined references|undefined citations|Citation .* undefined|Reference .* undefined|Missing character",
            line,
        )
    ]
    if problems:
        raise RuntimeError("LaTeX audit failed: " + "\n".join(problems))
    info = subprocess.check_output(
        ["pdfinfo", str(ROOT / "report/main.pdf")], text=True
    )
    pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    if pages > 20:
        raise RuntimeError(f"Physical page limit exceeded: {pages}")
    shutil.copy2(ROOT / "report/main.pdf", ROOT / "report/final_report.pdf")
    (ROOT / "output/pdf").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT / "report/main.pdf", ROOT / "output/pdf/COMP90072_Completed_Report.pdf"
    )
    atomic_json(
        ROOT / "logs/pdf_build.json",
        {
            "utc": now(),
            "command": command,
            "physical_pages": pages,
            "pdf_sha256": sha256(ROOT / "report/final_report.pdf"),
            "unresolved_references": False,
            "overfull_boxes": False,
            "visual_review": "separately recorded in docs/final_audit.md",
        },
    )
    print(
        f"Compiled main.tex: {pages} physical A4 pages; no unresolved references or overfull boxes. main.pdf, final_report.pdf and the delivery PDF match."
    )


if __name__ == "__main__":
    main()
