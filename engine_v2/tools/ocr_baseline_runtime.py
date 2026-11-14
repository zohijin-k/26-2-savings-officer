"""Memory-only input and observation adapters for the OCR baseline CLI.

All functions handling document contents must run inside batch.guarded().
No values, images, geometry or dependency exception details are serialized here.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import hashlib
import io
import math
from pathlib import Path
import random
import time
import unicodedata
from unittest.mock import patch

from .ocr_baseline_settings import SETTINGS

_WARM = set()


def page_seed(identifier, page):
    payload = f"{SETTINGS['seed']}\0{identifier}\0{page}".encode('utf-8')
    return int.from_bytes(hashlib.sha256(payload).digest()[:6], 'big')


def quality(text, words):
    """Return fixed exclusion and numeric corruption counts, never input text."""
    from engine_v2.pipeline.preprocess import TEXT_LAYER_MIN_CHARS
    from engine_v2.pipeline.privacy import mask_rrn
    chars = [char for char in text if not char.isspace()]
    counts = dict(characters=len(chars), replacement=sum(c == '\ufffd' for c in chars),
                  private_use=sum(unicodedata.category(c) == 'Co' for c in chars),
                  controls=sum(unicodedata.category(c) in {'Cc', 'Cs'} for c in chars))
    if not text.strip():
        return 'NO_TEXT_LAYER', counts
    if len(mask_rrn(text).strip()) < TEXT_LAYER_MIN_CHARS:
        return 'SHORT_TEXT_LAYER', counts
    settings = SETTINGS['quality']
    if (counts['replacement'] / max(len(chars), 1) >= settings['replacement_ratio'] or
            counts['private_use'] / max(len(chars), 1) >= settings['private_use_ratio'] or
            (counts['replacement'] + counts['private_use'] + counts['controls']) / max(len(chars), 1)
            >= settings['combined_ratio'] or not words):
        return 'BROKEN_TEXT_LAYER', counts
    return 'NONE', counts


def reference_page(source, number):
    from engine_v2.pipeline.ocr import OcrWord
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    size = (math.ceil(source.rect.width * 300 / 72), math.ceil(source.rect.height * 300 / 72))
    # PDF text coordinates are unrotated; page.rect and raster obey page rotation.
    rotation = source.rotation_matrix
    import pymupdf
    words = []
    for item in source.get_text('words'):
        rect = pymupdf.Rect(item[:4]) * rotation
        bounds = tuple(v * 300 / 72 for v in rect)
        if (item[4].strip() and all(math.isfinite(v) for v in bounds) and
                bounds[2] > bounds[0] and bounds[3] > bounds[1]):
            words.append(OcrWord(item[4], 1.0, bounds))
    page = PageImage(0, PageSource.TEXT_LAYER, (source.rect.width, source.rect.height),
                     pixel_size=size, dpi=300)
    return page, words


def variant_image(source, variant, seed, reference_size):
    """Return PageImage plus map from original 300-DPI coordinates to input pixels."""
    import cv2
    import numpy as np
    import pymupdf
    from PIL import Image, ImageFilter
    from engine_v2.pipeline.preprocess import PageImage, PageSource
    params = SETTINGS['variants'][variant]
    pix = source.get_pixmap(dpi=params['dpi'], colorspace=pymupdf.csRGB, alpha=False)
    image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    # Raster dimensions round outward. Coordinates scale by DPI, not by the
    # ratio of rounded canvas widths (which introduces a false clean warp).
    matrix = np.diag([params['dpi'] / 300, params['dpi'] / 300, 1.0])
    if variant == 'scan':
        image = image.convert('L')
    if variant == 'phone':
        rng = random.Random(seed)
        width, height = image.size
        angle = rng.uniform(-params['rotation_degrees'], params['rotation_degrees'])
        rotate = np.vstack([cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1), [0, 0, 1]])
        corners = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
        offsets = np.float32([[rng.uniform(-1, 1) * width * params['perspective_ratio'],
                               rng.uniform(-1, 1) * height * params['perspective_ratio']] for _ in corners])
        project = cv2.getPerspectiveTransform(corners, corners + offsets)
        transform = project @ rotate
        array = cv2.warpPerspective(np.asarray(image), transform, (width, height),
                                    flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
        image = Image.fromarray(array).filter(ImageFilter.GaussianBlur(params['blur_sigma']))
        matrix = transform @ matrix
    if variant != 'clean':
        jpeg = io.BytesIO()
        image.save(jpeg, 'JPEG', quality=params['jpeg_quality'])
        with Image.open(io.BytesIO(jpeg.getvalue())) as decoded:
            image = decoded.convert('RGB')
    png = io.BytesIO()
    image.save(png, 'PNG')
    page = PageImage(0, PageSource.RENDER, (source.rect.width, source.rect.height),
                     png=png.getvalue(), pixel_size=image.size, dpi=params['dpi'])
    return page, matrix


def map_words(words, matrix):
    """Geometry-only projection; all transformed box corners participate."""
    import numpy as np
    result = deepcopy(words)
    for word in result:
        x0, y0, x1, y1 = word.bbox_px
        points = np.array([[x0, y0, 1], [x1, y0, 1], [x1, y1, 1], [x0, y1, 1]]) @ matrix.T
        points = points[:, :2] / points[:, 2:]
        word.bbox_px = tuple(float(v) for v in (*points.min(axis=0), *points.max(axis=0)))
    return result


def recognize(engine, page):
    """Observe original adapters; preserve every original masking call/result."""
    from . import batch_assess as batch
    from engine_v2.pipeline import ocr
    captured = []
    timing = dict(ocr=0.0, detection=None, recognition=None, initialization=None,
                  residual=None, observer=0.0, cold=int(engine not in _WARM),
                  intra_threads=None, inter_threads=None, workers=1)

    def observe_mask(original):
        def call(words):
            if not captured:
                started = time.perf_counter()
                captured.append(deepcopy(words))
                timing['observer'] += time.perf_counter() - started
            return original(words)
        return call

    class Session:
        def __init__(self, original):
            self.original = original

        def __getattr__(self, name):
            return getattr(self.original, name)

        def run(self, *args, **kwargs):
            started = time.perf_counter()
            try:
                return self.original.run(*args, **kwargs)
            finally:
                timing['recognition'] += time.perf_counter() - started

    with ExitStack() as stack:
        stack.enter_context(patch.object(ocr, 'mask_words', observe_mask(ocr.mask_words)))
        if engine == 'own':
            from engine_v2.pipeline.ocr import own
            original_sessions, original_detect = own.sessions, own._detect
            timing.update(detection=0.0, recognition=0.0, initialization=0.0)
            timing['cold'] = int(not original_sessions.cache_info().currsize)

            def sessions():
                started = time.perf_counter()
                try:
                    det, rec, chars = original_sessions()
                finally:
                    timing['initialization'] += time.perf_counter() - started
                options = rec.get_session_options()
                timing.update(intra_threads=options.intra_op_num_threads,
                              inter_threads=options.inter_op_num_threads)
                return det, Session(rec), chars

            def detect(*args, **kwargs):
                started = time.perf_counter()
                try:
                    return original_detect(*args, **kwargs)
                finally:
                    timing['detection'] += time.perf_counter() - started

            stack.enter_context(patch.object(own, 'sessions', sessions))
            stack.enter_context(patch.object(own, '_detect', detect))
            stack.enter_context(patch.object(own, 'mask_words', observe_mask(own.mask_words)))
        started = time.perf_counter()
        try:
            recognized = batch._recognize(engine, page)
        finally:
            timing['ocr'] = max(0.0, time.perf_counter() - started - timing['observer'])
        if engine == 'own':
            timing['residual'] = max(0.0, timing['ocr'] - timing['detection'] -
                                      timing['recognition'] - timing['initialization'])
        _WARM.add(engine)
        return recognized, captured[0] if captured else deepcopy(recognized.words), timing


def extract(page, words, engine):
    from . import batch_assess as batch
    from .ocr_baseline_fields import prepare_pairs
    # A nonexistent neutral virtual path prevents name hints and source rereads.
    path = Path('/__ocr_baseline_memory__/page.pdf')
    return batch._read_pages(path, prepare_pairs(page, words, engine))
