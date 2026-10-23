"""Active-site queue with exact bulk elementary toppling counts.

Bulk floor(h/4) topplings at one vertex are a legal consecutive schedule.
Abelian uniqueness (Jarai 2018, Thm 2.3) makes this an exact optimization.
"""
from collections import deque
import numpy as np
from .model import check_grid, metrics


def stabilize(grid, graph, sources):
    """Return stable grid, full int64 odometer, and S/A/D/reach for one event."""
    h = check_grid(grid, graph).ravel()
    sources = np.asarray(sources, dtype=np.int64)
    if np.any(sources < 0) or np.any(sources >= graph.n):
        raise ValueError("Source outside grid")
    np.add.at(h, sources, 1)  # Accumulates duplicates; h[sources] += 1 does not.
    neighbours = graph.neighbours()
    active = deque(np.flatnonzero(h >= 4))
    queued = h >= 4
    u = np.zeros(graph.n, dtype=np.int64)
    while active:
        x = active.popleft()
        queued[x] = False
        count = h[x] // 4
        h[x] -= 4 * count
        u[x] += count
        for y in neighbours[x]:
            if y >= 0:
                h[y] += count
                if h[y] >= 4 and not queued[y]:
                    active.append(y)
                    queued[y] = True
    return (
        h.reshape(graph.rows, graph.cols),
        u.reshape(graph.rows, graph.cols),
        metrics(graph, u, sources),
    )
