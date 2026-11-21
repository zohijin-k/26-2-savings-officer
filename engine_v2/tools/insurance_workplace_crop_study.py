"""Bounded synthetic-only name-region feasibility; never a production recovery.

No input document paths. Four authored rows, original and fixed 2x/1.1 contrast
variants, <=1 MP each, eight serial calls to the existing pinned Own recognizer.
Outputs are aggregate counts/times only. No crop gallery or candidate text.
"""
from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
import json
import math
import signal
import time

TRUTH = "가상솔빛상사"
VARIANTS = ("original", "enlarged_contrast")
FONT_SIZES = (8, 6, 4, 3)
TIMEOUT_SECONDS = 5.0


@contextmanager
def _budget(seconds):
    previous = signal.getsignal(signal.SIGALRM)
    def expired(signum, frame):
        raise TimeoutError
    signal.signal(signal.SIGALRM, expired)
    prior_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *prior_timer)
        signal.signal(signal.SIGALRM, previous)


def crops():
    """A complete isolated column corridor from a newly authored in-memory page."""
    import pymupdf
    from PIL import Image, ImageEnhance
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=400, height=180)
        font = pymupdf.Font("cjk")
        for index, size in enumerate(FONT_SIZES):
            y = 40 + index * 35
            writer = pymupdf.TextWriter(page.rect)
            writer.append((110, y), TRUTH, font=font, fontsize=size)
            writer.write_text(page)
            page.insert_text((40, y), "SYNTHETIC", fontsize=6)
            page.insert_text((300, y), "2020.01.01", fontsize=6)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        for index in range(4):
            y = 40 + index * 35
            # Authored row boundaries and name-column corridor, excluding adjacent cells.
            crop = image.crop((100 * 3, (y - 16) * 3, 280 * 3, (y + 6) * 3))
            for variant in VARIANTS:
                candidate = crop if variant == "original" else ImageEnhance.Contrast(
                    crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.BICUBIC)).enhance(1.1)
                if candidate.width * candidate.height > 1_000_000:
                    raise ValueError("SYNTHETIC_CROP_BUDGET")
                out = BytesIO(); candidate.save(out, format="PNG")
                yield index, variant, out.getvalue(), candidate.size


def _stats(values):
    if not values:
        return {"n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
    values = sorted(value * 1000 for value in values)
    def percentile(q):
        return values[max(0, math.ceil(q * len(values)) - 1)]
    return {"n": len(values), "p50_ms": percentile(.5), "p95_ms": percentile(.95), "max_ms": values[-1]}


def run_study(recognize=None):
    if recognize is None:
        from engine_v2.pipeline.ocr import _run_own
        recognize = _run_own
    counts = {v: {k: 0 for k in ("correct", "wrong", "empty", "timeout", "error", "high_score_wrong")}
              for v in VARIANTS}
    records, candidates = [], {}
    for index, variant, png, size in crops():
        started = time.perf_counter()
        text = None
        outcome = "error"
        try:
            with _budget(TIMEOUT_SECONDS):
                words = recognize(png, size)
            text = "".join(word.text for word in words)
            outcome = "empty" if not text.strip() else "correct" if text == TRUTH else "wrong"
            if outcome == "wrong" and words and all(
                    type(w.confidence) in {float, int} and math.isfinite(w.confidence) and w.confidence >= .85
                    for w in words):
                counts[variant]["high_score_wrong"] += 1
        except TimeoutError:
            outcome = "timeout"
        except Exception:
            # No exception value, model path, raw text or candidate is emitted.
            outcome = "error"
        elapsed = time.perf_counter() - started
        counts[variant][outcome] += 1
        records.append((variant, elapsed, outcome))
        candidates[index, variant] = text
    disagreements = sum(candidates[i, "original"] != candidates[i, "enlarged_contrast"]
                        for i in range(4) if all(candidates[i, v] is not None for v in VARIANTS))
    return {"synthetic_only": True, "automatic_recovery_enabled": False,
            "rows": 4, "region_calls": len(records), "variants": counts,
            "disagreement_rows": disagreements, "timeout_seconds": TIMEOUT_SECONDS,
            "cold": _stats([records[0][1]]), "warm": _stats([r[1] for r in records[1:]]),
            "variant_latency": {v: _stats([r[1] for r in records if r[0] == v]) for v in VARIANTS},
            "total_region_seconds": sum(r[1] for r in records), "retained_crop_bytes": 0}


def main():
    print(json.dumps(run_study(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
