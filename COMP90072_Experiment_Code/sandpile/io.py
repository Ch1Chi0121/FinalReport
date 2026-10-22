"""Atomic checkpoints, source copies and saved-file checks."""
import zipfile
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def check_sources(folder):
    """Keep one copy of the simulation sources alongside a cohort's runs.

    A resumed cohort must use the same source text. Storing the text itself makes
    changes inspectable without a separate digest or versioning dependency.
    """
    folder = Path(folder)
    snapshot = folder / "simulation_sources.json"
    names = ["model.py", "kernel.c", "fast.py", "experiment.py", "io.py"]
    current = {name: (ROOT / "sandpile" / name).read_text() for name in names}
    if snapshot.exists():
        if json.loads(snapshot.read_text()) != current:
            raise ValueError("Simulation source changed; use a new data directory")
    else:
        atomic_json(snapshot, current)


def check_chunk(folder, entry):
    """Check a saved chunk's length and the NPZ archive's built-in CRCs."""
    path = Path(folder) / entry["file"]
    if path.stat().st_size != entry["bytes"]:
        raise ArithmeticError(f"Chunk length differs from its metadata: {path}")
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ArithmeticError(f"Damaged NPZ archive: {path}")
    return path


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False))
    os.replace(temporary, path)


def atomic_npz(path, **arrays):
    """Write an NPZ beside its target, then replace the target atomically.

    A checkpoint is either the previous complete file or this new complete file.
    Chunk/metadata/checkpoint ordering is handled by experiment.run_chain.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "wb") as f:
        np.savez_compressed(f, **arrays)
    os.replace(temporary, path)


def environment():
    return {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "packages": {
            p: importlib.metadata.version(p) for p in ["numpy", "scipy", "matplotlib"]
        },
        "timestamp": now(),
    }
