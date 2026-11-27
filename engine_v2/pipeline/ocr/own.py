"""PP-OCRv5 DB detection + Korean CTC recognition, exclusively ONNX CPU.

Algorithms implemented here; model and upstream attribution in docs/own-ocr.md.
No automatic download and no filename-based recognition.
"""
from __future__ import annotations

from functools import lru_cache
import logging
import math
import os
import re
import threading

from ...tools.fetch_own_models import MODEL_DIR, verify_models
from . import OcrWord
from ..privacy import mask_words


def ctc_decode(probabilities, characters: list[str]) -> tuple[str, float]:
    """Blank=0, collapse adjacent repeats BEFORE removing blank; mean emitted score."""
    import numpy as np
    probs = np.asarray(probabilities)
    if probs.ndim != 2 or probs.shape[1] != len(characters) + 1:
        raise ValueError('CTC class count does not match pinned dictionary')
    if not len(probs):
        return '', 0.0
    ids = probs.argmax(axis=1)
    keep = (ids != 0) & np.r_[True, ids[1:] != ids[:-1]]
    text = ''.join(characters[int(i) - 1] for i in ids[keep])
    return text, float(probs[np.arange(len(ids))[keep], ids[keep]].mean()) if keep.any() else 0.0


def polygon_bbox(points, source_size, map_size):
    """Map polygon coordinates to top-left pixel bounds of original input."""
    import numpy as np
    pts = np.asarray(points, dtype=float) * (np.asarray(source_size) / np.asarray(map_size))
    pts = np.clip(pts, (0, 0), source_size)
    return tuple(float(v) for v in (*pts.min(axis=0), *pts.max(axis=0)))


_log = logging.getLogger(__name__)


def _env_count(name: str, default: int) -> int:
    """Positive integer from environment variable ``name``; unset or empty → default.

    Anything else (0, negative, not 1-6 plain decimal digits) gives the default, with one
    warning line that names the variable but never echoes its value.
    """
    raw = os.environ.get(name, '').strip()
    if not raw:
        return default
    if re.fullmatch('[0-9]{1,6}', raw) and int(raw) > 0:
        return int(raw)
    _log.warning('%s is not a positive integer; using default %d', name, default)
    return default


THREAD_ENV = ('OWN_OCR_INTRA_THREADS', 'OWN_OCR_PAGE_WORKERS')
#: Automatic thread choice by page count (11-19): on when neither variable is set (unset or empty).
#: A document read one page at a time (one OCR page, or any sequential read) uses one session with
#: ``single_intra_threads()`` threads; 2+ pages read concurrently use page sessions with
#: INTRA_OP_THREADS threads each. Setting either variable fixes the values as before (auto off).
AUTO_THREADS = not any(os.environ.get(name, '').strip() for name in THREAD_ENV)
#: Auto: onnxruntime threads of the single (sequential) session, capped at the logical CPU count.
SINGLE_INTRA_THREADS = 4
#: onnxruntime threads per page session (env OWN_OCR_INTRA_THREADS, read at import; fixed mode:
#: every session). Page workers are bounded so that workers x INTRA_OP_THREADS never exceeds the
#: logical CPU count.
INTRA_OP_THREADS = _env_count('OWN_OCR_INTRA_THREADS', 2)
#: Upper bound on concurrent page sessions (memory: one det+rec pair each);
#: env OWN_OCR_PAGE_WORKERS, read at import. 1 reads pages sequentially.
MAX_PAGE_WORKERS = _env_count('OWN_OCR_PAGE_WORKERS', 4)
#: Auto (11-19 T4b): a two-page document reads both pages at once on two page sessions with this
#: many threads each, when 2 x TWO_PAGE_INTRA_THREADS fits the logical CPU count; otherwise (and for
#: 3+ pages, and in fixed mode) page sessions use INTRA_OP_THREADS. Its slot 0 is the single session
#: only when this equals single_intra_threads(). 11-27: 2 (was 4). On the 8-core M2 (4P+4E) intra 4 x 2
#: read two-page scans 35% slower than intra 2 x 2 (same code, 4 interleaved rounds, round means apart),
#: so two pages now use the 3+-page sessions and preload holds 5 sessions again.
TWO_PAGE_INTRA_THREADS = 2
_worker = threading.local()


