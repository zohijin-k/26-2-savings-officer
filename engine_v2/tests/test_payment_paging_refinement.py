"""Authored margin layouts; no private values or source coordinates."""
import pytest
from engine_v2.extractors import payment_paging
from engine_v2.tests import p2_payment_samples as base


def authored(marker, *, bottom=False, inside=False):
    cells,size=base.payment()
    y=1100 if inside else size[1]*.93 if bottom else size[1]*.135
    cells.append(base.cell(size[0]*.84,y,size[0]*.94,y+28,marker,1))
    return [base.page(cells,size=size)]

@pytest.mark.parametrize('bottom',[False,True])
@pytest.mark.parametrize('marker',['1/2','1 / 2','1／2'])
def test_isolated_margin_folio_is_collected_outside_table(bottom,marker):
    data=payment_paging.collect(authored(marker,bottom=bottom))
    assert data['markers']==[[1,2]]
    assert data['marker_states']==['READABLE']

@pytest.mark.parametrize('marker',['2024/01','2024.01~2024.12','2024/01/02','01/02','1,000/2,000'])
@pytest.mark.parametrize('bottom',[False,True])
def test_dates_periods_and_money_are_never_adopted(marker,bottom):
    data=payment_paging.collect(authored(marker,bottom=bottom))
    assert not any(data['markers'])
    assert 'READABLE' not in data['marker_states']

def test_folio_shaped_body_fraction_is_never_adopted():
    assert not any(payment_paging.collect(authored('1/2',inside=True))['markers'])


def test_duplicate_currents_cannot_be_adopted_in_value_free_statistics():
    p=authored('1/2')
    other=authored('1/2')[0];other[0].page=1;p.append(other)
    data=payment_paging.collect(p)
    assert data['status']=='AMBIGUOUS'
    assert payment_paging.statistics(data)['adopted']=='X'


def test_footer_band_does_not_override_unknown_table_end():
    p=authored('1/2',bottom=True)
    p[0][1].words[:]=[w for w in p[0][1].words if w.text!='합계']
    assert not any(payment_paging.collect(p)['markers'])


@pytest.mark.parametrize('bottom',[False,True])
def test_split_date_cannot_supply_counter_from_another_horizontal_region(bottom):
    from engine_v2.pipeline.ocr import OcrWord
    p=authored('1/1',bottom=bottom)
    words=p[0][1].words
    words[:]=[w for w in words if w.text!='1/1']
    y=2720 if bottom else 35
    for text,box in [('2024',(1240,y,1310,y+35)),('/',(1315,y,1335,y+35)),
                     ('1',(1348,y,1380,y+35)),('/',(1385,y,1400,y+35)),('2',(1405,y,1435,y+35))]:
        words.append(OcrWord(text,1,box))
    assert not any(payment_paging.collect(p)['markers'])


def test_separate_distant_counter_is_not_removed_with_date_on_same_line():
    from engine_v2.pipeline.ocr import OcrWord
    p=authored('1/2')
    p[0][1].words.append(OcrWord('2024/1/2',1,(100,395,330,423)))
    assert payment_paging.collect(p)['markers']==[[1,2]]
