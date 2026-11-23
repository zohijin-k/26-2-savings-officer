# 두배적금 담당자·공용 백엔드

**PRODUCTION_NOT_READY.** 전북청년 함께 두배적금의 담당자 화면과 신청자·담당자가 공유하는 FastAPI 백엔드입니다. 담당자는 원본·기존 판정·근거를 확인하고 결정·메모를 기록합니다. 읍면동/시군/도 역할 선택은 화면 범위이며 실운영 사용자별 RBAC 승인 근거가 아닙니다.

## 저장소와 연결 구조

| 저장소 | 현재 역할 |
|---|---|
| [capstone](https://github.com/zohijin-k/26-2-capstone) | 전체 안내·분리 전 코드와 이력 보관 |
| [officer](https://github.com/zohijin-k/26-2-savings-officer) | 두배적금 공용 백엔드 + 담당자 프런트 |
| [applicant](https://github.com/zohijin-k/26-2-savings-applicant) | 두배적금 신청자 프런트 |
| [youth](https://github.com/zohijin-k/26-2-youth) | 취업지원패키지·범용 청년사업의 독립 백엔드 + 신청자·담당자 프런트 |

두배적금은 **officer 백엔드 하나(8000)**에 applicant 프런트(5173)와 officer 프런트(5174)를 연결합니다. 신청·파일은 officer의 로컬 DB·저장소에 저장됩니다. applicant 저장소의 보존 백엔드를 동시에 실행하지 않습니다. youth는 별도 API·DB이며 같은 서비스가 아닙니다.

## 설치·실행

검증 환경은 **CPython 3.14.6 / macOS 26.6.2 / arm64, Node 26.13.1 / npm 11.20.0**입니다. 최신 코드의 Python 3.12·Linux·Windows 전체 실행은 미검증입니다. 과거 WSL 결과를 최신 main의 보장으로 사용하지 않습니다. Node의 직접 TypeScript 시험은 22.18 이상이 필요하며, 여기서는 위 실측 버전을 기준으로 합니다.

[`package-lock.json`](demo/frontend/package-lock.json)의 실제 잠금 버전은 React **19.3.0**, Vite **8.3.0**, TypeScript **6.0.3**, pdfjs-dist **5.7.284**입니다. Python 잠금은 FastAPI **0.162.2**, uvicorn **0.54.0**, SQLModel **0.0.44**, ONNX Runtime **1.31.1**, pytest **9.2.0** 등 55개 패키지를 포함합니다. [hash lock](demo/backend/locks/macos-arm64-py314.txt)과 [재현 범위](demo/backend/locks/README.md)를 확인하세요. 이 macOS 전용 lock을 다른 OS에 적용하거나 기존 requirements의 하한을 지원 보장으로 해석하지 않습니다. 프런트 package `0.0.0`·API 선언 `0.1.0`은 제품 릴리스 번호가 아닙니다.
```bash
# 새 로컬 개발 사본의 루트; 위 macOS/arm64·CPython 3.14.6 환경
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes --only-binary=:all: -r demo/backend/locks/macos-arm64-py314.txt
python -m pip check
cp .env.example .env
cd demo/frontend
npm ci
cd ../..
```

기존 [`demo/backend/requirements.txt`](demo/backend/requirements.txt)·[`engine_v2/requirements.txt`](engine_v2/requirements.txt)는 일반 의존성 선언이며 위 재현용 lock과 목적이 다릅니다. 모델·합성 시험용 글꼴은 lock에 포함되지 않습니다.
실행 전 로컬 `.env`에 서로 다른 `OFFICER_PASSWORD`와 긴 임의 값의 `OFFICER_SESSION_SECRET`을 채웁니다. 두 값 중 하나라도 없으면 담당자 API는 503으로 차단됩니다. `.env`는 코드가 자동으로 읽지 않으므로 `--env-file .env`를 유지합니다. 비밀값은 커밋하지 않습니다.

로컬 합성 검증은 `JBAI_API_KEY`를 비우고 `JBAI_ALLOW_REAL_DOCS=false`, `PROGRAM_LLM_ENABLED=false`, `PROGRAM_LLM_PROVIDER=none`으로 둡니다. JBAI OCR은 키와 실서류 전송 허용 플래그가 모두 켜져야 동작하며 문서 이미지가 외부 서비스로 전송될 수 있습니다. 예제 파일의 오래된 허용 문구가 기관 승인이나 이번 제출의 외부 전송 허가를 뜻하지 않습니다. `JBAI_BASE_URL`, `JBAI_TIMEOUT_SEC`, `JBAI_MAX_TOKENS`는 선택 설정입니다.

```bash
# 터미널 1: 이 저장소 루트
python -m uvicorn demo.backend.main:app --env-file .env --reload --host 127.0.0.1 --port 8000
```

```bash
# 터미널 2: 이 저장소 루트
cd demo/frontend
npm run dev -- --port 5174 --strictPort
```

신청자 저장소에서는 `demo/frontend`에서 `npm ci`, `npm run dev -- --port 5173 --strictPort`를 실행합니다. 같은 `localhost` 호스트명을 사용하세요. 담당자 화면은 <http://localhost:5174>, API 문서는 <http://localhost:8000/docs>입니다. 두 Vite 설정은 `/api`를 8000으로 프록시합니다. 새 개발 사본에서 합성 데이터만 사용하세요. 빈 DB는 빈 목록을 표시합니다. `?mock=1`은 합성 화면이며 실제 인증·DB 검증을 대신하지 않습니다.

## OCR·Document AI와 데이터 안전성

일반 문서의 구현 체인은 **fixture → 조건부 JBAI → LocalOcr → PDF text → 상용 스텁**입니다. [`demo/backend/ocr/`](demo/backend/ocr/__init__.py)가 순서를 정하고, [`engine_v2/`](engine_v2/README.md)가 OCR·분류·문서별 필드 추출, `engine/`과 백엔드 규칙이 자격·제출 판정을 담당합니다. Document AI의 필드·좌표·신뢰도 추출과 규칙 판정, 담당자 최종 판단은 구분합니다. Upstage 계층은 실제 연동 완료가 아닌 스텁입니다.

로컬 기본 선택은 own입니다. 현재 코드는 **기본 선택에서 모델이 없을 때** easyocr를 선택하지만 easyocr는 기본 requirements에 설치되지 않습니다. 명시한 `ENGINE_V2_OCR=own`의 모델 누락·해시·추론 오류를 다른 엔진으로 대체하지 않습니다. 자동 대체를 설치 성공이나 정확도 보장으로 설명하지 않습니다. 아래 명령은 선택한 own 모델을 다운로드·검증하므로, 로컬 OCR을 시험할 때만 별도로 실행합니다.

```bash
python -m engine_v2.tools.fetch_own_models
python -c "from engine_v2.tools.fetch_own_models import verify_models; verify_models()"
```

[`fetch_own_models.py`](engine_v2/tools/fetch_own_models.py)의 고정 SHA-256:

| 파일 (`engine_v2/models/own/`) | SHA-256 |
|---|---|
| `det.onnx` | `4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae` |
| `rec.onnx` | `cd6e2ea50f6943ca7271eb8c56a877a5a90720b7047fe9c41a2e541a25773c9b` |
| `korean_dict.txt` | `a88071c68c01707489baa79ebe0405b7beb5cca229f4fc94cc3ef992328802d7` |

신청자에게는 `UPLOADED`/`REUPLOAD_REQUIRED`와 허용된 재업로드 사유만 투영합니다. 저장된 `PASS`/`FAIL`/`NEEDS_REVIEW`와 OCR 신뢰도·담당자 사유를 신청자 공개 응답과 동일시하지 않습니다. submit은 서버에서 기존 차단 조건을 재검사합니다. 신청자 API는 신청 소유자 쿠키, 원본은 소유자 또는 로그인한 담당자만 접근합니다. 담당자 작성 서식은 `/api/officer/applications/{id}/forms/{form_no}.pdf` 경로로 제공합니다.

담당자 결정·메모는 `expected_revision`, 일괄 처리는 `expected_revisions`를 보내는 Review CAS(compare-and-swap)를 사용합니다. 오래된 revision은 충돌로 처리하며 전체 심사 내용을 덮어쓰지 않습니다. 제출 후 문서 변경 잠금과 트랜잭션 회귀도 유지합니다. 세션은 단일 프로세스 가정을 포함하므로 다중 worker 안전성을 보장하지 않습니다.

youth의 canonical `PAYMENT_RECEIPT`는 OCR·Document AI를 우회하는 수동 검토 정책이며 이 저장소의 일반 문서 정책을 youth에 일괄 복사하지 않습니다. [youth 정책표](https://github.com/zohijin-k/26-2-youth/blob/main/docs/phase7-policy-decisions.md)의 P1–P19는 미결이며 현재 youth 판정을 유지합니다. 선택적 담당자 AI 종합의견은 규칙 판정과 별개이고 기본 로컬 검증에서는 비활성화합니다.

## 시험과 확인된 범위

```bash
# 저장소 루트, 위 venv 활성화, 외부 공급자 비활성화
JBAI_API_KEY= JBAI_ALLOW_REAL_DOCS=false PROGRAM_LLM_ENABLED=false python -m pytest -q demo/backend/tests engine_v2/tests
```

전체 suite에는 별도 모델·합성 글꼴 등 자산이 필요합니다. 합성 글꼴 도구는 `python -m engine_v2.tools.fetch_synth_fonts`이며 출처·사용 조건을 확인한 별도 로컬 자산입니다. 자산 없는 사본의 skip/failure를 숨기거나 hash/시험 규칙을 완화하지 않습니다.
```bash
# demo/frontend에서; tests와 함께 배치된 .test.ts도 포함
npm run lint
npm run build
python3 - <<'NODE_TESTS'
from pathlib import Path
import subprocess
roots = ['tests', 'src/lib', 'src/forms', 'src/pages/officer']
files = sorted(str(f) for root in roots for f in Path(root).glob('*.test.ts'))
assert files, 'No Node tests found'
subprocess.run(['node', '--test', *files], check=True)
NODE_TESTS
```

Phase 8 기술 PR [#43](https://github.com/zohijin-k/26-2-savings-officer/pull/43)·[#44](https://github.com/zohijin-k/26-2-savings-officer/pull/44)의 기존 검증은 Python **5,124**, 프런트 **70**개 통과(실패·오류·skip 0)입니다. 코드 main에서 접근 제어·신청자 제출 투영·bulk revision 핵심 **171**개를 추가 확인했습니다. 전체 결과는 검증 HEAD와 코드 main의 실행 코드·테스트 동일성으로 연결한 과거 결과이며 README 수정에서 전체 시험을 새로 실행했다는 뜻이 아닙니다. GitHub Actions의 event/pr-head/latest-main backend/frontend 검증과 로컬 전체 suite는 범위가 다릅니다. 기존 bundle·deprecation 경고는 지원 승인으로 바꾸지 않습니다.

## 버전과 release-manifest

README 정리 직전 확인한 최신 코드 main은 [`006f151b67801340bc50302ec2d66dd900024b0b`](https://github.com/zohijin-k/26-2-savings-officer/commit/006f151b67801340bc50302ec2d66dd900024b0b)입니다. 문서 전용 병합 이후의 현재 main SHA는 [GitHub main 조회](https://api.github.com/repos/zohijin-k/26-2-savings-officer/commits/main) 또는 아래 명령으로 확인합니다. 문서 커밋 SHA와 코드 검증 기준 SHA를 혼동하지 않습니다.

```bash
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

[전체 release-manifest](https://github.com/zohijin-k/26-2-capstone#release-manifest)는 네 코드 기준 SHA와 검증 범위를 연결합니다. 전체 내부 `release-manifest.final.json`과 증거·소스 아카이브는 비공개로 보존하며 공개 링크를 만들지 않습니다.
## 개인정보·권리·검증 한계

시험에는 합성 정보와 임시 DB·저장소만 사용합니다. 실서류·주민번호·OCR 원문·환경변수·쿠키·DB·업로드·모델·비공개 증거와 소스 스냅샷을 Git/PR에 올리지 않습니다. 마스킹이 원본 파일을 익명화한다는 뜻은 아닙니다. 실제 외부 OCR/LLM 호출과 실서류 정확도·신뢰도 보정, 최종 SHA 전체 브라우저 흐름, 다중 worker 세션·잠금은 이번 문서 검증으로 승인하지 않습니다.

프로젝트 LICENSE와 기여자·기관의 재배포 권한은 **미확정**입니다. 기존 공개 저장소도 신규 소스 공개 권한의 근거가 아닙니다. Noto subset 출처·조건, Pretendard GOV 고지, 기관 브랜드, PDF/HWP 서식 재사용, PyMuPDF의 AGPL/상용 조건 및 의존성 고지는 별도 확인이 필요합니다. [제3자 고지](THIRD_PARTY_NOTICES.md)를 확인하되 전체 프로젝트의 재배포 허가로 해석하지 마세요. 비공개 소스 스냅샷은 공개하지 않습니다.

**PRODUCTION_NOT_READY.** 운영 DB migration·배포·인프라 변경은 이 안내의 범위가 아닙니다.

[개발 안내](docs/DEVELOPMENT.md) · [데모](demo/README.md) · [엔진](engine_v2/README.md). 기존 하위 문서의 오래된 버전·실행 범위는 위 코드 기준과 대조하세요.
