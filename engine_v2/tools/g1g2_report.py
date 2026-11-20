"""Synthetic G1/G2 report for the presentation and validation sets (own engine, original condition).

Run with ``python -B -m engine_v2.tools.g1g2_report``. Synthetic sources only: no real
document path or value is read or written.

* G1 = documents whose form type is right / 25.
* G2 = core items read right / 165 fixed items (nhis_payment, nhis_qualification,
  nhis_acquisition_loss, resident_abstract; an item of an unclassified document counts as wrong).
* G2-4대보험 (supplementary) = insurance_4 items read right / 25 fixed items.
* ITEM lines give the O/X count of every (form, item); the 190 total is reference only.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
from collections import Counter
import tempfile
from pathlib import Path

#: (label, samples, seed) — research/validation-set.md of 11-17-speed-baseline.
SETS = (("presentation", range(0, 5), 20261113), ("validation", range(5, 10), 20261117))
INS4 = "insurance_4"
G2_DENOMINATOR = 165
INS4_DENOMINATOR = 25


def tally(stages):
    """Aggregate measure_stage results: [(doc, stage)] -> counts and per-item O/X."""
    result = dict(n=0, g1=0, g2=0, g2_items=0, ins4=0, ins4_items=0, items=Counter())
    for doc, stage in stages:
        result["n"] += 1
        result["g1"] += stage["type_match"] == "O"
        for key, field in stage["fields"].items():
            ok = field["normalized_match"] == "O"
            result["items"][(doc, key, "O" if ok else "X")] += 1
            if doc == INS4:
                result["ins4_items"] += 1
                result["ins4"] += ok
            else:
                result["g2_items"] += 1
                result["g2"] += ok
    return result


def measure(samples, seed):
    import numpy as np
    from . import documentai_corpus_v2 as v2
    from .documentai_staged import measure_stage
    rng = np.random.default_rng(seed)
    stages = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "case.png"
        for sample in range(max(samples) + 1):
            for source in v2.sources(sample):
                # Consume the generator for every sample so later samples see the same randomness.
                for case in v2.cases_for_source(source, sample, rng):
                    if case["condition"] != "original" or sample not in samples:
                        continue
                    case["image"].save(path)
                    stages.append((source.doc, measure_stage(path, source.doc, case["source"].truth,
                                                             identity=case["source"].identity)))
    return tally(stages)


def report(label, result):
    lines = [f"G1 {label} {result['g1']}/{result['n']}",
             f"G2 {label} {result['g2']}/{G2_DENOMINATOR} (items {result['g2_items']})",
             f"G2_INS4 {label} {result['ins4']}/{INS4_DENOMINATOR} (items {result['ins4_items']})"]
    keys = sorted({(doc, key) for doc, key, _ in result["items"]})
    for doc, key in keys:
        lines.append(f"ITEM {label} {doc} {key} O {result['items'][(doc, key, 'O')]} "
                     f"X {result['items'][(doc, key, 'X')]}")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(prog="g1g2_report", description="Synthetic G1/G2 report")
    parser.add_argument("--sets", nargs="+", choices=[label for label, _, _ in SETS],
                        default=[label for label, _, _ in SETS])
    args = parser.parse_args(argv)
    for label, samples, seed in SETS:
        if label in args.sets:
            print("\n".join(report(label, measure(set(samples), seed))), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
