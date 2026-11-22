"""주소 → 읍·면·동. 담당자 화면 머리글과 읍면동 관할 필터가 이 값을 쓴다."""
import pytest

from demo.backend.rules.facts import extract_town


@pytest.mark.parametrize(("address", "town"), [
    # 도로명주소의 괄호 참고항목: 괄호가 값에 섞이면 화면에 "(인후동"으로 보였다.
    ("전북특별자치도 전주시 덕진구 동가재미3길 42,2이호 (인후동1가)", "인후동"),
    ("전북특별자시도 전주시 완산구 따박골5길 19-4 (중화산동2가)", "중화산동"),
    ("전북특별자치도 전주시 완산구 효자로 1 (효자동)", "효자동"),
    # 지번주소
    ("전북특별자치도 전주시 완산구 효자동 123", "효자동"),
    ("전북특별자치도 완주군 봉동읍 1", "봉동읍"),
    # 읍면동이 없으면 빈 값 (괄호 안 다른 말을 잡지 않는다)
    ("전라북도 전주시 덕진구 호반로 11", ""),
    ("전북특별자치도 전주시 가상시연로 0 (합성)", ""),
])
def test_extract_town_ignores_parentheses(address, town):
    assert extract_town(address, "전주시" if "전주시" in address else "완주군") == town
