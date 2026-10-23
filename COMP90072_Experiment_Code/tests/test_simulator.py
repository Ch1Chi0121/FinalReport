"""Local rules, handout example, geometry and Python schedule comparisons."""

import itertools
import unittest
import numpy as np
from sandpile.model import Graph, driving, benchmark, metrics
from sandpile import engine, reference


class Rules(unittest.TestCase):
    def compare(self, h, graph, sources, schedules=False):
        expected = reference.stabilize(h, graph, sources)
        actual = engine.stabilize(h, graph, sources)
        for x, y in zip(expected, actual):
            np.testing.assert_array_equal(x, y)
        final, u, obs = actual
        self.assertTrue(np.all((final >= 0) & (final <= 3)))
        self.assertEqual(int(final.sum()), int(np.sum(h)) + len(sources) - int(obs[2]))
        added = np.bincount(sources, minlength=graph.n)
        np.testing.assert_array_equal(
            final.ravel(), np.asarray(h).ravel() + added - graph.matrix() @ u.ravel()
        )
        self.assertLessEqual(obs[1], obs[0])
        self.assertLessEqual(obs[1], graph.n)
        if schedules:
            for schedule in ["reverse", "random"]:
                alt = reference.stabilize(
                    h, graph, sources, schedule, np.random.default_rng(985)
                )
                for x, y in zip(expected, alt):
                    np.testing.assert_array_equal(x, y)
        return actual

    def test_handout(self):
        h = np.array([[1, 3, 3], [2, 3, 2], [2, 1, 1]])
        final, u, obs = self.compare(h, Graph(3, 3), [4], True)
        np.testing.assert_array_equal(final, [[2, 1, 1], [3, 2, 0], [2, 2, 2]])
        np.testing.assert_array_equal(obs, [4, 4, 4, 3])

    def test_simple_and_degenerate(self):
        for shape in [(1, 1), (1, 5), (5, 1), (2, 5), (5, 5)]:
            g = Graph(*shape)
            for x in [0, g.n // 2, g.n - 1]:
                for value in [0, 3, 12]:
                    h = np.zeros(shape, dtype=np.int64)
                    h.flat[x] = value
                    self.compare(h, g, [x], True)
        for source, loss in [(12, 0), (2, 1), (0, 2)]:
            h = np.zeros((5, 5), dtype=np.int64)
            h.flat[source] = 3
            self.assertEqual(self.compare(h, Graph(5, 5), [source])[2][2], loss)

    def test_exhaustive_2x2(self):
        for heights in itertools.product(range(4), repeat=4):
            for x in range(4):
                self.compare(np.array(heights).reshape(2, 2), Graph(2, 2), [x], True)

    def test_random_bounded(self):
        rng = np.random.default_rng(9321)
        for case in range(1000):
            g = Graph(int(rng.integers(1, 6)), int(rng.integers(1, 6)))
            h = rng.integers(0, 9 if case < 200 else 4, size=(g.rows, g.cols))
            self.compare(h, g, rng.integers(g.n, size=4).tolist(), case < 100)

    def test_cylinder(self):
        with self.assertRaises(ValueError):
            Graph(3, 2, "cylinder")
        for rows in [1, 2, 3, 5]:
            g = Graph(rows, 5, "cylinder")
            for x in range(g.n):
                h = np.zeros((rows, 5), dtype=np.int64)
                h.flat[x] = 3
                _, _, o = self.compare(h, g, [x], True)
                self.assertEqual(o[2], int(x // 5 == 0) + int(x // 5 == rows - 1))
            w = np.repeat([(i + 1) * (rows - i) / 2 for i in range(rows)], 5)
            np.testing.assert_allclose(g.matrix() @ w, 1)
            self.assertAlmostEqual(benchmark(g)["mean_S"], (rows + 1) * (rows + 2) / 12)
        g = Graph(5, 5, "cylinder")
        np.testing.assert_array_equal(g.distances(np.array([14]), [10]), [1])
        np.testing.assert_array_equal(g.boundary_distance([10, 14]), [2, 2])
        h = np.zeros((5, 5), dtype=np.int64)
        h.flat[10] = 3
        final, _, o = self.compare(h, g, [10])
        self.assertEqual(final.flat[14], 1)
        self.assertEqual(o[2], 0)

    def test_drive(self):
        g = Graph(16, 16)
        q = driving(g, 0.9)
        self.assertAlmostEqual(q.sum(), 1)
        self.assertGreater(q.min(), 0)
        np.testing.assert_allclose(driving(g, 0), np.ones(g.n) / g.n)
        rng = np.random.default_rng(783)
        counts = np.bincount(rng.choice(g.n, size=200000, p=q), minlength=g.n)
        # Fixed-seed Pearson discrepancy, generous 6-sigma engineering check.
        chi = float(np.sum((counts - 200000 * q) ** 2 / (200000 * q)))
        self.assertLess(abs(chi - (g.n - 1)), 6 * np.sqrt(2 * (g.n - 1)))

    def test_batch_identities(self):
        rng = np.random.default_rng(174)
        for boundary in ["open", "cylinder"]:
            g = Graph(5, 5, boundary)
            for case in range(100):
                h = rng.integers(0, 4, size=(5, 5))
                sources = [12] * 4 if case == 0 else rng.integers(25, size=4).tolist()
                hb, ub, ob = self.compare(h, g, sources)
                hs = h.copy()
                us = np.zeros_like(h)
                area_sum = 0
                for x in sources:
                    hs, u, o = engine.stabilize(hs, g, [x])
                    us += u
                    area_sum += o[1]
                np.testing.assert_array_equal(hb, hs)
                np.testing.assert_array_equal(ub, us)
                np.testing.assert_array_equal(ob, metrics(g, us, sources))
                self.assertLessEqual(ob[1], area_sum)
                self.compare(h, g, [sources[0]])

    def test_invalid_inputs(self):
        for h in [np.ones((2, 2)) * 0.1, np.full((2, 2), -1), np.full((2, 2), 2**62)]:
            with self.assertRaises((ValueError, OverflowError)):
                engine.stabilize(h, Graph(2, 2), [0])


if __name__ == "__main__":
    unittest.main()
