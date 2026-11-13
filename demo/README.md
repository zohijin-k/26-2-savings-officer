# 데모 사이트 — 두배적금 담당자 서류 검토

앱을 열면 두배적금 담당자 화면으로 바로 진입한다. 첫 화면의 **적합 서류**는 문서 상태 PASS, **확인 필요 서류**는 그 외 상태다. 항목을 선택하면 원본과 기존 사유를 2단으로 확인한다. 신청자 화면·사업 선택·취업지원 담당자 화면은 제공하지 않는다. 신청·서식·업로드·판정·취업지원 백엔드 API와 엔진은 회귀 검증을 위해 보존한다.

아래 과거 요구사항·설계·시연 대본은 분리 전 기록이다. 현재 화면 범위는 [루트 안내](../README.md)를 따른다.

- 요구사항: `.trellis/tasks/09-16-demo-site/prd.md`
- 설계: `.trellis/tasks/09-16-demo-site/design.md`
- 업무 규칙 관련 옛 기록: [보관 문서](../docs/archive/demo-site-dev-plan.md)
- **시연 대본**: [`docs/demo-script.md`](docs/demo-script.md)
- 담당자 화면 목업 데이터의 옛 기록: [보관 문서](../docs/archive/officer-mock-data.md)

> 원본·사유를 나란히 확인하는 PC 화면을 기준으로 시연한다.

> ⚠️ **더미 데이터만 쓴다.** 이름·주민등록번호·주소·계좌번호는 전부 가짜이고,
> 실물 서류는 저장소에 두지 않는다(R7.1). 업로드 원본과 SQLite 파일은 커밋되지
> 않는다(루트 `.gitignore`).

---

## 1. 폴더

```
demo/
├── backend/            FastAPI — 신청·업로드·심사·담당자 API
│   ├── main.py         엔트리 (uvicorn 대상)
│   ├── tools/seed_officer_demo.py  합성 시연 데이터 생성·자체 생성분 정리
│   ├── reset.py        전체 초기화 (파괴적, 일반 시연에 사용하지 않음)
│   ├── engine_adapter.py   engine/ 와의 유일한 접점
│   ├── api/ ocr/ rules/    라우터 · 판독 3계층 · 업무 규칙
│   ├── forms/          원본 PDF 위 입력·서명 렌더링 및 서식 응답
│   └── tests/          P2\~P20 시나리오 검증 스크립트 (pytest 없이 실행)
├── frontend/           React + Vite (두배적금 담당자 화면)
├── fixtures/
│   ├── make_samples.py 시연용 더미 서류 생성기
│   ├── cut_templates.py     원본 공고 PDF에서 서식별 A4 쪽 템플릿 생성
│   ├── build_form_coords.py 템플릿 → 서식 좌표 맵 추출
│   ├── samples/        생성된 더미 PDF (gitignore)
│   ├── templates/      두 사업 신청자 서식 PDF 템플릿 (커밋 대상)
│   ├── form_coords/    서식별 필드 좌표 맵 JSON
│   └── expected/       시연 시나리오 10종의 기대 결과 JSON
├── docs/demo-script.md 시연 대본
├── storage/            업로드 원본 (gitignore)
└── demo.db             SQLite (gitignore)
```

`engine/`은 **복사하지 않는다.** `engine_adapter.py`가 저장소 루트를 `sys.path`에
올려 `from engine.pipeline import run_pipeline` 으로 직접 import 한다. 엔진 담당자의
수정이 그대로 반영되어야 하기 때문이다.

---

## 2. 준비 (최초 1회)

검증에 쓴 환경: **Python 3.14.0 · Node 22.19.0** (Windows 11).
Python은 3.12 이상, Node는 20.19 이상이면 된다.

```bash
# 저장소 루트에서
pip install -r demo/backend/requirements.txt

cd demo/frontend
npm install
```

시연용 더미 서류를 만든다. `demo/fixtures/samples/`에 가상 PDF가 생긴다.

```bash
# 저장소 루트에서
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.fixtures.make_samples
```

