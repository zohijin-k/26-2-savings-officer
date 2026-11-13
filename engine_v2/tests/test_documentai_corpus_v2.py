"""Synthetic corpus integrity; never read any real/private document."""
from collections import Counter,defaultdict
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from engine_v2.pipeline.ocr import OcrWord
from engine_v2.tools import documentai_corpus_v2 as corpus,documentai_synth as old


def test_five_unique_sources_and_unchanged_original_layout_and_labels():
    for kind in corpus.DOCS:
        legacy=next(s for s in old.sources(0) if s.doc==kind)
        variants=[next(s for s in corpus.sources(n) if s.doc==kind) for n in range(5)]
        assert len({corpus.source_fingerprint(source) for source in variants})==5
        for source in variants:
            assert set(source.truth)==set(legacy.truth)
            assert len(source.pages)==len(legacy.pages)
            for (cells,size),(previous,old_size) in zip(source.pages,legacy.pages):
                assert size==old_size
                assert [(x,y,pt) for x,y,_,pt in cells]==[(x,y,pt) for x,y,_,pt in previous]
                assert len(cells)==len(previous)
        if kind=='insurance_4':
            for source in variants:
                texts=[cell[2] for cells,_ in source.pages for cell in cells]
                assert '확인용' in texts
                assert '가입자 가입내역 확인서' in texts
        assert variants[0].identity!=variants[4].identity


def test_source_dates_are_independent_consistent_and_font_glyphs_present():
    for n in (0,4):
        for source in corpus.sources(n):
            issued=source.truth['issue_date' if source.doc=='resident_abstract' else '발급일']
            assert issued==f'2026-03-{n+3:02}'
            image,words,metadata=corpus.rendered(source)
            assert image.size==(2480,3509)
            assert words and metadata['missing_glyphs']==0
            assert metadata['font']=='Droid Sans Fallback Regular'
            if source.doc=='insurance_4':
                printed=' '.join(cell[2] for cells,_ in source.pages for cell in cells)
                assert f'2026.03.{n+4:02} 09:30' in printed


def test_reference_geometry_matches_rotation_and_resolution():
    image=Image.new('RGB',(100,140),'white')
    words=[OcrWord('가상',.5,(10,20,20,30))]
    rotated,reference=corpus.transformed(image,words,'rotate90',np.random.default_rng(7))
    assert rotated.size==(140,100)
    assert reference[0].bbox_px==pytest.approx((20,80,30,90))
    assert reference[0].confidence==1
    small,reference=corpus.transformed(image,words,'low_resolution',np.random.default_rng(7))
    assert reference[0].bbox_px==pytest.approx((2.4,20*34/140,4.8,30*34/140))
    for condition in ('original','monochrome','rotate_plus5','rotate_minus5','phone'):
        picture,reference=corpus.transformed(image,words,condition,np.random.default_rng(9))
        assert reference[0].text==words[0].text
        x0,y0,x1,y1=reference[0].bbox_px
        assert 0<=x0<x1<=picture.width and 0<=y0<y1<=picture.height
    assert words[0].confidence==.5 and words[0].bbox_px==(10,20,20,30)


def test_layout_stress_preserves_every_source_character_and_original():
    source=next(corpus.sources())
    before=deepcopy(source)
    changed=corpus.layout_variant(source,4)
    assert source==before
    assert [cell[2:] for cells,_ in changed.pages for cell in cells]==[cell[2:] for cells,_ in source.pages for cell in cells]
    assert changed.pages!=source.pages
    assert changed.truth==source.truth


def test_case_taxonomy_and_varied_issue_truth_are_authored_before_verdict(monkeypatch):
    # Real text-layer words still come from generated synthetic PDFs; only the
    # large raster operation is replaced to keep this integrity check cheap.
    original=corpus.rendered
    def tiny(source):
        image,words,meta=original(source)
        return Image.new('RGB',(100,140),'white'),words,meta
    monkeypatch.setattr(corpus,'rendered',tiny)
    source=next(s for s in corpus.sources(4) if s.doc=='nhis_payment')
    cases=list(corpus.cases_for_source(source,4,np.random.default_rng(6)))
    grouped={case['condition']:case for case in cases}
    assert len(cases)==17
    assert grouped['original']['group']=='normal_baseline'
    assert grouped['original']['expected']=='VALID'
    for condition in ('monochrome','rotate_plus5','rotate_minus5','rotate90','phone','layout_variant'):
        assert grouped[condition]['group']=='stress' and grouped[condition]['expected']=='VALID'
    for condition in ('low_resolution','defect_low_resolution','low_image_quality'):
        assert grouped[condition]['group']=='quality_defect' and grouped[condition]['expected']=='FAIL'
    assert grouped['issued_too_early']['source'].truth['발급일']=='2024-03-07'
    assert grouped['issued_after_application']['source'].truth['발급일']=='2027-03-07'
    assert grouped['unreadable_file']['image'] is None
    assert grouped['wrong_document_type']['slot_doc']!=source.doc
    assert all(case['expected']=='FAIL' for case in cases if case['group']=='content_defect')


