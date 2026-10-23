"""Known discrete distributions, normalization and dependent-series checks."""

import unittest
import numpy as np
from sandpile.statistics import (
    histogram,
    log_binned,
    mean_interval,
    autocorrelation,
    block_means,
    discrete_fit,
    fitted_pmf,
)


class StatisticalTests(unittest.TestCase):
    def test_normalization(self):
        x = np.array([0, 0, 1, 2, 2, 4])
        s, p, c = histogram(x)
        self.assertAlmostEqual(p.sum(), 1)
        self.assertAlmostEqual(c[0], 1)
        np.testing.assert_allclose(c, [1, 4 / 6, 3 / 6, 1 / 6])
        edges = np.array([0, 1, 3, 5])
        d = log_binned(x, edges)
        self.assertAlmostEqual(np.dot(d, np.diff(edges)), 1)

    def test_synthetic_fits(self):
        rng = np.random.default_rng(19812)
        for model, alpha, rate in [
            ("power", 1.7, 0),
            ("exponential", 0, 0.08),
            ("cutoff", 0.8, 0.03),
        ]:
            truth = dict(xmin=2, xmax=100, alpha=alpha, **{"lambda": rate})
            x, p = fitted_pmf(truth)
            self.assertAlmostEqual(p.sum(), 1)
            samples = rng.choice(x, size=100000, p=p)
            fit = discrete_fit(samples, 2, 100, model)
            self.assertEqual(fit["status"], "ok")
            self.assertLess(abs(fit["alpha"] - alpha), 0.1)
            self.assertLess(abs(fit["lambda"] - rate), 0.005)
            self.assertLess(fit["KS"], 0.01)

    def test_sparse_degenerate_and_truncation(self):
        for x in [np.array([], dtype=int), np.ones(1000, dtype=int)]:
            self.assertEqual(discrete_fit(x, 1, 100)["status"], "sparse_or_degenerate")
        with self.assertRaises(ValueError):
            discrete_fit(np.array([1.1, 2.0]), 1, 10)
        fit = discrete_fit(np.tile(np.arange(1, 31), 100), 3, 20)
        self.assertEqual(fit["n"], 1800)
        self.assertAlmostEqual(fit["alpha"], 0, places=5)
        self.assertIsNone(mean_interval([1])["low"])

    def test_dependence(self):
        rng = np.random.default_rng(895)
        white = rng.normal(size=100000)
        _, tau = autocorrelation(white)
        self.assertLess(tau, 1.2)
        ar = np.zeros(100000)
        for i in range(1, len(ar)):
            ar[i] = 0.8 * ar[i - 1] + white[i]
        _, tau = autocorrelation(ar)
        self.assertGreater(tau, 7)
        self.assertLess(tau, 12)
        np.testing.assert_allclose(block_means(np.arange(8), 2), [0.5, 2.5, 4.5, 6.5])


if __name__ == "__main__":
    unittest.main()