> Windows 콘솔은 기본 인코딩이 cp949라 한글 출력이 깨진다. 파이썬 스크립트를
> 돌릴 때는 `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`을 앞에 붙인다.

---

## 3. 기동

터미널 2개가 필요하다. **백엔드는 반드시 저장소 루트에서** 띄운다 — 그래야
`engine/` 을 import 할 수 있다.

```bash
# 터미널 1 — 백엔드 (저장소 루트에서)
uvicorn demo.backend.main:app --reload --port 8000
```

이번 제출에서는 전북AI를 사용하지 않는다(연동 코드는 있으나 이번 제출에서는 사용하지 않음). JBAI_* 설정은 비워 둔 채 실행한다. 데모 로컬 OCR은 macOS를 포함한 모든 환경에서 own이 기본이다. 합성 시연 고정 응답에는 모델 설치가 필요하지 않다. 로컬 OCR 자체를 쓰려면 모델을 설치한다. 저장소 루트에서 `pip install -r engine_v2/requirements.txt`와 `python engine_v2/tools/fetch_own_models.py`를 실행한다. 모델 파일은 저장소에 포함되지 않는다.

```bash
# 터미널 2 — 프론트엔드
cd demo/frontend
npm run dev
```

브라우저에서 <http://localhost:5173>을 열면 두배적금 담당자 화면이 나온다. Vite가 `/api` 요청을 8000 포트로 프록시하므로 별도 설정은 없다.

### 담당자 시연 데이터 넣기

저장소 루트에서 실행한다.

```bash
python -m demo.fixtures.make_samples
python -m demo.backend.tools.seed_officer_demo
```

로컬 데모 DB에 정상 1건(업로드 서류 전부 PASS), 확인 필요 1건(non-PASS 서류 포함)을 생성한다. 저장소의 합성 PDF만 읽고 기존 API 흐름으로 제출한다. 자체 생성 표시를 확인하므로 다시 실행해도 중복 생성하지 않는다. 화면을 새로고침하면 각 서류가 PASS 여부에 따라 두 목록에 나뉜다.

```bash
python -m demo.backend.tools.seed_officer_demo --clean
```

정리는 도구가 생성한 신청·관련 행과 소유 저장 파일만 대상으로 하며 다른 신청은 보존한다. 외부 DB·서류 경로를 받지 않는다. 기존 `seed_application.py`는 본인인증된 초안의 2단계만 채우는 보존 도구이며, 현재 화면 시연에 필요한 업로드·제출을 완성하지 않는다.

DB가 비어 있으면 빈 목록이 표시된다. `?mock=1`로 두배적금 전용 프런트 목업을 볼 수 있으며, 기본 동작에서 API 실패를 목업으로 숨기지 않는다. 목업은 DB에 저장되지 않는다.

확인용 엔드포인트:

```bash
curl http://localhost:8000/api/health     # {"status":"ok"}
curl http://localhost:8000/api/programs   # 사업 2종 설정
```

API 문서는 <http://localhost:8000/docs> (FastAPI 자동 생성).

담당자 화면은 업로드 원본을 브라우저 안에서만 보여 준다. 신청자용 서식·제출 API는 보존하지만 이 프런트엔드에서 신청서 작성 화면으로 이동하지 않는다.

---

## 4. 시연 초기화

**전체 초기화가 필요한 경우에만 사용한다.** 담당자 시연 데이터만 정리하려면 위의 `seed_officer_demo --clean`을 사용한다. 다음 도구는 다른 신청까지 지운다.

```bash
# 무엇을 지울지 보기만 한다
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.reset --dry-run

# 확인을 묻고 지운다
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.reset

# 확인 없이 전체 삭제 (다른 신청까지 삭제됨)
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.reset --yes
```

지우는 것은 `demo/demo.db`와 `demo/storage/` **둘뿐**이다. 소스·시연 샘플·문서는
건드리지 않고, git이 추적하는 파일은 하나도 지워지지 않는다.

> **Windows에서는 uvicorn을 먼저 멈춰야 한다.** 실행 중이면 SQLite 파일이 잠겨
> 삭제가 실패한다. 그 경우 안내 문구와 함께 종료코드 3으로 끝난다.

