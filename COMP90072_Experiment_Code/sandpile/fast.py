"""ctypes wrapper for the profiled C queue kernel; Python owns RNG and files."""
import ctypes
import json
from pathlib import Path
import platform
import subprocess
import time
import numpy as np
from .model import check_grid

ROOT = Path(__file__).resolve().parents[1]
_library = None


def build(force=False):
    """Build a small local shared library; return compiler/timing metadata."""
    source = Path(__file__).with_name("kernel.c")
    folder = ROOT / "build"
    folder.mkdir(exist_ok=True)
    library = folder / (
        "kernel.dylib" if platform.system() == "Darwin" else "kernel.so"
    )
    saved_source = folder / "kernel_source.c"
    meta_path = folder / "compiler.json"
    if not force and library.exists() and meta_path.exists():
        old = json.loads(meta_path.read_text())
        if saved_source.exists() and saved_source.read_bytes() == source.read_bytes():
            return old
    args = [
        "cc",
        "-O3",
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-fPIC",
        "-shared",
        str(source),
        "-o",
        str(library),
    ]
    start = time.perf_counter()
    subprocess.run(args, check=True, capture_output=True)
    meta = {
        "command": args,
        "seconds": time.perf_counter() - start,
        "compiler": subprocess.check_output(
            ["cc", "--version"], text=True
        ).splitlines()[0],
        "library": str(library),
    }
    saved_source.write_bytes(source.read_bytes())
    meta_path.write_text(json.dumps(meta, indent=2))
    return meta


def library():
    global _library
    if _library is None:
        meta = build()
        _library = ctypes.CDLL(meta["library"])
        arr = np.ctypeslib.ndpointer(dtype=np.int64, flags="C_CONTIGUOUS")
        _library.simulate.argtypes = [
            ctypes.c_int64,
            ctypes.c_int64,
            ctypes.c_int,
            arr,
            arr,
            arr,
            ctypes.c_int64,
            ctypes.c_int64,
            ctypes.c_int64,
            ctypes.c_int64,
            ctypes.c_int64,
            arr,
            arr,
            arr,
            ctypes.c_int,
        ]
        _library.simulate.restype = ctypes.c_int
    return _library


def run(grid, graph, sources, offset=0, stride=128, limit=10**9, scan_initial=False):
    """Stabilize a stream of events and return its measurements.

    sources has shape (event_count, grains_per_event), with flat site indices and
    replacement allowed. offset and stride count events, rather than grains.
    Returns (stable_grid, records, height_counts, last_odometer). Record columns are
    S, A, D, reach, mass_after and minimum source-to-sink-boundary distance.

    The input grid is copied before C sees it. If a safety or mass check fails, the
    caller can retry from its unchanged stable checkpoint. scan_initial is used by
    single-event validation when the starting grid may already be unstable.
    """
    h = check_grid(grid, graph).ravel()
    raw = np.asarray(sources)
    if not np.issubdtype(raw.dtype, np.integer):
        raise ValueError("Integer sources required")
    src = np.ascontiguousarray(raw, dtype=np.int64)
    if src.ndim == 1:
        src = src[:, None]
    if src.ndim != 2 or src.shape[0] == 0 or not 1 <= src.shape[1] <= 1024:
        raise ValueError(
            "Sources must have positive events and 1..1024 grains per event"
        )
    if np.any(src < 0) or np.any(src >= graph.n):
        raise ValueError("Source outside graph")
    if stride < 1 or offset < 0 or limit < 1:
        raise ValueError("Invalid stride/offset/safety limit")
    if not scan_initial and np.any(h > 3):
        raise ValueError("Stable initial state required")
    # Allocate the exact number of checkpoints crossed by this chunk.
    events, m = src.shape
    out = np.zeros((events, 6), dtype=np.int64)
    frequencies = np.zeros(
        ((offset + events) // stride - offset // stride, 4), dtype=np.int64
    )
    u = np.zeros(graph.n, dtype=np.int64)
    # Argument order mirrors simulate() in kernel.c; arrays are contiguous int64.
    code = library().simulate(
        graph.rows,
        graph.cols,
        int(graph.boundary == "cylinder"),
        h,
        graph.neighbours(),
        src,
        events,
        m,
        offset,
        stride,
        limit,
        out,
        frequencies,
        u,
        int(scan_initial),
    )
    if code:
        raise RuntimeError(
            f"Kernel failed with status {code}; entire chunk must restart"
        )
    if np.any(h < 0) or np.any(h > 3) or h.sum() != out[-1, 4]:
        raise ArithmeticError("Final stability/mass failure")
    before = np.r_[int(np.sum(grid)), out[:-1, 4]]
    if not np.array_equal(out[:, 4], before + m - out[:, 2]):
        raise ArithmeticError("Event mass failure")
    if np.any(out[:, 1] > out[:, 0]) or np.any(out[:, 1] > graph.n):
        raise ArithmeticError("Metric bound failure")
    return (
        h.reshape(graph.rows, graph.cols),
        out,
        frequencies,
        u.reshape(graph.rows, graph.cols),
    )


def stabilize(grid, graph, sources):
    """Reference-compatible single-event interface, also allowing unstable h."""
    h, obs, _, u = run(
        grid,
        graph,
        np.array(sources, dtype=np.int64)[None, :],
        stride=1,
        scan_initial=True,
    )
    return h, u, obs[0, :4]
