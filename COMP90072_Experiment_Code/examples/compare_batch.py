"""Check a four-grain batch against the same inputs added one grain at a time."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from sandpile.engine import stabilize
from sandpile.model import Graph


def main():
    graph = Graph(8, 8)
    initial = np.full((8, 8), 3, dtype=np.int64)
    sources = [27, 27, 27, 27]  # A repeated location is intentional.
    batch_grid, batch_odometer, batch_metrics = stabilize(initial, graph, sources)
    sequential_grid = initial.copy()
    summed_odometer = np.zeros_like(initial)
    summed_metrics = np.zeros(4, dtype=np.int64)

    for source in sources:
        sequential_grid, odometer, metrics = stabilize(sequential_grid, graph, [source])
        summed_odometer += odometer
        summed_metrics += metrics

    np.testing.assert_array_equal(batch_grid, sequential_grid)
    np.testing.assert_array_equal(batch_odometer, summed_odometer)
    np.testing.assert_array_equal(batch_metrics[[0, 2]], summed_metrics[[0, 2]])
    assert batch_metrics[1] == np.count_nonzero(summed_odometer)
    assert batch_metrics[1] < summed_metrics[1]
    print("Final grids, odometers, topplings and loss agree exactly.")
    print(
        f"Batch area: {batch_metrics[1]}; sum of sequential areas: {summed_metrics[1]}"
    )
    print(
        "The summed area can count a site more than once; the batch area counts its union."
    )


if __name__ == "__main__":
    main()
