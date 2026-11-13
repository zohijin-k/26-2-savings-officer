"""Paired synthetic-only corpus; preserve ambiguous source layouts and labels.

V1 reports and generator stay unchanged. V2 changes only authored fictitious
identity/date parameters to fix duplicate repetitions and adds explicit groups.
Reference glyphs are extracted from the generated text layer, then mapped into
exactly the same image coordinates as each own-OCR input.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
import tempfile
import time

import numpy as np
import pymupdf
from PIL import Image, ImageFilter

from . import documentai_synth as legacy
from .make_synth_eval import phone_capture
from ..pipeline.ocr import OcrWord

DOCS = legacy.DOCS
CONDITIONS = (*legacy.CONDITIONS, "layout_variant")
SOURCE_EVIDENCE = [
    "S01: Original layouts, purpose markings and table cells are unchanged from documentai_synth.sources(), nhis_form_samples and p2_payment_samples; ambiguity is retained, not repaired to obtain PASS.",
    "S02: documentai_synth.sources() uses sample % 4. V2 replaces only fictitious identity/date values with five distinct parameter sets; no labels, column positions or original typography are removed.",
    "S03: Insurance output timestamp follows the varied issue date, preserving the +1 day relationship printed by insurance_portal_cells(); qualification request precedes issue and validity remains after it.",
    "S04: Legacy defects() replaces every printed 2026 year but leaves other truth dates unchanged and hardcodes issue March03. V2 changes all authored 2026 truth date values to the same negative-case year, including qualification request dates, while retaining the varied issue month/day.",
    "S05: layout_variant adds bounded row-position jitter as a separately labeled stress case; original geometry and all source text are retained. Existing p2 geometry/jitter tests motivate stress coverage, not a baseline correction.",
]


def sources(sample=0):
    if type(sample) is not int or not 0 <= sample < 20:
        raise ValueError("SAMPLE_INVALID")
    alphabet = "가나다라마바사아자차카타파하"
    name = "가상" + alphabet[sample // len(alphabet)] + alphabet[sample % len(alphabet)]
    issued = date(2026, 3, 3) + timedelta(days=sample)
    old = date(2026, 3, 3)
    replacements = [
        ("가짜이름", name),
        (old.isoformat(), issued.isoformat()),
        ("2026년03월03일", f"{issued.year}년{issued.month:02}월{issued.day:02}일"),
        ("2026 년 03 월 03 일", f"{issued.year} 년 {issued.month:02} 월 {issued.day:02} 일"),
        ("2026.03.03", issued.strftime("%Y.%m.%d")),
    ]
    def replace(value):
        if isinstance(value, str):
            for before, after in replacements:
                value = value.replace(before, after)
            return value
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value
    for source in legacy.sources(0):
        source = deepcopy(source)
        source.truth = replace(source.truth)
        source.identity = replace(source.identity)
        for cells, _ in source.pages:
            for index, (x, y, text, size) in enumerate(cells):
                if source.doc == "insurance_4" and text.startswith("출력일시"):
                    text = "출력일시 : " + (issued + timedelta(days=1)).strftime("%Y.%m.%d") + " 09:30"
                else:
                    text = replace(text)
                cells[index] = x, y, text, size
        yield source


def source_fingerprint(source):
    data = {"doc": source.doc, "pages": source.pages, "truth": source.truth, "identity": source.identity}
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def rendered(source):
    """One physical PDF page; emit actual raster and exact text-layer word boxes."""
    with pymupdf.open(stream=legacy.pdf_bytes(source), filetype="pdf") as document:
        if len(document) != 1:
            raise ValueError("PAGE_SCOPE_UNSUPPORTED")
        page = document[0]
        pix = page.get_pixmap(dpi=300, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        scale = 300 / 72
        words = [OcrWord(item[4], 1.0, tuple(value * scale for value in item[:4]))
                 for item in page.get_text("words", sort=True) if item[4].strip()]
        if not words:
            raise ValueError("TEXT_LAYER_REQUIRED")
        font = pymupdf.Font("cjk")
        text = "".join(cell[2] for cells, _ in source.pages for cell in cells)
        metadata = {"font": font.name, "font_sha256": hashlib.sha256(font.buffer).hexdigest(),
                    "missing_glyphs": sum(not font.has_glyph(ord(char)) for char in set(text) if not char.isspace()),
                    "reference_characters": sum(not char.isspace() for word in words for char in word.text)}
        return image, words, metadata


def map_words(words, matrix):
    """Map continuous glyph bounds; each OCR-style box encloses all four corners."""
    matrix = np.asarray(matrix, dtype=float)
    result = []
    for word in words:
        x0, y0, x1, y1 = word.bbox_px
        corners = np.array([[x0, y0, 1], [x1, y0, 1], [x1, y1, 1], [x0, y1, 1]]) @ matrix.T
        xy = corners[:, :2] / corners[:, 2:3]
        result.append(OcrWord(word.text, 1.0, tuple(float(v) for v in (*xy.min(axis=0), *xy.max(axis=0)))))
    return result


def transformed(image, words, condition, rng):
    if condition == "phone":
        capture, matrix, _ = phone_capture(image, "phone_strong", rng)
        return capture, map_words(words, matrix)
    result = legacy.transform(image, condition, rng)
    matrix = np.eye(3)
    if condition == "low_resolution":
        matrix = np.diag([result.width / image.width, result.height / image.height, 1.0])
    elif condition == "rotate90":
        matrix = np.array([[0, 1, 0], [-1, 0, image.width], [0, 0, 1]], dtype=float)
    elif condition in {"rotate_plus5", "rotate_minus5"}:
        angle = math.radians(5 if condition == "rotate_plus5" else -5)
        rotate = np.array([[math.cos(angle), math.sin(angle), 0], [-math.sin(angle), math.cos(angle), 0], [0, 0, 1]])
        origin = np.array([[1, 0, -image.width / 2], [0, 1, -image.height / 2], [0, 0, 1]])
        destination = np.array([[1, 0, result.width / 2], [0, 1, result.height / 2], [0, 0, 1]])
        matrix = destination @ rotate @ origin
    return result, map_words(words, matrix)


def layout_variant(source, sample):
    """Source augmentation only: retain every character and existing proximity."""
    changed = deepcopy(source)
    for cells, _ in changed.pages:
        for index, (x, y, text, size) in enumerate(cells):
            # Shared row offsets retain relative order; bounded and deterministic.
            band = int(y // 20)
            dx = ((band + sample) % 5 - 2) * .8
            dy = ((band * 3 + sample) % 3 - 1) * .8
            cells[index] = x + dx, y + dy, text, size
    return changed


def negative_date_truth(source, year):
    """Mirror legacy's printed year mutation in independent authored GT only."""
    def replace(value):
        if isinstance(value, str):
            return value.replace("2026", str(year))
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value
    return replace(source.truth)


