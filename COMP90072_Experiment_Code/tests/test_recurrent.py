"""Tiny exact state-space control, including a potentially periodic chain."""
import itertools
import unittest
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from sandpile.model import Graph
from sandpile.reference import stabilize


class Recurrence(unittest.TestCase):
    def test_uniform_recurrent_for_positive_drive_and_grouping(self):
        states = list(itertools.product(range(4), repeat=4))
        index = {s: i for i, s in enumerate(states)}
        destinations = np.empty((256, 4), dtype=int)
        for i, s in enumerate(states):
            for x in range(4):
                h, _, _ = stabilize(np.array(s).reshape(2, 2), Graph(2, 2), [x])
                destinations[i, x] = index[tuple(h.ravel())]
        reach = np.zeros((256, 256))
        for i in range(256):
            np.add.at(reach[i], destinations[i], 0.25)
        n, labels = connected_components(
            csr_matrix(reach), directed=True, connection="strong"
        )
        closed = []
        for k in range(n):
            members = np.flatnonzero(labels == k)
            if np.all(labels[destinations[members]] == k):
                closed.append(members)
        self.assertEqual(len(closed), 1)
        members = closed[0]
        self.assertEqual(len(members), 192)
        for q in [[0.25] * 4, [0.7, 0.1, 0.1, 0.1]]:
            P = np.zeros((256, 256))
            for i in range(256):
                np.add.at(P[i], destinations[i], q)
            invariant = np.zeros(256)
            invariant[members] = 1 / len(members)
            np.testing.assert_allclose(invariant @ P, invariant, atol=1e-14)
            np.testing.assert_allclose(
                invariant @ np.linalg.matrix_power(P, 4), invariant, atol=1e-14
            )


if __name__ == "__main__":
    unittest.main()
