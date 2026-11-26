"""시나리오 테스트 공통 준비."""

from pathlib import Path

from demo.backend.ocr.fixture import enable_synthetic_fixture_ocr_for_tests

# 합성 시나리오 시험은 생성기 샘플의 고정 판독 결과에 기대므로 이 시험 패키지 안에서만
# fixture 판독을 명시적으로 켠다. 앱을 정상 실행하면 꺼져 있다(test_fixture_ocr_isolation).
enable_synthetic_fixture_ocr_for_tests()

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "samples"


def ensure_demo_samples() -> None:
    """깨끗한 체크아웃에서 첫 시나리오 실행 전 시연 PDF를 생성한다."""
    if SAMPLES_DIR.is_dir() and any(SAMPLES_DIR.glob("*.pdf")):
        return
    from demo.fixtures.make_samples import main as make_samples

    make_samples()


ensure_demo_samples()