def test_new_results_refuse_to_overwrite_any_previous_report(tmp_path):
    output=tmp_path/'existing.json';output.write_text('previous')
    with pytest.raises(ValueError,match='OUTPUT_EXISTS'):corpus.run(output)
    assert output.read_text()=='previous'
    output.unlink();output.with_suffix('.md').write_text('old report')
    with pytest.raises(ValueError,match='OUTPUT_EXISTS'):corpus.run(output)
    assert output.with_suffix('.md').read_text()=='old report'


def test_output_extension_cannot_alias_numeric_and_markdown_artifacts(tmp_path):
    output=tmp_path/'result.md'
    with pytest.raises(ValueError,match='OUTPUT_FORMAT_INVALID'):corpus.run(output)
    assert not output.exists()


def test_each_submitted_invalid_sample_is_distinct_and_checkpoint_is_value_free(monkeypatch,tmp_path):
    from engine_v2.tools import documentai_staged as staged
    def negative(source,sample,rng):
        yield {'condition':'unreadable_file','group':'content_defect','expected':'FAIL',
               'image':None,'reference_words':[],'source':source,'slot_doc':source.doc,'font':{}}
    monkeypatch.setattr(corpus,'cases_for_source',negative)
    monkeypatch.setattr(staged,'measure_stage',lambda path,doc,truth,**kw:staged.failure_stage(doc,truth))
    output=tmp_path/'numbers.json'
    result=corpus.run(output,samples=5)
    assert len(result['rows'])==25
    for kind in corpus.DOCS:
        rows=[row for row in result['rows'] if row['doc']==kind]
        assert len({row['input_fingerprint'] for row in rows})==5
    checkpoint=output.with_suffix('.rows.jsonl').read_text()
    assert len(checkpoint.splitlines())==25
    assert '가상가가' not in checkpoint and str(tmp_path) not in checkpoint


def test_duplicate_submitted_images_are_rejected_even_if_source_parameters_differ(monkeypatch,tmp_path):
    from engine_v2.tools import documentai_staged as staged
    def repeated(source,sample,rng):
        yield {'condition':'original','group':'normal_baseline','expected':'VALID',
               'image':Image.new('RGB',(100,140),'white'),'reference_words':[],
               'source':source,'slot_doc':source.doc,'font':{}}
    monkeypatch.setattr(corpus,'cases_for_source',repeated)
    monkeypatch.setattr(staged,'measure_stage',lambda path,doc,truth,**kw:staged.failure_stage(doc,truth))
    output=tmp_path/'numbers.json'
    with pytest.raises(ValueError,match='DUPLICATE_INPUT'):corpus.run(output,samples=5)
    assert not output.exists()
    assert output.with_suffix('.rows.jsonl').exists()


def test_negative_year_truth_follows_every_printed_metadata_date_not_only_issue(tmp_path):
    source=next(s for s in corpus.sources(4) if s.doc=='nhis_qualification')
    original=deepcopy(source)
    early=corpus.negative_date_truth(source,2024)
    future=corpus.negative_date_truth(source,2027)
    assert early['발급일']=='2024-03-07'
    assert early['자격확인요청일']=='2024-03-01'
    assert future['발급일']=='2027-03-07'
    assert future['자격확인요청일']=='2027-03-01'
    assert early['생년월일']==source.truth['생년월일']
    assert early['가구원목록']==source.truth['가구원목록']
    assert source==original
    from engine_v2.tools.documentai_bench import _text_reference
    for label,damaged in old.defects(source):
        if label not in {'issued_too_early','issued_after_application'}:continue
        year=2024 if label=='issued_too_early' else 2027
        damaged.truth=corpus.negative_date_truth(source,year)
        path=tmp_path/'FAKE-negative.pdf'
        path.write_bytes(old.pdf_bytes(damaged))
        actual=_text_reference(path,source.doc)
        assert actual['발급일']==damaged.truth['발급일']
        assert actual['자격확인요청일']==damaged.truth['자격확인요청일']