def cases_for_source(source, sample, rng):
    image, words, font = rendered(source)
    for condition in CONDITIONS:
        if condition == "layout_variant":
            picture, reference, _ = rendered(layout_variant(source, sample))
        else:
            picture, reference = transformed(image, words, condition, rng)
        group = "normal_baseline" if condition == "original" else "quality_defect" if condition == "low_resolution" else "stress"
        yield {"condition": condition, "group": group, "expected": "FAIL" if group == "quality_defect" else "VALID",
               "image": picture, "reference_words": reference, "source": source, "slot_doc": source.doc, "font": font}
    for label, damaged in legacy.defects(source):
        if label in {"issued_too_early", "issued_after_application"}:
            # Repair truth only, never the printed input or decision logic.
            damaged.truth = negative_date_truth(source, 2024 if label == "issued_too_early" else 2027)
        condition = "defect_low_resolution" if label == "low_resolution" else label
        picture, reference, _ = rendered(damaged)
        if label == "low_resolution":
            smaller = picture.resize((400, 566), Image.Resampling.LANCZOS)
            reference = map_words(reference, np.diag([400 / picture.width, 566 / picture.height, 1.0]))
            picture = smaller
        elif label == "low_image_quality":
            # All text and original pixels remain authored; blur is the defect.
            # Keep the v1 upsampled-blur case; do not label only by verdict.
            picture = picture.resize((200, 280)).filter(ImageFilter.GaussianBlur(3)).resize(picture.size)
        slot = DOCS[(DOCS.index(source.doc) + 1) % len(DOCS)] if label == "wrong_document_type" else source.doc
        yield {"condition": condition, "group": "quality_defect" if label in {"low_resolution", "low_image_quality"} else "content_defect",
               "expected": "FAIL", "image": None if label == "unreadable_file" else picture,
               "reference_words": [] if label == "unreadable_file" else reference,
               "source": damaged, "slot_doc": slot, "font": font}


