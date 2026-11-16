# 합성 글자층 PDF 생성 명령 — 미실행

계획 승인과 네 회귀 기준 일치 후, 추적 소스 격리 폴더에서 아래 전체 명령을 실행한다. 이 문서는 명령만 담고 있으며 실행 스크립트나 PDF는 아직 만들지 않았다. 기존 입력을 열지 않고 기존 합성 함수·빈 추적 서식만 사용한다. 원본 생성기/정답/410쌍 입력은 수정하지 않는다.

50쪽은 기존 `make_synth_eval.documents`의 legacy 납부 셀과 `documentai_synth.Source`/`pdf_bytes` 렌더러에 이름 5 × 가입표기 2 × 날짜/월 형식 5를 입력한다. 전문 생성기에 형식 옵션이 있다는 주장은 하지 않는다. 셀 입력은 원래 렌더 API가 지원한다. 위치·라벨·금액은 기존 셀을 유지하고 사전에 정한 가상 이름/표기만 바꾼다. OCR·추출 결과를 보고 양식을 조정하지 않는다. 50쪽 모두 참조가 생긴다고 미리 보장하지 않고 실제 필드별 분모를 확인한다.

```sh
cd /tmp/own_adapter_before/source && PYTHONPATH=. .venv/bin/python -B - <<'PY'
import io
import json
import random
import sys
sys.excepthook = lambda *_: sys.stderr.write('GENERATION_ERROR\n')
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import pymupdf
from engine_v2.tools import documentai_synth as synth
from engine_v2.tools.documentai_corpus_v2 import sources
from engine_v2.tools.make_synth_eval import documents
from engine_v2.tools.make_job_docs import LAYOUTS
from engine_v2.tests.p2_payment_samples import payment
from engine_v2.tests.p2_business_samples import business, text_pdf
from engine_v2.tests.fail_case_samples import daily
from demo.fixtures.make_samples import make

root = Path('/tmp/own_adapter_before/pdfs')
root.mkdir(exist_ok=False)
ids = []
government_ids = []
count = 0

def target():
    global count
    count += 1
    return root / f'{count:04}.pdf'

for sample in range(5):
    for source in sources(sample):
        target().write_bytes(synth.pdf_bytes(source))

_, original, _ = next(x for x in documents() if x[0] == 'nhis_payment')
names = ('가상가', '가상나', '가상다', '가상라', '가상마')
issue_formats = ('2026.11.10', '2026-11-10', '2026/11/10', '2026년11월10일', '20261110')
month_formats = ('2025.{m:02}', '2025-{m:02}', '2025/{m:02}', '2025년{m:02}월', '2025{m:02}')
for name in names:
    for membership in ('직장가입자', '지역가입자'):
        for index, issued in enumerate(issue_formats):
            cells = []
            for x, y, text in original:
                text = text.replace('가상시험', name).replace('직장가입자', membership)
                text = text.replace('2026.11.10', issued)
                for month in (10, 11, 12):
                    text = text.replace(f'2025.{month:02}', month_formats[index].format(m=month))
                cells.append((x * 5.95, y * 8.42, text, 10))
            source = synth.Source('nhis_payment', [(cells, (595, 842))], {}, {})
            path = target()
            path.write_bytes(synth.pdf_bytes(source))
            ids.append(path.name)

for name in names:
    for workplace in ('가상사업장가', '가상사업장나'):
        for blank in (False, True):
            path = target()
            text_pdf(path, *payment(name=name, workplace=workplace, trailing_blank=blank))
            government_ids.append(path.name)
for _, builder in LAYOUTS.values():
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        document, _, _, _ = builder(random.Random(20261113 + count))
    with document:
        document.save(target())
text_pdf(target(), *business())

with pymupdf.open() as document:
    font = pymupdf.Font('cjk')
    for index, (_, recognized) in enumerate(daily()):
        page = document.new_page(width=595, height=842)
        if index % 2:
            writer = pymupdf.TextWriter(page.rect)
            writer.append((55, 60), '합성시험용 가짜 안내 문장입니다. 실제 서류나 실제 인물의 정보가 아닙니다.', font=font, fontsize=8)
            writer.write_text(page)
        for word in recognized.words:
            x0, y0, x1, y1 = word.bbox_px
            text = word.text.replace('[√]', '[X]')
            size = min((y1 - y0) * .9, (x1 - x0) / font.text_length(text, fontsize=1))
            writer = pymupdf.TextWriter(page.rect)
            writer.append((x0, y1 - 2), text, font=font, fontsize=size)
            writer.write_text(page)
    document.save(target())

for label in ('주민등록등본', '면접용사진사본'):
    path = make(label, root)
    path.rename(target())

Path('/tmp/own_adapter_before/payment.ids').write_text('\n'.join(ids) + '\n')
Path('/tmp/own_adapter_before/payment_government.ids').write_text('\n'.join(government_ids) + '\n')
Path('/tmp/own_adapter_before/payment_all.ids').write_text('\n'.join(ids + government_ids) + '\n')
summary = {'PDF': count, 'PAYMENT_DIAG_PDF': len(ids), 'PAGE': 0}
for path in root.glob('*.pdf'):
    with pymupdf.open(path) as document:
        summary['PAGE'] += document.page_count
assert summary == {'PDF': 111, 'PAYMENT_DIAG_PDF': 50, 'PAGE': 114}
payload = json.dumps(summary, allow_nan=False) + '\n'
Path('/tmp/own_adapter_before/corpus_counts.json').write_text(payload)
print(payload, end='')
PY
```

기존 helper가 분류/필드 참조를 생성하지 못하면 생성 실패와 참조 부재를 분리해 보고한다. 위쪽 renderer/배치가 실제 합성 필드 분모를 충분히 만들지 못해도 추출기 규칙을 고치지 않는다. 부분 생성 결과는 완성 코퍼스로 채택하지 않고, 새 폴더를 덮어쓰지 않는다. legacy 50쪽은 payment.ids, 정부형 20쪽은 payment_government.ids, 합계 70쪽은 payment_all.ids로 고정하고 서식별로 집계한다.

생성 예정 15종과 제외 5종, 간이 본문 2종 및 여러 쪽 일용근로의 한계는 `source-map.md`가 기준이다. PDF 생성·내용 확인·모델 실행은 이 계획 작성 턴에 하지 않는다.
