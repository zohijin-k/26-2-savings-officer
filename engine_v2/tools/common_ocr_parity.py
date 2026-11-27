"""Common OCR parity between savings-officer and youth (11-27).

Both backends must run the same verified OCR technology (page rendering, preprocessing, PP-OCRv5 ONNX
recognition, thread scheduling, shared-image marks, resident-abstract structure extraction and its
completeness signals) while each keeps its own Document AI rules. This module hashes exactly that
common part. ``engine_v2/common_ocr_manifest.json`` is byte-identical in both repositories.

  python -m engine_v2.tools.common_ocr_parity --check            # this checkout matches the manifest
  python -m engine_v2.tools.common_ocr_parity --write            # regenerate after a reviewed common change
  python -m engine_v2.tools.common_ocr_parity --compare OTHER    # compare two checkouts directly

A common change is made in both repositories together and the manifest is regenerated in both; a
difference in either repository fails its test (demo/backend/tests/test_common_ocr_parity.py).
Outputs are hashes and names only (no document content).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'engine_v2' / 'common_ocr_manifest.json'

#: Whole files that are common OCR technology (byte-identical in both repositories).
COMMON_GLOBS = (
    'engine_v2/pipeline/**/*.py',
    'engine_v2/extractors/resident_abstract.py',
    'engine_v2/extractors/address_dates.py',
    'engine_v2/tools/fetch_own_models.py',
    'engine_v2/tools/common_ocr_parity.py',
    'demo/backend/ocr/__init__.py',
    'demo/backend/ocr/base.py',
    'demo/backend/ocr/file_evidence.py',
    'demo/backend/ocr/fixture.py',
    'demo/backend/ocr/jbai.py',
    'demo/backend/ocr/upstage.py',
)

#: Mixed files: every top-level block is common except the business-specific ones named here.
#: Excluded blocks are each business's Document AI and may differ (listed, never hashed).
MIXED = {
    'demo/backend/ocr/localocr.py': {
        'exclude': (
            '_business_resident_marks',  # 두배적금 '열람용' 표시 (11-18 S3); youth: 없음
            '_from_nhis', '_from_insurance4', '_from_supported_form',  # 두배적금 납부확인서·4대보험 판독 정책 (11-19~21)
        ),
    },
    'demo/backend/ocr/pdftext.py': {
        'exclude': (
            'read_page_text',  # 글자층 판독 결과에 '열람용' 표시를 붙이는 두배적금 정책 (11-18 S3)
            'VIEWING_COPY_NOTE', 'VIEWING_COPY_FIELD', 'viewing_copy_note', 'mark_viewing_copy',
        ),
    },
    #: Only the resident page-integrity check and the history reason legend are common in doc_check;
    #: every other rule is business Document AI (``include`` lists the common blocks).
    'demo/backend/rules/doc_check.py': {
        'include': ('CODE_PAGE_IMAGE_SHARED', 'RESIDENT_HISTORY_REASON_LEGEND',
                    '_repeats_from_shared_image', '_check_resident_pages'),
    },
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blocks(text: str) -> dict[str, str]:
    """Top-level name -> exact source (with its leading comment lines)."""
    lines = text.splitlines(keepends=True)
    out: dict[str, str] = {}
    for node in ast.parse(text).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue
        start = (node.decorator_list[0].lineno if getattr(node, 'decorator_list', None) else node.lineno) - 1
        while start > 0 and lines[start - 1].lstrip().startswith('#'):
            start -= 1
        for name in names:
            out[name] = ''.join(lines[start:node.end_lineno])
    return out


def compute(root: Path = ROOT) -> dict:
    files = sorted({str(path.relative_to(root)) for pattern in COMMON_GLOBS for path in root.glob(pattern)
                    if '__pycache__' not in path.parts})
    mixed = {}
    for rel, rule in MIXED.items():
        found = blocks((root / rel).read_text(encoding='utf-8'))
        names = (rule['include'] if 'include' in rule else
                 [name for name in found if name not in rule['exclude']])
        mixed[rel] = {'excluded': sorted(rule.get('exclude', ())) or 'all blocks not listed',
                      'blocks': {name: _sha(found[name].encode()) if name in found else None for name in sorted(names)}}
    from engine_v2.tools.fetch_own_models import ASSETS
    return {
        'note': 'Common OCR parity manifest (savings-officer == youth). Regenerate with --write in BOTH repositories.',
        'models': {name: sha for name, (_, sha) in sorted(ASSETS.items())},
        'files': {rel: _sha((root / rel).read_bytes()) for rel in files},
        'mixed': mixed,
    }


def differences(expected: dict, actual: dict) -> list[str]:
    out = []
    for key in ('models', 'files'):
        for name in sorted(set(expected.get(key, {})) | set(actual.get(key, {}))):
            if expected.get(key, {}).get(name) != actual.get(key, {}).get(name):
                out.append(f'{key}: {name}')
    for rel in sorted(set(expected.get('mixed', {})) | set(actual.get('mixed', {}))):
        e = expected.get('mixed', {}).get(rel, {}).get('blocks', {})
        a = actual.get('mixed', {}).get(rel, {}).get('blocks', {})
        out += [f'mixed: {rel}::{name}' for name in sorted(set(e) | set(a)) if e.get(name) != a.get(name)]
    return out


def dump(manifest: dict) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + '\n'


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='common_ocr_parity')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--write', action='store_true')
    group.add_argument('--compare', metavar='OTHER_REPO_ROOT')
    args = parser.parse_args(argv)
    actual = compute()
    if args.write:
        MANIFEST.write_text(dump(actual), encoding='utf-8')
        print(f'written {MANIFEST.relative_to(ROOT)} sha256={_sha(MANIFEST.read_bytes())}')
        return 0
    if args.compare:
        other = Path(args.compare).resolve()
        found = differences(compute(other), actual)
        print('\n'.join(found) if found else 'COMMON_OCR_IDENTICAL')
        return 1 if found else 0
    found = differences(json.loads(MANIFEST.read_text(encoding='utf-8')), actual)
    print('\n'.join(found) if found else f'COMMON_OCR_MATCHES_MANIFEST sha256={_sha(MANIFEST.read_bytes())}')
    return 1 if found else 0


if __name__ == '__main__':
    raise SystemExit(main())