def run(output: Path, samples=5, seed=20261113):
    from .documentai_staged import measure_stage, pair_metrics, failure_stage
    from .documentai_staged_report import summarize, markdown
    if type(samples) is not int or not 1 <= samples <= 20:
        raise ValueError("SAMPLE_INVALID")
    output = Path(output)
    # V2 never overwrites an old result/report, including symlink targets.
    if output.suffix.lower() != ".json":
        raise ValueError("OUTPUT_FORMAT_INVALID")
    checkpoint = output.with_suffix(".rows.jsonl")
    if output.exists() or output.with_suffix(".md").exists() or checkpoint.exists():
        raise ValueError("OUTPUT_EXISTS")
    rows = []
    sources_seen = {kind: set() for kind in DOCS}
    metadata = []
    input_seen = {}
    rng = np.random.default_rng(seed)
    started = time.perf_counter()
    with checkpoint.open("x", encoding="utf-8") as progress, tempfile.TemporaryDirectory(prefix="documentai-staged-synthetic-") as directory:
        path = Path(directory) / "synthetic.png"
        for sample in range(samples):
            for source in sources(sample):
                fingerprint = source_fingerprint(source)
                if fingerprint in sources_seen[source.doc]:
                    raise ValueError("DUPLICATE_SOURCE")
                sources_seen[source.doc].add(fingerprint)
                for case in cases_for_source(source, sample, rng):
                    if case["image"] is None:
                        path.write_bytes(f"FICTITIOUS INVALID IMAGE {source.doc} SAMPLE {sample+1}".encode())
                    else:
                        case["image"].save(path)
                    input_fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
                    input_key = (source.doc, case["condition"])
                    seen = input_seen.setdefault(input_key, set())
                    if input_fingerprint in seen:
                        raise ValueError("DUPLICATE_INPUT")
                    seen.add(input_fingerprint)
                    stages = {}
                    for name, reference in (("reference", case["reference_words"]), ("own", None)):
                        t = time.perf_counter()
                        try:
                            stage = measure_stage(path, source.doc, case["source"].truth, identity=case["source"].identity,
                                                  reference_words=reference, slot_doc=case["slot_doc"])
                        except Exception:
                            stage = failure_stage(source.doc, case["source"].truth)
                            stage["seconds"] = time.perf_counter() - t
                            stage["source"] = "TEXT_LAYER_REFERENCE" if name == "reference" else "OWN"
                        if case["image"] is None:
                            stage["pages"] = 0
                            stage["seconds_per_page"] = None
                        stages[name] = stage
                    row = {"case_id": f"s{sample+1}_{source.doc}_{case['condition']}", "doc": source.doc,
                           "condition": case["condition"], "sample": sample + 1,
                           "group": case["group"], "expected": case["expected"],
                           "input_fingerprint": input_fingerprint,
                           **stages, "attribution": pair_metrics(stages["reference"], stages["own"])}
                    rows.append(row)
                    progress.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                    progress.flush()
                    if case["condition"] == "original":
                        metadata.append({"doc": source.doc, "sample": sample + 1, "source_fingerprint": fingerprint, **case["font"]})
                    print(f"{len(rows)} {source.doc} {case['condition']} {stages['reference']['failed']} {stages['own']['failed']}", flush=True)
    report = {"schema_version": 2, "samples": samples, "seed": seed, "rows": rows, "summary": summarize(rows),
              "elapsed_wall_seconds": time.perf_counter() - started, "source_metadata": metadata, "source_changes": SOURCE_EVIDENCE,
              "method": "PAIRED_SAME_IMAGE_GEOMETRY_TEXT_LAYER_WORDS_VS_OWN", "legacy_reports_unchanged": "O"}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    return report
