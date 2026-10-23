"""Compare complete event streams with independent geometry and actual mass."""
import unittest
import numpy as np
from sandpile.fast import run
from sandpile.model import Graph
from array_oracle import stabilize


class StreamOracle(unittest.TestCase):
    def test_independent_stream_events_and_checkpoints(self):
        rng = np.random.default_rng(72011)
        geometries = [
            (1, 1, False),
            (1, 5, False),
            (4, 1, False),
            (3, 5, False),
            (1, 3, True),
            (3, 4, True),
            (8, 8, False),
            (8, 8, True),
        ]
        for rows, cols, cylinder in geometries:
            for m in (1, 4):
                with self.subTest(rows=rows, cols=cols, cylinder=cylinder, m=m):
                    initial = rng.integers(4, size=(rows, cols), dtype=np.int64)
                    sources = rng.integers(rows * cols, size=(64, m))
                    sources[:2, :] = 0  # Repeated coordinates and boundary inputs.
                    sources[2, :] = cols - 1  # Periodic seam when applicable.
                    graph = Graph(rows, cols, "cylinder" if cylinder else "open")
                    actual, events, frequencies, last_u = run(
                        initial, graph, sources, offset=3, stride=7
                    )
                    expected = initial.copy()
                    expected_events = []
                    expected_frequencies = []
                    for index, sites in enumerate(sources, start=4):
                        expected, u, event = stabilize(expected, sites, cylinder)
                        expected_events.append(event)
                        if index % 7 == 0:
                            expected_frequencies.append(
                                np.bincount(expected.ravel(), minlength=4)
                            )
                    np.testing.assert_array_equal(actual, expected)
                    np.testing.assert_array_equal(events, expected_events)
                    np.testing.assert_array_equal(frequencies, expected_frequencies)
                    np.testing.assert_array_equal(last_u, u)


if __name__ == "__main__":
    unittest.main()
