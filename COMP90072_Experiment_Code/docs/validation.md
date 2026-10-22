# Release validation

Validated on 22 October 2026 using Python 3.12.2, pinned dependencies and a C11
compiler on arm64 macOS. A ZIP of this edition was extracted into a new folder,
without copying in original raw data.

```bash
python run_project.py all
python run_project.py smoke
```

The complete workflow passed: 11 pilot/control chains, 50 primary runs,
100 independent ensemble chains, 20 confirmation runs, analysis, sensitivity,
figures, tables and the result index. The unit suite passed all 24 tests.
Two tests specifically cover changed source copies and damaged NPZ archives.
A separate check confirmed that a stale C source copy causes recompilation.
The smoke passed two fresh executions of eight model/seed combinations.

Direct byte comparisons with the original experiments found 4,765 identical
event chunks and 543 identical initial/start/checkpoint files. Statistical
outputs match, including confirmation and range-sensitivity results. All 11
plots are identical. Of 499 numerical macros, 493 match; the six differences
are new measured kernel, I/O, wall, compilation, warm-up and queue-speed timings.
The mathematical rules, random streams and frozen experimental choices remain
the same. File checks and stored metadata are the parts changed in this edition.

The file-integrity checks now use source copies, expected byte lengths and NPZ
CRCs. These detect source changes and ordinary archive damage. They are not
proof against deliberate edits to otherwise consistent records.

`reference_results/validation.json` records the executed stages and comparisons.
The test, smoke and result-index check outputs are included in the same folder.
PDF compilation was not rerun for this change; its optional tools remain listed
in README. Other operating systems have not been tested.