def single_intra_threads() -> int:
    """Threads of the single (sequential) session: auto 4 within the CPU count, fixed INTRA_OP_THREADS."""
    if not AUTO_THREADS:
        return INTRA_OP_THREADS
    return max(1, min(SINGLE_INTRA_THREADS, os.cpu_count() or 1))


def _load_sessions(intra_threads: int | None = None):
    verify_models(MODEL_DIR)
    import onnxruntime as ort
    ort.disable_telemetry_events()
    options = ort.SessionOptions()
    options.intra_op_num_threads = INTRA_OP_THREADS if intra_threads is None else intra_threads
    options.inter_op_num_threads = 1
    det, rec = [ort.InferenceSession(str(MODEL_DIR / name), sess_options=options,
                                    providers=['CPUExecutionProvider']) for name in ('det.onnx', 'rec.onnx')]
    chars = (MODEL_DIR / 'korean_dict.txt').read_text(encoding='utf-8').splitlines() + [' ']
    embedded = rec.get_modelmeta().custom_metadata_map.get('character')
    if embedded is not None and embedded.splitlines() != chars[:-1]:
        raise ValueError('own model metadata does not match pinned Korean dictionary')
    if rec.get_outputs()[0].shape[-1] != len(chars) + 1:
        raise ValueError('own recognition class count does not match dictionary')
    return det, rec, chars


@lru_cache(maxsize=1)
def sessions():
    """The single (sequential) sessions: one OCR page, or pages read one at a time."""
    return _load_sessions(single_intra_threads())


def shares_single_session(slot: int, intra_threads: int) -> bool:
    """Page slot 0 reuses the single sessions() when their thread counts agree.

    Fixed mode: always (every session uses INTRA_OP_THREADS), as before. Auto: only when the page
    threads equal ``single_intra_threads()``, i.e. a two-page document (intra 4) on 8+ cores; 3+
    pages (intra 2) keep their own slot 0. onnxruntime runs one session from several threads safely.
    """
    return slot == 0 and (not AUTO_THREADS or intra_threads == single_intra_threads())


@lru_cache(maxsize=None)
def page_sessions(slot: int, intra_threads: int):
    """Sessions owned by one concurrent page worker, with ``intra_threads`` threads.

    ``intra_threads`` is ``page_intra_threads(pages)`` of the document (always passed, so one
    slot and thread count is one cache entry). Slot 0 is the single sessions() when
    ``shares_single_session``; otherwise every (slot, threads) pair has its own session, so
    two-page sessions (intra 4) never share with 3+-page ones (intra 2).
    """
    return sessions() if shares_single_session(slot, intra_threads) else _load_sessions(intra_threads)


def page_intra_threads(pages: int) -> int:
    """Threads of each concurrent page session for a document of ``pages`` OCR pages.

    Auto: two pages use TWO_PAGE_INTRA_THREADS when two such sessions fit the logical CPU count;
    everything else (3+ pages, fewer cores, fixed mode) uses INTRA_OP_THREADS as before.
    """
    if (AUTO_THREADS and pages == 2 and MAX_PAGE_WORKERS >= 2 and
            (os.cpu_count() or 1) >= 2 * TWO_PAGE_INTRA_THREADS):
        return TWO_PAGE_INTRA_THREADS
    return INTRA_OP_THREADS


