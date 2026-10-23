"""Follow the corrected 3-by-3 handout example through all three implementations."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from sandpile import engine, fast, reference
from sandpile.model import Graph


def main():
    graph = Graph(3, 3)
    before_input = np.array([[1, 3, 3], [2, 3, 2], [2, 1, 1]], dtype=np.int64)
    source = [4]  # Row 1, column 1 in zero-based, row-major indexing.
    expected_grid = np.array([[2, 1, 1], [3, 2, 0], [2, 2, 2]])
    expected_observables = [4, 4, 4, 3]  # S, A, D, reach.

    for name, stabilize in [
        ("elementary scan", reference.stabilize),
        ("Python queue", engine.stabilize),
        ("C queue", fast.stabilize),
    ]:
        stable_grid, odometer, observables = stabilize(before_input, graph, source)
        np.testing.assert_array_equal(stable_grid, expected_grid)
        np.testing.assert_array_equal(observables, expected_observables)
        print(f"{name}: S, A, D, reach = {observables.tolist()}")
    print("Final grid:\n", stable_grid)
    print("Topplings per site:\n", odometer)


if __name__ == "__main__":
    main()
