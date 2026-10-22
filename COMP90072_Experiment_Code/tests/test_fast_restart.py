"""Compiled/reference agreement, exact batching and interruption recovery."""

import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from sandpile import fast, reference
from sandpile import experiment
from sandpile.model import Graph
from sandpile.experiment import run_chain, read_events


class FastAndRestart(unittest.TestCase):
    def test_exhaustive_compiled(self):
        g = Graph(2, 2)
        for state in itertools.product(range(4), repeat=4):
            for x in range(4):
                h = np.array(state).reshape(2, 2)
                for a, b in zip(
                    fast.stabilize(h, g, [x]), reference.stabilize(h, g, [x])
                ):
                    np.testing.assert_array_equal(a, b)

    def test_compiled_random_models(self):
        rng = np.random.default_rng(6723)
        for k in range(1000):
            g = Graph(
                int(rng.integers(1, 6)),
                int(rng.integers(3, 7)),
                "cylinder" if k % 2 else "open",
            )
            h = rng.integers(0, 8 if k < 100 else 4, size=(g.rows, g.cols))
            sources = rng.integers(g.n, size=4 if k % 3 else 1).tolist()
            for a, b in zip(
                fast.stabilize(h, g, sources), reference.stabilize(h, g, sources)
            ):
                np.testing.assert_array_equal(a, b)

    def test_compiled_batch_odometer_and_union(self):
        rng = np.random.default_rng(1110)
        g = Graph(8, 8)
        for case in range(120):
            h = rng.integers(4, size=(8, 8))
            sites = [27] * 4 if case == 0 else rng.integers(64, size=4).tolist()
            hb, ub, ob = fast.stabilize(h, g, sites)
            hs = h.copy()
            us = np.zeros_like(h)
            S = D = 0
            for s in sites:
                hs, u, o = fast.stabilize(hs, g, [s])
                us += u
                S += o[0]
                D += o[2]
            np.testing.assert_array_equal(hb, hs)
            np.testing.assert_array_equal(ub, us)
            self.assertEqual(ob[0], S)
            self.assertEqual(ob[2], D)
            self.assertEqual(ob[1], np.count_nonzero(us))

    def test_safety_rolls_back(self):
        h = np.full((8, 8), 3, dtype=np.int64)
        original = h.copy()
        with self.assertRaises(RuntimeError):
            fast.run(h, Graph(8, 8), np.array([[27]]), limit=1)
        np.testing.assert_array_equal(h, original)

    def test_restart_equivalence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for model in ["baseline", "biased", "cylinder"]:
                args = dict(
                    L=8,
                    model=model,
                    seed=1,
                    burn_grains=512,
                    production_grains=2048,
                    chunk_grains=256,
                    sample_grains=16,
                )
                a = root / (model + "a")
                b = root / (model + "b")
                run_chain(a, **args)
                run_chain(b, stop_after_chunks=3, **args)
                run_chain(b, **args)
                for stage in ["burn", "production"]:
                    da, db = read_events(a, stage), read_events(b, stage)
                    for key in da:
                        np.testing.assert_array_equal(da[key], db[key])
                with np.load(a / "checkpoint.npz") as ca, np.load(
                    b / "checkpoint.npz"
                ) as cb:
                    for key in ca.files:
                        np.testing.assert_array_equal(ca[key], cb[key])
            args = dict(
                L=8,
                model="batch",
                seed=1,
                burn_grains=0,
                production_grains=2048,
                chunk_grains=256,
                sample_grains=16,
                matched_path=root / "baselinea",
            )
            run_chain(root / "batcha", **args)
            run_chain(root / "batchb", stop_after_chunks=3, **args)
            run_chain(root / "batchb", **args)
            for k, v in read_events(root / "batcha").items():
                np.testing.assert_array_equal(v, read_events(root / "batchb")[k])

    def test_failure_between_metadata_and_checkpoint_commits(self):
        """A durable chunk/metadata update must not advance an older checkpoint."""
        real_atomic_npz = experiment.atomic_npz
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for model in ["baseline", "biased", "cylinder", "batch"]:
                with self.subTest(model=model):
                    args = dict(
                        L=8,
                        model=model,
                        seed=31,
                        burn_grains=128 if model != "batch" else 0,
                        production_grains=768,
                        chunk_grains=128,
                        sample_grains=16,
                    )
                    if model == "batch":
                        args["matched_path"] = root / "baseline_control"
                    control = root / (model + "_control")
                    crashed = root / (model + "_crashed")
                    run_chain(control, **args)
                    injected = []

                    def fail_checkpoint(path, **arrays):
                        if (
                            Path(path) == crashed / "checkpoint.npz"
                            and arrays.get("stage") == "production"
                            and arrays.get("done")
                            == 256 // (4 if model == "batch" else 1)
                        ):
                            meta = json.loads((crashed / "metadata.json").read_text())
                            with np.load(path) as checkpoint:
                                self.assertEqual(
                                    len(meta["chunks"]),
                                    int(checkpoint["committed"]) + 1,
                                )
                            injected.append(True)
                            raise OSError(
                                "Injected interruption after metadata, before checkpoint"
                            )
                        return real_atomic_npz(path, **arrays)

                    with patch.object(
                        experiment, "atomic_npz", side_effect=fail_checkpoint
                    ):
                        with self.assertRaisesRegex(OSError, "Injected interruption"):
                            run_chain(crashed, **args)
                    self.assertEqual(injected, [True])
                    run_chain(crashed, **args)
                    for stage in (
                        ["burn", "production"] if model != "batch" else ["production"]
                    ):
                        a, b = read_events(control, stage), read_events(crashed, stage)
                        for key in a:
                            np.testing.assert_array_equal(a[key], b[key])
                    with np.load(control / "checkpoint.npz") as a, np.load(
                        crashed / "checkpoint.npz"
                    ) as b:
                        for key in a.files:
                            np.testing.assert_array_equal(a[key], b[key])
                    ameta = json.loads((control / "metadata.json").read_text())
                    bmeta = json.loads((crashed / "metadata.json").read_text())
                    self.assertEqual(ameta["chunks"], bmeta["chunks"])

    def test_stored_event_schema_dtypes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for model in ["baseline", "biased", "cylinder", "batch"]:
                args = dict(
                    L=4,
                    model=model,
                    seed=72,
                    burn_grains=0,
                    production_grains=32,
                    chunk_grains=16,
                    sample_grains=8,
                )
                if model == "batch":
                    args["matched_path"] = root / "baseline"
                run_chain(root / model, **args)
                with np.load(root / model / "production_000000000.npz") as data:
                    self.assertEqual(data["sources"].dtype, np.dtype("int32"))
                    for key in [
                        "events",
                        "event_index",
                        "grains_per_event",
                        "frequencies",
                        "frequency_event",
                        "grid_start",
                        "grid_end",
                    ]:
                        self.assertEqual(data[key].dtype, np.dtype("int64"), key)


if __name__ == "__main__":
    unittest.main()