빈 DB는 서버를 다음에 띄울 때 자동으로 만들어진다.

---

## 5. 검증 스크립트

pytest 없이 그대로 실행된다. 전부 임시 폴더에서 돌기 때문에 `demo/demo.db`·
`demo/storage/`(시연용 데이터)를 건드리지 않는다.
`demo/fixtures/samples/`가 없으면 첫 시나리오 실행 시 `make_samples`가 더미 PDF를 자동 생성한다.

```bash
# 저장소 루트에서
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p2_scenarios  # 업로드 즉시 판정
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p3_scenarios  # 통합심사·채점
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p4_scenarios  # 담당자 원본 서류 인라인·저장 경로 검사
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p5_scenarios  # 취업지원패키지 분기
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p6_scenarios  # 리셋 후 시연 10종 재현
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p7_scenarios  # 작성 서식 PDF 내보내기
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p8_localocr_scenarios
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p9_identity_scenarios
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p11_criteria_scenarios
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p12_subsidy_criteria_scenarios
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p13_household_scenarios
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p14_pdf_forms_scenarios
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p15_jbai_scenarios
```

실패한 시나리오 뒤에도 나머지를 끝까지 실행하려면 아래 반복문을 쓴다. 파일 이름 순서상 P11\~P15가 P2\~P9보다 먼저라, 첫 실패에서 멈추면 뒤 시나리오 결과를 확인할 수 없다.

```bash
for f in demo/backend/tests/run_p*_scenarios.py; do echo "== $f"; python -m demo.backend.tests.$(basename "$f" .py) || echo "FAILED $f"; done
```

`run_p6_scenarios`는 **리셋 → S1\~S10 연속 실행 → 기대값 대조**를 두 번 반복해,
리셋이 실제로 동작하고 두 번째 시연에서도 같은 화면이 나오는지(신청번호까지)
확인한다. 기대값은 `fixtures/expected/S*.json`에 있다.

