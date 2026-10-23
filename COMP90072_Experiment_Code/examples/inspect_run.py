"""Print a few event records and their input sites from a completed run."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sandpile.experiment import read_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="e.g. data/full_v1/baseline_L8_s21001")
    args = parser.parse_args()
    data = read_events(args.run)
    print("event | input sites | S A D reach mass boundary_distance")
    for index, (sources, record) in enumerate(
        zip(data["sources"][:10], data["events"][:10]), 1
    ):
        print(index, sources.tolist(), record.tolist(), sep=" | ")


if __name__ == "__main__":
    main()
