# 개발 안내

OCR은 서류 사진이나 PDF에서 글자를 읽는 기술입니다.

## 목차

- [저장소와 브랜치](#저장소와-브랜치)
- [협업 규칙](#협업-규칙)
- [폴더 구조](#폴더-구조)
- [개발 환경과 실행](#개발-환경과-실행)
- [신청자 화면과 연결해서 실행](#신청자-화면과-연결해서-실행)
- [OCR 판독 설정](#ocr-판독-설정)
- [평가 도구](#평가-도구)
- [확인 및 테스트](#확인-및-테스트)
- [지켜야 할 원칙](#지켜야-할-원칙)
- [확인이 필요한 사항](#확인이-필요한-사항)
- [참고 자료](#참고-자료)

## 저장소와 브랜치

저장소는 [zohijin-k/26-2-savings-officer](https://github.com/zohijin-k/26-2-savings-officer)이며 두배적금 담당자 화면 저장소입니다. 백엔드는 신청자 화면([26-2-savings-applicant](https://github.com/zohijin-k/26-2-savings-applicant))의 API도 함께 제공해서, 두 화면을 한 DB에 이어 실행할 수 있습니다([신청자 화면과 연결해서 실행](#신청자-화면과-연결해서-실행)). 전체 프로젝트와 분리된 저장소 안내는 [26-2-capstone](https://github.com/zohijin-k/26-2-capstone)을 참고합니다. 기준 브랜치는 `main`입니다. 분리 전 통합 저장소의 브랜치 목록은 이 저장소의 현재 브랜치 안내로 사용하지 않습니다.

## 협업 규칙

1. 작업 전 `main`을 최신으로 받습니다: `git checkout main && git pull`.
2. 새 브랜치를 만듭니다: `git checkout -b feat/<작업-내용>`.
3. 커밋하고 push한 뒤 GitHub에서 `main`으로 PR(변경 내용을 검토받기 위한 병합 요청)을 만듭니다.
4. PR에 변경 내용을 적고 병합합니다. 병합한 브랜치는 삭제합니다.
5. `main`에 직접 push하지 않습니다.
6. 커밋 전 `git status`로 실제 서류, 환경 설정 파일, API 키가 섞이지 않았는지 확인합니다.

## 폴더 구조

| 경로 | 내용 |
|---|---|
| [`demo/`](../demo/README.md) | 두배적금 담당자 데모, 보존된 신청·판정 API와 FastAPI(Python 웹 API 도구) 백엔드, React(화면 구성 라이브러리) 화면, 시나리오 확인 스크립트 |
| [`engine/`](../engine/README.md) | 기존 규칙 판정 엔진. 데모가 서류·자격 판정 파이프라인으로 사용합니다. |
| [`engine_v2/`](../engine_v2/README.md) | OCR 파이프라인·서류 추출기·분류기·평가 도구. `own` 모델 파일은 `models/`에 내려받으며 커밋하지 않습니다. |
| [`engine_v2/pipeline/ocr/`](../engine_v2/pipeline/ocr/) | OCR 공통 인터페이스와 엔진별 모듈 (`own.py` 포함) |
| [`engine_v2/classifier/`](../engine_v2/classifier/) · [`engine_v2/docs/`](../engine_v2/docs/) | 합성 서류 분류 실험 코드 · OCR/분류 설명 문서 |
| `engine_v2/models/` | 내려받은 OCR·분류 모델 파일 (gitignore, 커밋하지 않음) |
| [`dashboard/`](../dashboard/) | 현황 대시보드 코드 |
| [대시보드 옛 안내](archive/dashboard-README.md) | 현재 상태와 다를 수 있는 이전 문서 |
| [`docs/archive/`](archive/) | 옛 기록 보관 문서 |
| [`docs/`](./) | 기획·계획, 개발, 데모 환경 문서 |
| [`.trellis/`](../.trellis/workflow.md), [`.claude/`](../.claude/), [`AGENTS.md`](../AGENTS.md) | 작업 흐름, 에이전트 설정, 저장소 작업 지침 |

`demo_run.py`는 기존 `engine/` 단독 실행 예제입니다. 시스템 전체는 데모 백엔드와 프론트엔드를 실행합니다.

## 개발 환경과 실행

Python 3.12 이상, Node.js 22.13 이상(`node --test tests/`는 22.18 이상)이 필요합니다. macOS와 Linux에서 백엔드·프론트엔드를 실행할 수 있습니다. 합성 담당자 시연은 시연 고정 응답을 사용합니다. 로컬 OCR 자체를 사용할 때는 `python engine_v2/tools/fetch_own_models.py`로 모델을 설치합니다.

저장소 루트에서 설치하고 시연 샘플을 생성합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r demo/backend/requirements.txt
python -m pip install -r engine_v2/requirements.txt
cd demo/frontend
npm install
cd ../..
python -m demo.fixtures.make_samples
```

샘플은 가상 값으로 만든 PDF이며 `demo/fixtures/samples/`에 생성됩니다. 시나리오 확인 스크립트는 폴더가 없을 때 샘플을 자동 생성합니다.

처음 한 번 `.env.example`을 `.env`로 복사하고 `OFFICER_PASSWORD`(담당자 비밀번호)와 `OFFICER_SESSION_SECRET`(로그인 쿠키 서명값)을 채웁니다. 서명값은 `python -c "import secrets; print(secrets.token_hex(32))"`로 만듭니다. `.env`는 커밋하지 않습니다.

백엔드와 프론트엔드를 별도 터미널에서 실행합니다.

```bash
# 터미널 1 — 저장소 루트
python -m uvicorn demo.backend.main:app --env-file .env --reload --port 8000
```

```bash
# 터미널 2
cd demo/frontend
npm run dev
```

브라우저에서 <http://localhost:5173>을 열면 담당자 로그인 칸이 나오고, 로그인하면 두배적금 담당자 화면으로 들어갑니다. 신청 건을 확인 필요 · 적합 · 처리 완료 · 반려 탭으로 나눈 표로 표시합니다. FastAPI 문서는 <http://localhost:8000/docs>입니다.

합성 시연 데이터를 넣거나 그 데이터만 정리할 때는 저장소 루트에서 실행합니다.

```bash
python -m demo.backend.tools.seed_officer_demo
python -m demo.backend.tools.seed_officer_demo --clean
```

정상·확인 필요 신청 각 한 건을 생성하며 재실행으로 중복 생성하지 않습니다. 다른 신청이나 판정은 수정하지 않습니다. 전체 DB 초기화는 필요하지 않습니다. 기존 `seed_application`은 인증된 초안의 2단계 보조 도구로 남아 있지만 이 저장소의 화면 시연 주입에는 사용하지 않습니다.

## 신청자 화면과 연결해서 실행

신청자 화면([26-2-savings-applicant](https://github.com/zohijin-k/26-2-savings-applicant))에서 낸 신청을 이 저장소의 담당자 화면에서 바로 보려면, 이 저장소의 백엔드 하나에 두 프런트를 붙입니다. 두 저장소를 같은 폴더에 나란히 받아 둔 상태를 기준으로 합니다.

| 무엇 | 어디서 실행 | 주소 |
|---|---|---|
| 백엔드 | 이 저장소 루트 | <http://localhost:8000> |
| 신청자 프런트 | `26-2-savings-applicant/demo/frontend` | <http://localhost:5173> |
| 담당자 프런트 | 이 저장소의 `demo/frontend` | <http://localhost:5174> |

```bash
# 터미널 1 — 이 저장소 루트
python -m uvicorn demo.backend.main:app --env-file .env --reload --port 8000
```

```bash
# 터미널 2 — 신청자 저장소
cd ../26-2-savings-applicant/demo/frontend
npm run dev
```

```bash
# 터미널 3 — 이 저장소
cd demo/frontend
npm run dev -- --port 5174
```

- 두 프런트 모두 `/api` 요청을 `localhost:8000`으로 넘기므로 프런트 코드는 고치지 않습니다.
- 신청은 이 저장소의 `demo/demo.db`와 `demo/storage/`에 쌓입니다. 신청자가 제출한 건은 담당자 목록에 바로 나타나고, 담당자가 내린 결정은 신청자 마이페이지에 보입니다.
- 신청자 저장소의 백엔드는 띄우지 않습니다. 같은 8000번을 쓰므로 둘을 함께 띄울 수 없습니다. 신청자 저장소의 백엔드를 대신 띄우면 신청이 그쪽 DB에 쌓이고, 판정도 그 저장소의 코드로 됩니다. 접근 제어도 이 저장소의 백엔드에만 있습니다.
- 담당자 화면(5174)은 로그인부터 합니다. 신청자 화면(5173)은 로그인 없이 쓰고, 신청을 만든 브라우저가 받은 소유자 쿠키로 이어 씁니다. 같은 브라우저에서 두 화면을 함께 열어도 됩니다. 쿠키는 포트를 가리지 않지만 신청자 검사와 담당자 검사가 각자 자기 쿠키만 봅니다.
- 접근 제어를 넣기 전에 만든 작성 중 신청은 이어 쓸 수 없습니다(403). 새 탭에서 신청을 다시 시작합니다.

이 저장소의 백엔드에는 신청자 API(`/api/applications`, `/api/programs`)와 담당자 API(`/api/officer`, `/api/files`)가 함께 있습니다. 신청자 API의 응답은 신청자 저장소와 같은 규칙을 따릅니다. 서류 상태는 `UPLOADED`와 `REUPLOAD_REQUIRED`만 내보내고, 내부 판정·판독 신뢰도·점수·자격 사유는 내보내지 않습니다. 저장되는 판정과 담당자 API의 응답은 그대로입니다.

신청자 API 코드(`demo/backend/api/applications.py`, `documents.py`, `review.py`와 `common.py`의 신청자 응답 부분)는 신청자 저장소에도 같은 내용으로 있습니다. 한쪽에서 고치면 다른 쪽에도 반영합니다. 시험에서 신청자 API의 `status`로 내부 판정을 확인하지 않습니다. 판정은 저장된 값(`Document.stage1_status`)이나 담당자 API로 확인합니다(`test_portal_uploads.assert_upload_status`).

## 담당자 로그인과 접근 제어

요청이 라우터에 닿기 전에 미들웨어 두 개가 확인합니다(`demo/backend/officer_auth.py`, `demo/backend/applicant_access.py`). 계약은 [access-control 규격](../.trellis/spec/backend/access-control.md)에 있습니다.

| 경로 | 열리는 조건 | 아니면 |
|---|---|---|
| `/api/health`, `/api/programs…`, `POST /api/applications` | 누구나 | — |
| `/api/applications/{신청 번호}/…` | 그 신청을 만든 브라우저의 소유자 쿠키 | 403 |
| `GET /api/files/{문서 번호}` | 그 서류의 신청자, 또는 로그인한 담당자 | 403 |
| `/api/officer…` | 로그인한 담당자(`POST /api/officer/login`만 예외) | 401, 설정 없으면 503 |

- 담당자 로그인: `.env`의 `OFFICER_PASSWORD`와 상수 시간으로 비교하고, `OFFICER_SESSION_SECRET`으로 서명한 `officer_session` 쿠키(HttpOnly, SameSite=Lax, 8시간)를 줍니다. 같은 주소에서 5번 틀리면 60초 동안 막힙니다. 로그아웃한 쿠키는 다시 쓸 수 없습니다. 실패 횟수와 로그아웃 목록은 서버 메모리에 있어 서버를 다시 띄우면 비워집니다.
- 담당자 화면은 따로 로그인 주소가 없습니다. 보던 주소(목록, `/officer/review/{신청 번호}`)에서 로그인 칸이 나오고, 로그인하면 그 화면이 그대로 열립니다.
- 소유자 쿠키: 신청을 만들 때 `applicant_access_{신청 번호}`(경로 `/api`, HttpOnly, 5년)를 주고 DB에는 해시만 둡니다. 담당자 세션으로는 원본 보기만 열리고 신청자 경로는 열리지 않습니다.
- 시험에서 담당자 API를 부를 때는 `demo/backend/tests/security_support.py`의 `authenticate_officer(client, monkeypatch)`로 합성 비밀번호 로그인을 하고, DB에 직접 만든 신청을 HTTP로 부를 때는 `claim_synthetic_application(client, 신청 번호)`를 씁니다. 경계 시험은 `test_access_control.py`입니다.

## OCR 판독 설정

이번 제출의 OCR 판독에서는 전북AI를 사용하지 않습니다(연동 코드는 있으나 이번 제출에서는 사용하지 않음). `JBAI_ALLOW_REAL_DOCS`는 비워 둔 채 실행합니다. 판독 순서는 시연 고정 응답 → 로컬 OCR → PDF 텍스트입니다. 전북AI 연동 코드는 남아 있지만 이번 제출 판독 체인에서는 호출하지 않습니다.

## 담당자 화면 AI 종합의견 (선택)

담당자 심사 상세의 **1. 최종 판정** 패널 맨 위에 신청 건 요약지를 보입니다. 한 줄 결론, 왜 이 상태인지, 확인 포인트, 서류별 요약, 심사표 요약으로 구성됩니다. 저장된 판정을 풀어 쓴 참고 문구이고 판정·담당자 판단은 바꾸지 않습니다.

- 켜기: `.env`에 `PROGRAM_LLM_ENABLED=true`, `PROGRAM_LLM_PROVIDER=jbai`, `JBAI_API_KEY`를 넣고 `uvicorn demo.backend.main:app --reload --port 8000 --env-file .env`로 띄웁니다. 모델은 `JBAI_LLM_MODEL`(기본 `MainModel`)입니다.
- 끄기: 위 값을 비우면 외부 전송 없이 규칙 기반 요약을 보입니다. 전북AI가 실패해도 같은 규칙 기반 요약으로 대체합니다.
- 전송 범위: 허용목록으로 투영한 값만 보냅니다. 이름·주민번호·주소·연락처·계좌·사업장명·신청번호·파일은 보내지 않고, 명의·생년월일은 '신청자와 일치/다름'으로만 보냅니다. 계약은 [officer-summary 스펙](../.trellis/spec/backend/officer-summary.md)에 있습니다.
- 미리 생성: 백엔드가 켜져 있는 동안 백그라운드 작업자가 10초마다 DB를 훑어, 제출된 두배적금 신청 중 요약이 없거나 판정이 바뀐 건을 접수 순서(`submitted_at`)대로 한 건씩 만들어 둡니다. 담당자가 열 때는 저장된 요약을 바로 읽습니다. 아직 차례가 안 온 건을 먼저 열면 그 자리에서 만듭니다. `OFFICER_SUMMARY_PREFETCH=false`로 끌 수 있습니다.
- 캐시: 결과는 `ReviewSummary` 테이블에 저장하고, 판정·서류가 바뀌어 입력 해시가 달라지면 작업자나 다음 조회가 다시 만듭니다. 화면의 '다시 생성'은 캐시를 무시합니다.
- API: `GET/POST /api/officer/applications/{id}/summary?role=`

데모 로컬 OCR은 macOS를 포함한 모든 환경에서 own이 기본입니다. 비어 있지 않은 `ENGINE_V2_OCR` 값이 있으면 이를 우선합니다. 기본 선택에서 own 모델 파일이 없을 때만 easyocr로 대체합니다. 명시적으로 own을 선택했는데 모델이 없거나 해시 확인·추론에 실패하면 다른 OCR 엔진으로 대체하지 않습니다. 모델 설치는 macOS에서도 필요합니다.

`engine_v2.engine.run`과 CLI(명령줄 도구)의 선택값은 `own`, `applevision`, `easyocr`, `paddle`입니다. `off`는 데모 전용 비활성화 값입니다. 공용 엔진 선택에 전북AI는 포함되지 않습니다.
## 평가 도구

`fetch_synth_fonts.py`는 합성 평가용 글꼴을 받고 `make_synth_eval.py`는 가상 문서 평가 세트를 만듭니다. `ocr_bench`로 own·Apple Vision 등 OCR 엔진을 비교할 수 있습니다. OCR은 서류 사진이나 PDF에서 글자를 읽는 기술입니다. 평가 정의와 한계, 실서류 평가의 개인정보 보호 방식은 [own OCR 설명](../engine_v2/docs/own-ocr.md)을 참고합니다. `extract_diag --safe-issue`는 값·인식 텍스트·파일명·좌표를 출력하지 않습니다.

담당자 화면 정리 작업의 검증에는 저장소 합성 샘플과 임시 DB/storage만 사용합니다. OCR 평가 데이터 생성·모델 성능 평가는 이 작업의 범위 밖입니다.

own의 현재 평가는 합성 서류 3종(주민등록초본·납부확인서·자격득실확인서 형태), 열화 조건과 ±2도 이내 회전을 포함합니다. 90도·180도 방향 보정은 없습니다. 기존 문서에서 보고한 실서류 관찰은 주민등록초본과 4대보험 가입내역에 한정되며 공개 안내에서는 식별정보와 수치 판독 결과를 공개하지 않습니다. 합성 자료 결과는 실제 서류 전반의 성능을 보장하지 않습니다.

자체 OCR 모델은 공개 사전학습 PP-OCRv5 mobile 검출·한국어 인식 모델의 ONNX 변환본이며, 모델을 직접 사전학습했다는 의미는 아닙니다. 데모 기본 연결과 2단계 학습은 진행 중입니다. 출처·라이선스, 모델 설치와 평가 방법은 [own OCR 설명](../engine_v2/docs/own-ocr.md)에 있습니다.

## 확인 및 테스트

테스트는 가상 데이터와 임시 저장소를 사용합니다. 시나리오 전체와 OCR 엔진 테스트는 저장소 루트에서 실행합니다.

```bash
for f in demo/backend/tests/run_p*_scenarios.py; do echo "== $f"; python -m demo.backend.tests.$(basename "$f" .py) || echo "FAILED $f"; done
python -m pytest engine_v2/tests -q
python -m pytest demo/backend/tests -q
```

2026-11-13 작업 전 기준선은 엔진 1,264개 통과·3개 건너뜀, 백엔드 1,227개 통과, 시나리오 18개 모듈 1,885개 통과·실패 0입니다. 새 시드·화면 연동 시험은 백엔드 기준선에 별도 가산합니다. 신청자·취업지원 프런트는 제거해도 보존된 API·엔진 회귀 시험은 유지합니다. 위 반복문은 한 시나리오가 실패해도 나머지를 계속 실행합니다.

프론트엔드 타입 검사·린트·빌드는 다음과 같습니다.

```bash
cd demo/frontend
node --test tests/  # 새 화면 회귀 시험: Node.js 22.18 이상
npm run lint
npm run build
```

하위 폴더별 기능과 추가 실행 방법은 [데모](../demo/README.md), [기존 엔진](../engine/README.md), [엔진 v2](../engine_v2/README.md), 대시보드 코드와 [대시보드 옛 안내](archive/dashboard-README.md)를 확인합니다.

자체 OCR의 제작 과정·평가·한계는 [제작 과정 기록](../engine_v2/docs/own-ocr-history.md)을 참고하세요.

## 지켜야 할 원칙

- 실제 서류는 로컬 내부 평가용 보관 위치에만 두고 저장소에 커밋하지 않습니다.
- 판정은 공고문에 근거한 규칙으로 합니다. OCR·모델은 문서를 읽는 데 씁니다.
- 보존된 신청 API의 배점·내부 판단 정보·타인 이름 비공개 계약을 유지합니다.
- 파일 이름이 아니라 서류 내용으로 종류와 판정 근거를 판단합니다.
- 담당자는 신청자가 올린 원본 서류를 내려받지 않고 화면으로만 확인합니다. 신청자는 본인이 작성한 서식만 내려받을 수 있으며 P4 시나리오가 이 경계를 확인합니다.
- 값을 출력하는 점검 도구는 이름·주소·번호를 가립니다.
- OCR 모델·글꼴·패키지의 제3자 출처와 라이선스는 [제3자 고지](../THIRD_PARTY_NOTICES.md)와 [own OCR 설명](../engine_v2/docs/own-ocr.md)에서 확인합니다.
- API 키를 코드·로그·커밋에 넣지 않습니다.
- 모델 학습에는 개인정보가 없는 합성 데이터만 사용합니다. 실서류는 기관 내부 평가에만 사용하고 판독은 가능한 한 기관 내부 엔진으로 합니다. 외부 전송은 기관의 명시 확인 범위에서만 합니다. 주민등록번호 뒷자리는 응답 즉시 지우고 원문을 남기지 않습니다.

## 확인이 필요한 사항

- 혼합가입자가 제출할 서류와 건강보험료 합산 방식
- 공고문 표가 7인까지인 상태에서 8\~10인 상한표를 적용할 출처·기준
- 취업지원패키지 지원 횟수 누적 범위와 인정 시험 목록
- 담당자 심사 상태를 승인·보완요청·부적격·재검토 4종으로 전환할지

## 참고 자료

- `‘26년 전북청년 함께 두배적금 운영성과 및 ‘27년 운영계획.pdf` — 사업 개요, 2026년 운영 애로사항, 2027년 개선 방향
- `2026년 전북청년 함께 두배적금 상담(콜센터) 시스템 구축 및 운영 결과 보고서_주베스트인.pdf` — 콜센터 상담 데이터, 실무자 건의사항(통합 플랫폼, 자체 취소 기능, 온라인 서명 등)