def page_workers(pages: int) -> int:
    """Concurrent page readers for a document, within the CPU budget (workers x threads <= cores)."""
    return max(1, min(pages, MAX_PAGE_WORKERS, (os.cpu_count() or 1) // page_intra_threads(pages)))


def prepare_page_workers(pages: int) -> int:
    """Load every worker slot in the calling thread; 1 (sequential) when any load fails.

    One worker reads pages one at a time on the single sessions(): no page session is loaded.
    """
    workers = page_workers(pages)
    if workers == 1:
        return 1
    intra = page_intra_threads(pages)
    try:
        for slot in range(workers):
            page_sessions(slot, intra)
    except Exception:  # noqa: BLE001 - the sequential path reports the same error per page
        return 1
    return workers


def bind_page_worker(slot: int, intra_threads: int | None = None) -> None:
    """Thread initializer: recognize() in this thread uses page_sessions(slot, intra_threads).

    ``intra_threads``: ``page_intra_threads(pages)`` of the document (None: INTRA_OP_THREADS).
    """
    _worker.slot = slot
    _worker.intra = INTRA_OP_THREADS if intra_threads is None else intra_threads


def _ordered_box(points):
    import numpy as np
    # Sort left/right pairs, then top/bottom, avoiding duplicate corners on diamonds.
    p = points[np.argsort(points[:, 0])]
    left, right = p[:2][np.argsort(p[:2, 1])], p[2:][np.argsort(p[2:, 1])]
    return np.array([left[0], right[0], right[1], left[1]], dtype=np.float32)


def _detect(image, session):
    import cv2
    import numpy as np
    import pyclipper
    h, w = image.shape[:2]
    ratio = min(1.0, 1600 / max(h, w))
    rh, rw = [max(32, round(v * ratio / 32) * 32) for v in (h, w)]
    resized = cv2.resize(image, (rw, rh)).astype(np.float32) / 255
    tensor = ((resized - np.array([.485, .456, .406], dtype=np.float32)) /
              np.array([.229, .224, .225], dtype=np.float32)).transpose(2, 0, 1)[None]
    pred = session.run(None, {session.get_inputs()[0].name: tensor})[0][0, 0]
    mask = (pred > .3).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    mh, mw = pred.shape
    boxes = []
    for contour in contours[:2000]:
        rect = cv2.minAreaRect(contour)
        if min(rect[1]) < 3:
            continue
        region = np.zeros_like(mask)
        cv2.fillPoly(region, [contour], 1)
        if cv2.mean(pred, region)[0] < .5:
            continue
        poly = cv2.boxPoints(rect)
        perimeter = cv2.arcLength(poly, True)
        if perimeter <= 0:
            continue
        offset = pyclipper.PyclipperOffset()
        offset.AddPath((poly * 1024).astype(np.int64).tolist(), pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        expanded = offset.Execute(cv2.contourArea(poly) * 1.5 / perimeter * 1024)
        if len(expanded) != 1:
            continue
        box = _ordered_box(cv2.boxPoints(cv2.minAreaRect(np.array(expanded[0], dtype=np.float32) / 1024)))
        box *= np.array([w / mw, h / mh], dtype=np.float32)
        box = np.clip(box, (0, 0), (w - 1, h - 1)).astype(np.float32)
        boxes.append(box)
    return _align_glyph_boxes(boxes, (w, h))


#: (11-26) A box whose long side is under this multiple of its short side holds one or two glyphs.
#: Its minAreaRect angle then follows the glyph shape (the diagonal stroke of "7", a lone ")"),
#: not a text line, and warping along it rotates the glyph (synthetic scan: "7" at +26 deg read "1").
GLYPH_BOX_MAX_ASPECT = 1.5
#: Boxes at least this elongated are text lines; their median angle is the page text angle.
LINE_BOX_MIN_ASPECT = 2.0
#: Glyph boxes within this many degrees of the page text angle keep their detected corners.
GLYPH_ANGLE_TOLERANCE = 3.0


def _box_angle(box) -> float:
    """Top-edge angle in degrees, folded to [-45, 45) (a rectangle repeats every 90 degrees)."""
    dx, dy = (float(v) for v in box[1] - box[0])
    return (math.degrees(math.atan2(dy, dx)) + 45) % 90 - 45


def _box_aspect(box) -> float:
    import numpy as np
    width, height = float(np.linalg.norm(box[1] - box[0])), float(np.linalg.norm(box[3] - box[0]))
    return max(width, height) / max(min(width, height), 1e-6)


def _align_glyph_boxes(boxes, size):
    """Re-frame glyph-sized boxes along the page text angle; every other box is returned as is.

    The page text angle is the median angle of elongated (line) boxes. Without line boxes nothing
    changes. A re-framed box is the rectangle at the page angle that encloses the detected box, so
    no detected ink is cut off; its corners stay in the [tl, tr, br, bl] order _crop expects.
    """
    import numpy as np
    lines = [_box_angle(box) for box in boxes if _box_aspect(box) >= LINE_BOX_MIN_ASPECT]
    if not lines:
        return boxes
    page_angle = float(np.median(lines))
    theta = math.radians(page_angle)
    rotation = np.array([[math.cos(theta), -math.sin(theta)],
                         [math.sin(theta), math.cos(theta)]], dtype=np.float32)
    w, h = size
    aligned = []
    for box in boxes:
        off = (_box_angle(box) - page_angle + 45) % 90 - 45
        if _box_aspect(box) < GLYPH_BOX_MAX_ASPECT and abs(off) > GLYPH_ANGLE_TOLERANCE:
            local = box @ rotation  # rotate by -page_angle: page text axis -> image axis
            (x0, y0), (x1, y1) = local.min(axis=0), local.max(axis=0)
            rect = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32) @ rotation.T
            box = np.clip(rect, (0, 0), (w - 1, h - 1)).astype(np.float32)
        aligned.append(box)
    return aligned


def _crop(image, box):
    import cv2
    import numpy as np
    width = max(1, round(max(np.linalg.norm(box[0] - box[1]), np.linalg.norm(box[2] - box[3]))))
    height = max(1, round(max(np.linalg.norm(box[0] - box[3]), np.linalg.norm(box[1] - box[2]))))
    dst = np.array([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]], dtype=np.float32)
    crop = cv2.warpPerspective(image, cv2.getPerspectiveTransform(box, dst), (width, height), borderMode=cv2.BORDER_REPLICATE)
    return np.rot90(crop) if height / width >= 1.5 else crop


def recognize(png: bytes, size: tuple[int, int]) -> list[OcrWord]:
    # None: not a page-worker thread (one page, or pages read one at a time) -> the single sessions.
    slot = getattr(_worker, 'slot', None)
    # Clear missing-model error even without optional image libraries.
    det, rec, chars = (sessions() if slot is None else
                       page_sessions(slot, getattr(_worker, 'intra', None) or INTRA_OP_THREADS))
    import cv2
    import numpy as np
    image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[1::-1] != tuple(size):
        raise ValueError('own input size must match decoded image pixel size')
    words = []
    for box in _detect(image, det):
        crop = _crop(image, box)
        h, w = crop.shape[:2]
        width = max(320, math.ceil(48 * w / h))
        if width > 4096:
            raise ValueError('own text line exceeds supported width (4096)')
        content_w = min(width, math.ceil(48 * w / h))
        tensor = np.zeros((1, 3, 48, width), dtype=np.float32)
        normalized = cv2.resize(crop, (content_w, 48)).astype(np.float32) / 127.5 - 1
        tensor[0, :, :, :content_w] = normalized.transpose(2, 0, 1)
        pred = rec.run(None, {rec.get_inputs()[0].name: tensor})[0][0]
        text, confidence = ctc_decode(pred, chars)
        if text.strip():
            words.append(OcrWord(text, confidence, polygon_bbox(box, size, size)))
    return mask_words(sorted(words, key=lambda word: (round(word.bbox_px[1] / 15), word.bbox_px[0])))
