"""Atomic checkpoints, content hashes and environment provenance."""
import hashlib
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


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def core_hash():
    """Fingerprint the four source files that determine stored simulations.

    The hash includes formatting and comments. Editing these files therefore requires
    a fresh output directory even when a change leaves the numerical rules intact.
    Analysis and report edits are tracked separately in the final manifest.
    """
    names = ["model.py", "kernel.c", "fast.py", "experiment.py"]
    return hashlib.sha256(
        b"".join((ROOT / "sandpile" / p).read_bytes() for p in names)
    ).hexdigest()


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
