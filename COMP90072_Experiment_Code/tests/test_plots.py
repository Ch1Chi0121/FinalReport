"""Check the meaning of the plotted curve, including unobserved thresholds."""
import unittest
import numpy as np
from sandpile.plots import inclusive_ccdf, plt
from sandpile.statistics import histogram


class InclusiveCCDF(unittest.TestCase):
    def test_gapped_support_path(self):
        sample = np.array([1, 1, 3, 7])
        x, _, ccdf = histogram(sample)
        fig, ax = plt.subplots()
        try:
            (line,) = inclusive_ccdf(ax, x, ccdf)
            vertices = line.get_path().vertices
            for threshold in [1.5, 2, 2.5, 4, 5, 6]:
                horizontal = [
                    a[1]
                    for a, b in zip(vertices[:-1], vertices[1:])
                    if a[0] < threshold < b[0] and a[1] == b[1]
                ]
                self.assertEqual(len(horizontal), 1)
                self.assertEqual(horizontal[0], np.mean(sample >= threshold))
            np.testing.assert_array_equal(line.get_ydata(), [1, 0.5, 0.25])
        finally:
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
