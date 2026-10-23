"""Graph, drive, observables and deterministic benchmarks.

The assignment uses Delta=-4I+B; all solves below use K=-Delta.
See Jarai (2018), Sections 2.1-2.3, doi:10.1214/14-PS228.
"""
from dataclasses import dataclass
from functools import lru_cache
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve


@dataclass(frozen=True)
class Graph:
    """Lattice geometry with open edges or horizontally periodic columns.

    Sites use row-major flat indices. Each row of neighbours() has four directional
    entries; -1 denotes a sink. Keeping the four directions explicit gives the same
    threshold at an interior site, an edge and a corner.
    """

    rows: int
    cols: int
    boundary: str = "open"

    def __post_init__(self):
        if self.rows < 1 or self.cols < 1:
            raise ValueError("Grid dimensions must be positive")
        if self.boundary not in ("open", "cylinder"):
            raise ValueError("Unknown boundary")
        if self.boundary == "cylinder" and self.cols < 3:
            raise ValueError("Cylinder requires width >=3; degenerate widths rejected")

    @property
    def n(self):
        return self.rows * self.cols

    @lru_cache(maxsize=32)
    def neighbours(self):
        """Return (N,4) int64 directional destinations, -1 for sinks."""
        out = np.full((self.n, 4), -1, dtype=np.int64)
        for x in range(self.n):
            i, j = divmod(x, self.cols)
            for d, (di, dj) in enumerate(((-1, 0), (1, 0), (0, -1), (0, 1))):
                ni, nj = i + di, j + dj
                if self.boundary == "cylinder":
                    nj %= self.cols
                if 0 <= ni < self.rows and 0 <= nj < self.cols:
                    out[x, d] = ni * self.cols + nj
        out.setflags(write=False)
        return out

    def matrix(self):
        """Independent Kronecker construction of symmetric sparse K."""

        def path(n):
            return sparse.diags([np.ones(n - 1), np.ones(n - 1)], [-1, 1], shape=(n, n))

        horizontal = path(self.cols).tolil()
        if self.boundary == "cylinder":
            horizontal[0, -1] = horizontal[-1, 0] = 1
        adjacency = sparse.kron(path(self.rows), sparse.eye(self.cols)) + sparse.kron(
            sparse.eye(self.rows), horizontal
        )
        return (4 * sparse.eye(self.n) - adjacency).tocsr()

    def boundary_distance(self, sites):
        """Nearest dissipative row/edge for each flattened input site."""
        sites = np.asarray(sites, dtype=np.int64)
        i, j = sites // self.cols, sites % self.cols
        b = np.minimum(i, self.rows - 1 - i)
        if self.boundary == "open":
            b = np.minimum(b, np.minimum(j, self.cols - 1 - j))
        return b

    def distances(self, sites, sources):
        """Distance of each site to nearest source, using graph geodesics."""
        sites, sources = np.asarray(sites), np.asarray(sources)
        if len(sources) == 0:
            raise ValueError("Reach requires at least one source")
        di = np.abs(sites[:, None] // self.cols - sources[None, :] // self.cols)
        dj = np.abs(sites[:, None] % self.cols - sources[None, :] % self.cols)
        if self.boundary == "cylinder":
            dj = np.minimum(dj, self.cols - dj)
        return (di + dj).min(axis=1)


def driving(graph, eta=0.0, sigma=None):
    """Return normalized full-support mixture q_eta, including eta=0 limit."""
    if not 0 <= eta < 1:
        raise ValueError("eta must be in [0,1) to guarantee full support")
    if sigma is None:
        sigma = min(graph.rows, graph.cols) / 8
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    i, j = np.indices((graph.rows, graph.cols))
    r2 = (i - (graph.rows - 1) / 2) ** 2 + (j - (graph.cols - 1) / 2) ** 2
    gaussian = np.exp(-r2.ravel() / (2 * sigma * sigma))
    gaussian /= gaussian.sum()
    q = (1 - eta) / graph.n + eta * gaussian
    return q / q.sum()


def benchmark(graph, q=None, m=1):
    """Solve the stationary mean-response equations on this finite graph.

    q is the probability of each input site and m is the grains added per event.
    K v = m q gives expected topplings per site; summing v gives E[S]. The second
    solve, K w = 1, supplies a positive potential used in balance checks. These are
    deterministic benchmarks, separate from the Monte Carlo estimates.
    """
    if q is None:
        q = driving(graph)
    matrix = graph.matrix()
    v = spsolve(matrix, m * q)
    w = spsolve(matrix, np.ones(graph.n))
    residual = float(np.max(np.abs(matrix @ v - m * q)))
    if residual > 1e-10 or np.min(w) <= 0:
        raise ArithmeticError("Invalid sparse benchmark solve")
    return {
        "mean_S": float(v.sum()),
        "residual": residual,
        "potential": w,
        "S_bound": int(np.ceil(3 * w.sum() + m * w.max())),
    }


def check_grid(grid, graph):
    """Validate exact nonnegative integer input and conservative overflow bound."""
    raw = np.asarray(grid)
    if raw.size != graph.n or not np.issubdtype(raw.dtype, np.integer):
        raise ValueError("Grid must contain N integer heights")
    if np.any(raw < 0) or np.max(raw) > 10**9 or graph.n > 10**6:
        raise ValueError("Negative height or input outside supported int64 envelope")
    # Worst supported N and mass are bounded before entry to compiled arithmetic.
    # Production grids are <=4096 sites and stable heights <=3.
    if sum(int(x) for x in raw.ravel()) * graph.n**2 > 2**60:
        raise OverflowError(
            "Conservative toppling/potential bound exceeds int64 envelope"
        )
    return np.array(raw, dtype=np.int64).reshape(graph.rows, graph.cols)


def metrics(graph, odometer, sources):
    """Compute [S, A, D, reach] from one event's complete odometer.

    S counts elementary topplings; A counts sites that toppled. D weights each site's
    odometer by its missing neighbours. Reach uses distance to the nearest source,
    so repeated batch locations are allowed and a zero event has reach zero.
    """
    u = np.asarray(odometer).ravel()
    touched = np.flatnonzero(u)
    return np.array(
        [
            u.sum(),
            len(touched),
            ((graph.neighbours() < 0).sum(axis=1) * u).sum(),
            1 + graph.distances(touched, sources).max() if len(touched) else 0,
        ],
        dtype=np.int64,
    )
