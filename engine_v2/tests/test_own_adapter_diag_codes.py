"""Independent authored token evidence; never load an existing document tree."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace
import unicodedata

import pytest

from engine_v2.pipeline.ocr import OcrWord
from engine_v2.pipeline.preprocess import PageImage, PageSource
from engine_v2.tools import own_adapter_diag_evidence as evidence


def page(scale=1):
    return PageImage(0,PageSource.RENDER,(500,700),pixel_size=(1000*scale,1400*scale),dpi=144*scale)


def word(text,x=100,y=200,width=None,height=20):
    return OcrWord(text,.96,(x,y,x+(width if width is not None else max(20,len(text)*10)),y+height))


def tokens():
    return [word('건강보험료납부확인서',100,40),word('성명',100,100),word('가짜인물',180,100),
            word('생년월일',400,100),word('1990.01.01',510,100),word('직장가입자',100,160),
            word('발급일',100,220),word('2026.11.10',230,220),
            word('월별',100,300),word('고지금액',350,300),word('납부금액',600,300),
            word('2025.10',100,350),word('10000',350,350),word('10000',600,350),
            word('2025.11',100,400),word('10000',350,400),word('10000',600,400),
            word('2025.12',100,450),word('10000',350,450),word('10000',600,450)]


def run(key,reference,observed,*,ref=None,actual=None,kind='NHIS_PAYMENT',observed_kind='NHIS_PAYMENT',canvas=None):
    canvas=canvas or page()
    if ref is None:
        result,ref,_=evidence.extract_with_form(canvas,reference,'text_layer')
        assert result.detected_doc_type.name == kind
    if actual is None:
        result,actual,_=evidence.extract_with_form(canvas,observed,'own')
        observed_kind=result.detected_doc_type.name if result.detected_doc_type else 'X'
    return evidence.diagnose(canvas,reference,observed,kind,key,ref,actual,observed_kind,'own')


def remove(words,text):
    return [deepcopy(w) for w in words if w.text!=text]


def test_actual_dispatch_same_result_and_legacy_form():
    from engine_v2.tools import ocr_baseline_runtime as runtime
    reference=tokens();before=deepcopy(reference)
    ordinary,raw=runtime.extract(page(),reference,'text_layer')
    observed,observed_raw,form=evidence.extract_with_form(page(),reference,'text_layer')
    assert observed_raw == raw and observed.fields == ordinary.fields
    assert form=='LEGACY' and reference==before


@pytest.mark.parametrize('key', ('가입구분', '고지월', '발급일'))
def test_route_mismatch_precedes_missing_label_and_unsupported_evidence(key):
    assert evidence.diagnose(page(), tokens(), [], 'NHIS_PAYMENT', key,
        {key: '2026-11-10'}, {}, 'NHIS_PAYMENT', 'own',
        'GOVERNMENT', 'LEGACY') == 'ROUTE_MISMATCH'


@pytest.mark.parametrize('value', ('2026-11-10', date(2026, 11, 10)))
def test_ok_precedes_route_mismatch(value):
    assert evidence.diagnose(page(), tokens(), [], 'NHIS_PAYMENT', '발급일',
        {'발급일': '2026-11-10'}, {'발급일': value}, 'NHIS_PAYMENT', 'own',
        'GOVERNMENT', 'LEGACY') == 'OK'


def test_missing_reference_remains_unavailable_on_route_mismatch():
    assert evidence.diagnose(page(), [], [], 'NHIS_PAYMENT', '가입구분',
        {}, {}, 'NHIS_PAYMENT', 'own', 'GOVERNMENT', 'LEGACY') == 'REFERENCE_MISSING'


@pytest.mark.parametrize('observed_form,expected', (
    ('LEGACY', 'ROUTE_MISMATCH'), ('GOVERNMENT', 'CLASSIFICATION_FAILED')))
def test_route_mismatch_precedes_classification_failure(observed_form, expected):
    assert evidence.diagnose(page(), [], [], 'NHIS_PAYMENT', '발급일',
        {'발급일': '2026-11-10'}, {}, 'X', 'own', 'GOVERNMENT', observed_form) == expected


def test_matching_route_keeps_label_diagnosis():
    assert evidence.diagnose(page(), tokens(), [], 'NHIS_PAYMENT', '발급일',
        {'발급일': '2026-11-10'}, {}, 'NHIS_PAYMENT', 'own',
        'LEGACY', 'LEGACY') == 'LABEL_NOT_FOUND'


@pytest.mark.parametrize('key',('가입구분','고지월','발급일'))
def test_ok_actual_original_extractors(key):
    reference=tokens()
    assert run(key,reference,deepcopy(reference))=='OK'


def test_absent_membership_label_is_not_required():
    reference=tokens()
    assert all('가입구분' not in w.text for w in reference)
    observed=remove(reference,'직장가입자')
    assert run('가입구분',reference,observed)=='VALUE_NOT_FOUND'


def test_label_not_found_wins_over_missing_date():
    reference=tokens();observed=remove(remove(reference,'발급일'),'2026.11.10')
    assert run('발급일',reference,observed)=='LABEL_NOT_FOUND'


def test_spaced_required_anchor_is_distinct_from_absence():
    reference=tokens();observed=remove(remove(reference,'발급일'),'2026.11.10')
    observed.extend([word('발 급 일',100,220),word('2026.11.1O',230,220)])
    assert run('발급일',reference,observed)=='LABEL_SPACED'


def test_split_required_anchor_uses_adjacent_boxes():
    reference=tokens();observed=remove(remove(reference,'발급일'),'2026.11.10')
    observed.extend([word('발',100,220,width=10),word('급',112,220,width=10),word('일',124,220,width=10)])
    observed.append(word('2026.11.1O',230,220))
    assert run('발급일',reference,observed)=='LABEL_SPLIT'


def test_split_anchor_can_span_three_immediately_adjacent_lines():
    reference=tokens();observed=remove(remove(reference,'발급일'),'2026.11.10')
    observed.extend([word('발',100,200,width=10,height=10),word('급',100,215,width=10,height=10),
                     word('일',100,230,width=10,height=10),word('2026.11.1O',230,220)])
    # This is a bounded token-connection predicate fixture. Actual extraction
    # is still used, and its wrong/missing date must not be replaced.
    assert run('발급일',reference,observed)=='LABEL_SPLIT'


def test_nonfinite_geometry_is_conservative():
    reference=tokens();observed=remove(reference,'2026.11.10')
    observed.append(OcrWord('2026.11.1O',.96,(230,220,float('inf'),240)))
    assert run('발급일',reference,observed,ref={'발급일':'2026-11-10'},actual={})=='OTHER'


def test_label_is_not_joined_across_other_columns():
    reference=tokens();observed=remove(remove(reference,'발급일'),'2026.11.10')
    observed.extend([word('발',100,220,width=10),word('급일',800,220,width=20)])
    observed.append(word('2026.11.1O',230,220))
    assert run('발급일',reference,observed)=='LABEL_NOT_FOUND'


def test_value_not_found_requires_no_aligned_candidate():
    reference=tokens();observed=remove(reference,'2026.11.10')
    assert run('발급일',reference,observed)=='VALUE_NOT_FOUND'


def test_same_line_date_placed_below_header_is_other_line():
    reference=tokens();observed=remove(reference,'2026.11.10')
    observed.append(word('2026.11.10',100,260))
    assert run('발급일',reference,observed)=='VALUE_OTHER_LINE'


def test_unlabeled_confirmation_date_does_not_require_header_label():
    reference=remove(remove(tokens(),'발급일'),'2026.11.10')
    reference.extend([word('위와같이확인합니다',100,850),word('2026.11.10',100,900),
                      word('국민건강보험공단이사장',100,950)])
    observed=remove(reference,'2026.11.10')
    assert run('발급일',reference,observed)=='VALUE_NOT_FOUND'


def test_pattern_mismatch_has_same_date_parts_and_region():
    reference=tokens();observed=remove(reference,'2026.11.10')
    observed.append(word('2026:11:10',230,220))
    assert run('발급일',reference,observed)=='PATTERN_MISMATCH'


def test_character_error_requires_unique_aligned_candidate():
    reference=tokens();observed=remove(reference,'2026.11.10')
    observed.append(word('2026.11.1O',230,220))
    assert run('발급일',reference,observed)=='OCR_CHAR'


def test_multiple_aligned_candidates_stay_other():
    reference=tokens();observed=remove(reference,'2026.11.10')
    observed.extend([word('2026.11.1O',230,220),word('2026.11.1Q',230,220)])
    assert run('발급일',reference,observed)=='OTHER'


def test_identical_duplicate_observations_are_not_collapsed():
    reference=tokens();observed=remove(reference,'2026.11.10')
    observed.extend([word('2026.11.1O',230,220),word('2026.11.1O',230,220)])
    assert run('발급일',reference,observed)=='OTHER'


def test_unrelated_print_label_does_not_make_confirmation_date_labeled():
    reference=remove(remove(tokens(),'발급일'),'2026.11.10')
    reference.extend([word('출력일',700,700),
                      word('위와같이확인합니다',100,850),word('2026.11.10',100,900),
                      word('국민건강보험공단이사장',100,950)])
    observed=remove(reference,'2026.11.10')
    assert run('발급일',reference,observed)=='VALUE_NOT_FOUND'


def test_duplicate_or_moved_required_label_is_conservative():
    reference=tokens();observed=remove(remove(reference,'발급일'),'2026.11.10')
    observed.extend([word('발 급 일',800,220),word('2026.11.1O',230,220)])
    assert run('발급일',reference,observed)=='OTHER'
    observed.append(word('발 급 일',100,220))
    assert run('발급일',reference,observed)=='OTHER'


def test_other_column_exact_value_does_not_explain_target_cell():
    reference=tokens();observed=remove(reference,'2026.11.10')
    observed.append(word('2026.11.10',800,260))
    assert run('발급일',reference,observed)=='OTHER'


def test_billing_month_components_are_not_one_literal_list():
    reference=tokens()
    assert not any('2025-10,2025-11,2025-12' in w.text for w in reference)
    observed=remove(reference,'2025.11')
    assert run('고지월',reference,observed)=='VALUE_NOT_FOUND'


def test_one_bad_month_character_with_other_components_unchanged():
    reference=tokens();observed=remove(reference,'2025.11')
    observed.append(word('2025.1I',100,400))
    assert run('고지월',reference,observed)=='OCR_CHAR'


def test_month_with_neighbor_amount_is_structure_not_character_substitution():
    reference=tokens();observed=remove(reference,'2025.11')
    observed.append(word('2025.110',100,400,width=100))
    assert run('고지월',reference,observed)=='OTHER'


def test_month_only_literal_inside_composite_box_is_not_ocr_char():
    reference=[word('월별',100,200),word('2025년',300,200),word('11월',100,250)]
    observed=[word('월별',100,200),word('2025년',300,200),word('11월0',100,250)]
    assert run('고지월',reference,observed,ref={'고지월':'2025-11'},actual={})=='OTHER'


def test_merged_month_rows_require_visible_pieces_and_successful_original_replay():
    reference=tokens()+[word('합계',100,520),word('30000',350,520)]
    observed=reference
    for text in ('2025.10','2025.11','2025.12','합계'):
        observed=remove(observed,text)
    observed.append(word('2025.10 2025.11 2025.12 합계',100,350,width=100,height=190))
    before=deepcopy(observed)
    assert run('고지월',reference,observed)=='LINE_MERGED'
    assert observed==before


@pytest.mark.parametrize('mode', ('other-column', 'other-row', 'duplicate'))
def test_merged_month_replay_cannot_transplant_or_disambiguate_boxes(mode,monkeypatch):
    reference=tokens()+[word('합계',100,520),word('30000',350,520)]
    observed=reference
    for text in ('2025.10','2025.11','2025.12','합계'):
        observed=remove(observed,text)
    merged=word('2025.10 2025.11 2025.12 합계',
                800 if mode=='other-column' else 100,
                520 if mode=='other-row' else 350,
                width=100,height=20 if mode=='other-row' else 190)
    observed.append(merged)
    if mode=='other-row':
        # The target cells have unique wrong observations, while the correct
        # literal pieces appear elsewhere. Their boxes cannot be transplanted.
        observed.extend(word(text,100,y) for text,y in (('X',350),('Y',400),('Z',450)))
    if mode=='duplicate':
        observed.append(deepcopy(merged))
    monkeypatch.setattr(evidence,'_replay',lambda *args: pytest.fail('unsupported replay'))
    before=deepcopy(observed)
    assert run('고지월',reference,observed)=='OTHER'
    assert observed==before


def test_order_only_replay_preserves_same_characters_and_boxes():
    reference=remove(tokens(),'2026.11.10')
    reference.extend([word('2026.',230,220,width=40),word('11.',230,220,width=40),word('10',230,220,width=40)])
    observed=deepcopy(reference[:-3])+list(reversed(deepcopy(reference[-3:])))
    before=deepcopy(observed)
    assert run('발급일',reference,observed)=='ORDER'
    assert observed==before


def test_normalize_replay_removes_only_declared_zero_width_whitespace():
    reference=tokens();observed=remove(reference,'2026.11.10')
    observed.append(word('2026.\u200b11.10',230,220))
    before=deepcopy(observed)
    assert run('발급일',reference,observed)=='NORMALIZE'
    assert observed==before


def test_parentheses_date_grammar_is_not_rewritten_by_normalization():
    reference=tokens();observed=remove(reference,'2026.11.10')
    observed.append(word('2026(11)10',230,220))
    assert run('발급일',reference,observed)=='PATTERN_MISMATCH'


@pytest.mark.parametrize('rotation',(90,180,270))
def test_rotated_coordinate_evidence_has_no_orientation_guess(rotation):
    reference=tokens();observed=remove(reference,'2026.11.10');observed.append(word('2026.11.1O',230,220))
    def point(x,y):
        return (1400-y,x) if rotation==90 else (1000-x,1400-y) if rotation==180 else (y,1000-x)
    for item in reference+observed:
        x0,y0,x1,y1=item.bbox_px
        corners=[point(x,y) for x in (x0,x1) for y in (y0,y1)]
        item.bbox_px=(min(p[0] for p in corners),min(p[1] for p in corners),max(p[0] for p in corners),max(p[1] for p in corners))
    size=(1400,1000) if rotation in (90,270) else (1000,1400)
    canvas=PageImage(0,PageSource.RENDER,(size[0]/2,size[1]/2),pixel_size=size,dpi=144)
    assert run('발급일',reference,observed,ref={'발급일':'2026-11-10'},actual={},canvas=canvas)=='OCR_CHAR'


def test_missing_and_unsupported_reference_are_separate():
    reference=tokens()
    assert run('가입구분',reference,reference,ref={},actual={})=='REFERENCE_MISSING'
    assert run('가입구분',[],[],ref={'가입구분':'직장'},actual={})=='REFERENCE_UNATTRIBUTABLE'
    assert run('월별납부내역',reference,reference,ref={'월별납부내역':[{'월':'2025-10'}]},actual={})=='REFERENCE_UNATTRIBUTABLE'


def test_other_registered_fields_report_match_without_causal_invention():
    reference=tokens()
    assert run('성명',reference,reference,ref={'성명':'가짜'},actual={'성명':'가짜'})=='OK'
    assert run('성명',reference,reference,ref={'성명':'가짜'},actual={'성명':'다름'})=='REFERENCE_UNATTRIBUTABLE'


@pytest.mark.parametrize('text',('２０２６．１１．１０',unicodedata.normalize('NFD','2026년11월10일'),'2026／11／10'))
def test_already_normalized_original_path_is_ok(text):
    reference=tokens();observed=remove(reference,'2026.11.10');observed.append(word(text,230,220))
    assert run('발급일',reference,observed)=='OK'


@pytest.mark.parametrize('scale',(1,2,3))
def test_scale_does_not_change_evidence(scale):
    reference=tokens();observed=remove(reference,'2026.11.10');observed.append(word('2026.11.1O',230,220))
    for item in reference+observed:
        item.bbox_px=tuple(v*scale for v in item.bbox_px)
    assert run('발급일',reference,observed,canvas=page(scale))=='OCR_CHAR'


def test_wrapper_restoration_on_nested_exception(monkeypatch):
    from engine_v2.tools import ocr_baseline_runtime as runtime
    from engine_v2.extractors import nhis_payment,nhis_payment_gov
    original=nhis_payment.extract,nhis_payment_gov.extract
    def fail(*args,**kwargs):
        raise RuntimeError('AUTHORED_SENTINEL')
    monkeypatch.setattr(runtime,'extract',fail)
    with pytest.raises(RuntimeError):
        evidence.extract_with_form(page(),tokens(),'own')
    assert (nhis_payment.extract,nhis_payment_gov.extract)==original


def test_comparison_separates_raw_and_normalized():
    assert evidence.comparison('NHIS_PAYMENT','발급일',{'발급일':'2026.11.10'},
                               {'발급일':'2026-11-10'},'NHIS_PAYMENT')==(False,True)


def test_replay_delegates_runtime_path_and_preserves_words(monkeypatch):
    from engine_v2.tools import ocr_baseline_runtime as runtime
    words=tokens();before=deepcopy(words);calls=[]
    def extract(canvas,observed,engine):
        calls.append((canvas,observed,engine))
        return SimpleNamespace(detected_doc_type=SimpleNamespace(name='NHIS_PAYMENT')),{'발급일':'2026-11-10'}
    monkeypatch.setattr(runtime,'extract',extract)
    assert evidence._replay(page(),words,'NHIS_PAYMENT','발급일',{'발급일':'2026-11-10'},'own')
    assert len(calls)==1 and calls[0][1] is words and words==before
