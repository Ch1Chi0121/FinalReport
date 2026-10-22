"""Source-version and damaged-chunk checks for the simplified file format."""

import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import numpy as np
from sandpile.io import check_sources, check_chunk


class SavedFiles(unittest.TestCase):
    def test_changed_source_copy_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            check_sources(folder)
            check_sources(folder)
            path = Path(folder) / "simulation_sources.json"
            saved = json.loads(path.read_text())
            saved["model.py"] += "\n# changed\n"
            path.write_text(json.dumps(saved))
            with self.assertRaisesRegex(ValueError, "Simulation source changed"):
                check_sources(folder)

    def test_chunk_length_and_crc_are_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "chunk.npz"
            np.savez(path, events=np.arange(12, dtype=np.int64))
            entry = {"file": path.name, "bytes": path.stat().st_size}
            check_chunk(folder, entry)
            with self.assertRaises(ArithmeticError):
                check_chunk(folder, {**entry, "bytes": entry["bytes"] + 1})
            with zipfile.ZipFile(path) as archive:
                info = archive.getinfo("events.npy")
                offset = (
                    info.header_offset
                    + 30
                    + len(info.filename.encode())
                    + len(info.extra)
                )
            # Alter an array byte without changing the file length or saved CRC.
            content = bytearray(path.read_bytes())
            content[offset + info.compress_size - 1] ^= 1
            path.write_bytes(content)
            with self.assertRaises((ArithmeticError, zipfile.BadZipFile)):
                check_chunk(folder, entry)


if __name__ == "__main__":
    unittest.main()