`--live`를 주면 임시 폴더가 아니라 **진짜 `demo/`를 리셋하고** 거기서 돌린다.
전체 초기화 동작을 검증하는 옵션이며, 끝나면 다시 리셋된 상태로 정리된다. 담당자 데이터 주입에는 사용하지 않는다.

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python -m demo.backend.tests.run_p6_scenarios --live
```

프론트엔드 점검:

```bash
cd demo/frontend
npm test  # 새 화면 회귀 시험: Node.js 22.18 이상
npm run lint
npm run build
```

---

## 6. 보존된 서식 백엔드

신청·서식 작성·내보내기 API와 원본 서식 템플릿·좌표 맵은 보존한다. 이 저장소 프런트엔드에는 신청서 작성·전자서명·마이페이지·본인 보관용 메뉴가 없다. 담당자는 업로드 원본을 인라인으로 확인한다.

서식 렌더링과 API 계약은 P7/P14 시나리오로 계속 검증한다. 기존 템플릿·좌표 생성 도구도 그대로 유지한다.

### 서식 글꼴

보존된 PDF 서식 렌더링은 Noto KR TTF 서브셋을 사용한다. P14가 TTF·WOFF2·OFL을 함께 검사하므로 프런트 신청자 화면을 제거해도 글꼴 파일을 유지한다.

- 고딕: `frontend/src/assets/fonts/NotoSansKR/` — [Noto Sans KR 원본·라이선스](https://github.com/google/fonts/tree/main/ofl/notosanskr)
- 명조: `frontend/src/assets/fonts/NotoSerifKR/` — [Noto Serif KR 원본·라이선스](https://github.com/google/fonts/tree/main/ofl/notoserifkr)
- 서브셋: KS X 1001 한글 2,350자, ASCII 영문·숫자·문장부호, 서식 좌표의 라벨·보기와 가상 입력값에 쓰인 글자를 포함한다. 배경 PDF 문구는 원본 서식의 글꼴로 보존된다.
- 자동 글꼴 범위 검증: `run_p14_pdf_forms_scenarios`가 두 글꼴의 TTF/WOFF2/OFL 존재와 서식·가상 입력 글리프를 확인한다.

---

## 7. 알아 둘 것

- **판독(OCR)은 단계형 체인**이다. 판독 순서는 시연 고정 응답 → 로컬 OCR → PDF 텍스트다. 전북AI 연동 코드는 있으나 이번 제출에서는 사용하지 않으며 JBAI_* 설정은 비워 둔다.
- 데모 로컬 OCR은 macOS를 포함한 모든 환경에서 own이 기본이다. 기본 선택에서 own 모델 파일이 없을 때만 easyocr로 대체한다. 명시한 own의 모델 누락·해시 오류·추론 오류에는 다른 OCR 엔진으로 대체하지 않는다. own 모델 설치는 macOS에서도 필요하다.
- `ENGINE_V2_OCR`의 비어 있지 않은 값은 데모 엔진 선택에 우선한다. `off`는 데모 전용이고, `engine_v2.engine.run`과 CLI 선택값은 `own` / `applevision` / `easyocr` / `paddle`이다.
- **점수는 신청자에게 절대 보이지 않는다**(공고문: "평가결과는 공개하지 않음").
  마이페이지 응답에 점수 관련 필드가 하나라도 섞이면 검증 스크립트가 잡는다.
- **미확정 가정값**에는 `(데모 추정치)` 라벨이 붙어 있다. 중위소득 100\~130% 환산
  기준선, 판독 신뢰도·화질 컷라인, 취업패키지 서식 구성, 선착순 기준 시각이
  여기 해당한다. 화면과 코드 양쪽에 같은 문구로 노출된다.
- **서식 좌표는 손으로 적지 않았다.** 원본 PDF의 표 선(`get_drawings`)과 글자
  원점(`get_text("rawdict")`)에서 뽑는다. `run_p7_scenarios`가 좌표를 다시 뽑아
  커밋된 JSON과 대조하므로, 좌표를 손으로 고치면 검증이 깨진다.
- 담당자는 신청자가 올린 원본 서류를 화면에서만 본다. 신청자는 본인이 작성한 서식만
  내려받을 수 있다. P4 시나리오는 담당자 화면·API와 원본 파일 경로를 검사하고, 신청자용
  서식 제공 파일만 명시적 허용 목록에 둔다.

## 8. 보존된 취업지원 백엔드 기준 (화면 미제공, 2026 공고)

- [2026년 전북청년 취업지원패키지 모집 공고](https://youth.wanju.go.kr/board/view.wanju?boardId=BBS_0000001&dataSid=77474&menuCd=DOM_000000114001000000&paging=ok&startPage=1)는 면접비·정장비 각 5만원 최대 2회, 사진비 2만원 1회, 응시료 5만원 최대 2회와 항목별 추가 서류를 안내한다. 공고 페이지는 한도 횟수가 신청서·연간·생애 중 어디에 누적되는지 명시하지 않는다. 현재 데모는 기준의 `count_scope`를 설정할 수 있게 하고 기본값은 기존 동작인 신청서 단위다. 운영 전 담당 기관 확인이 필요하다.
- 공고는 면접비와 면접정장비 모두 면접확인서를 요구하지만, 정장 대여 회차를 특정 면접 회차와 연결하라고 정하지 않는다. 데모에서는 확인서 중복 업로드를 막도록 신청자가 연결 면접 회차를 고르게 하며, 이 연결 규칙은 접수서류 요구를 구현하기 위한 데모 가정이다.
- 면접비 대상 기업은 사업장 고용보험 가입자 5인 이상이며 결격 사유가 없어야 한다. 공개 공고에는 그 가입자 수를 어떤 서류나 조회 절차로 검증할지 적혀 있지 않아, 데모는 자동 판정을 하지 않는다.
- 공고 페이지는 인정 시험 목록을 별도 첨부 파일로 안내한다. 현재 공개 페이지 본문에는 목록이 없어 연도별 첨부 내용을 기준에 복사하지 않았다. 시험 목록 자동 판정은 담당 기관이 2026년 첨부 내용을 확정한 뒤 연결해야 한다.
