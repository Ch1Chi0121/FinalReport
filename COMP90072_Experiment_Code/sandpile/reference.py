"""Independent elementary-topple scanner, deliberately unoptimized.

Each iteration scans coordinates and transfers one grain in each direction.
It shares neither queue scheduling nor neighbour tables with production code.
Alternative schedules use a caller-owned RNG, never the driving stream.
"""
import numpy as np
from .model import check_grid, metrics


def stabilize(grid, graph, sources, schedule="scan", rng=None):
    """Add sources (flat indices with replacement); return grid,u,metrics."""
    h = check_grid(grid, graph)
    for x in sources:
        if not 0 <= x < graph.n:
            raise ValueError("Source outside grid")
        h.flat[x] += 1
    u = np.zeros_like(h)
    while True:
        unstable = [
            (i, j) for i in range(graph.rows) for j in range(graph.cols) if h[i, j] >= 4
        ]
        if not unstable:
            break
        if schedule == "scan":
            i, j = unstable[0]
        elif schedule == "reverse":
            i, j = unstable[-1]
        elif schedule == "random" and rng is not None:
            i, j = unstable[rng.integers(len(unstable))]
        else:
            raise ValueError("Unknown schedule or missing independent RNG")
        h[i, j] -= 4
        u[i, j] += 1
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ni, nj = i + di, j + dj
            if graph.boundary == "cylinder":
                nj %= graph.cols
            if 0 <= ni < graph.rows and 0 <= nj < graph.cols:
                h[ni, nj] += 1
    return h, u, metrics(graph, u, sources)
