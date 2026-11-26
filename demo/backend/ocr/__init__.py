"""OCR 폴백 체인.

Tier1(fixture) → Tier1.2(전북AI OCR) → Tier1.5(로컬 OCR, engine_v2) → Tier2(PDF 텍스트)
→ Tier3(상용 API) 순으로 시도하고, 전부 미스면
신뢰도 0짜리 결과를 돌려준다. 신뢰도 0은 엔진에서 NEEDS_REVIEW가 되어 담당자 큐로
가므로, 어떤 파일이 올라와도 화면이 멈추지 않는다.

설계 근거: .trellis/tasks/09-16-demo-site/design.md 4절
"""

import time
from engine_v2.pipeline.privacy import mask_data, mask_rrn

from ..rules.doc_types import DocType
from .base import BBox, OcrAdapter, OcrFallback, OcrResult
from .fixture import NAME as FIXTURE_TIER, FixtureOcr, fixture_ocr_enabled, fixture_keys
from .jbai import JbaiOcr
from .localocr import LocalOcr, ensure_nhis_required_fields, ensure_business_required_fields, exception_code
from .pdftext import PdfTextOcr, split_pdf_pages
from .upstage import UpstageOcr

#: 시도 순서. 앞 계층이 None을 돌려주면 다음으로 넘어간다.
#: FixtureOcr는 기본으로 꺼져 있어 정상 실행에서는 항상 None이다. 합성 시험만 명시적으로 켠다
#: (`fixture.synthetic_fixture_ocr`).
#: 전북AI(JbaiOcr)는 JBAI_API_KEY·JBAI_ALLOW_REAL_DOCS가 모두 있을 때만, 판독기가 있는 서류
#: (초본·등본·납부확인서·자격득실)의 텍스트 레이어 없는 파일을 맡는다. 실패하면 OcrFallback으로
#: 사유를 남기고 LocalOcr가 이어받는다.
#: LocalOcr는 텍스트 레이어가 **없는** 파일(브라우저 인쇄 PDF·사진)만 맡고, 텍스트 PDF는
#: None을 돌려 Tier2에 넘긴다. OCR 엔진이 없는 서버에서도 None → 기존 동작 그대로.
CHAIN: list[OcrAdapter] = [FixtureOcr(), JbaiOcr(), LocalOcr(), PdfTextOcr(), UpstageOcr()]


def read_document(file_path: str, expected: DocType | None = None) -> OcrResult:
    """서류 한 건을 판독한다. 예외를 밖으로 내보내지 않는다."""
    started = time.perf_counter()
    result: OcrResult | None = None
    fallback_reasons: list[str] = []
    fallback_result: OcrResult | None = None

    for adapter in CHAIN:
        try:
            result = adapter.read(file_path, expected)
        except OcrFallback as fallback:
            fallback_reasons.append(fallback.reason)  # 담당자 화면에 대체 사유로 남긴다
            if fallback.fallback_result is not None:
                fallback_result = fallback.fallback_result
            result = None
        except NotImplementedError:
            result = None  # 미구성 계층은 조용히 건너뛴다
        except Exception as exc:  # noqa: BLE001 - 한 계층이 터져도 다음으로 넘어가야 한다
            # 예외 문장에는 서류 내용이 섞일 수 있어 클래스 이름만 대체 사유로 남긴다.
            fallback_reasons.append(f"{str(getattr(adapter, 'name', 'tier')).upper()}_EXCEPTION:{exception_code(exc)}")
            result = None
        if result is not None:
            break

    if result is not None and result.tier == FIXTURE_TIER and not fixture_ocr_enabled():
        # 불변식: fixture 판독이 켜지지 않은 프로세스에서는 어떤 업로드 파일도 검증을 건너뛰는
        # fixture 결과를 받지 않는다. 자동 판독 실패로 처리해 담당자가 확인하게 한다.
        fallback_reasons.append("FIXTURE_DISABLED")
        result = None

    if result is None:
        result = fallback_result or OcrResult(
            detected_doc_type=None,
            confidence=0.0,
            image_quality=1.0,  # Recognition failure is not an image measurement.
            fields={"판독실패": "자동 판독이 되지 않아 담당자가 직접 확인합니다."},
            tier="none",
        )
        if fallback_result is not None:
            result.confidence = min(result.confidence, 0.4)

    # 어느 엔진으로 읽었는지와 대체 사유는 담당자 화면 전용이다 (신청자 응답에는 싣지 않는다).
    if not result.engine:
        result.engine = result.tier
    if fallback_reasons and not result.fallback_reason:
        result.fallback_reason = " / ".join(fallback_reasons)
    elif fallback_reasons and result.fallback_reason.startswith("RENDER_RETRY"):
        # LocalOcr 안의 렌더링 대체 판독 사유는 앞 계층 사유 뒤에 이어 둔다.
        result.fallback_reason = " / ".join([*fallback_reasons, result.fallback_reason])

    # 모든 OCR 계층이 공통으로 지난 뒤 추출값이 머리표만으로 구성됐는지 확인한다.
    from pathlib import Path
    import sys

    repo_root = str(Path(__file__).resolve().parents[3])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from engine_v2.pipeline.field_safety import remove_header_only_fields

    for key in remove_header_only_fields(result.fields):
        result.bboxes.pop(key, None)

    ensure_nhis_required_fields(result)
    ensure_business_required_fields(result)

    from .file_evidence import attach_file_evidence, normalize_image_quality
    attach_file_evidence(result, file_path)
    normalize_image_quality(result, file_path)

    result.fields = mask_data(result.fields)
    result.fallback_reason = mask_rrn(result.fallback_reason)
    result.quality_note = mask_rrn(result.quality_note)
    result.classification_evidence = mask_rrn(result.classification_evidence)

    result.elapsed_ms = int((time.perf_counter() - started) * 1000)
    return result


__all__ = [
    "BBox",
    "CHAIN",
    "OcrAdapter",
    "OcrResult",
    "fixture_keys",
    "read_document",
    "split_pdf_pages",
]
