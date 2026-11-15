# 실행 계획 — 0~1단계 조건부 승인

2026-11-15 사용자가 0~1단계 실행을 승인했다. 아래 조건은 별도 재승인 없이 반영한다. 커밋과 2단계 구현은 승인되지 않았다.

## 조건부 승인 반영 — 1단계 보고 첫머리

1. 고정 오통과 상한을 폐기하고 새 0단계 기준값을 쓴다. 엔진별(own/참조) × 종류별 하나라도 증가하면 중단한다. own 전체 0/235 필수, 글자층 참조 전후 수치 완전 동일 필수다.
2. 새 0단계 값이 PR #7 own 0/235, 참조 전체 15/235, 납부 5/50과 다르면 1단계에 진입하지 않고 보고한다.
3. 1단계 첫 작업은 baseline의 실제 납부 필드 추출 호출을 함수 이름으로 확인·보고하는 것이다. 진단도 그 호출을 그대로 사용한다. 가입구분은 같은 추출 경로의 50쪽, 고지월/발급일 정부형 출력이 있으면 정부형 20쪽을 별도로 추가한다. 서식별 집계와 “합성·실서류 서식 차이 가능” 여부/근거를 보고한다.

## 2026-11-15 재개 승인 — 아래 이전 실행 절차보다 우선

- 기준 소스는 현재 브랜치 HEAD `2b4ab5949a2d7455a3da7da3ab0fd7c1f687e4d8`이며 main과 같다. PR #7 소스를 기준 소스로 사용하지 않는다.
- 사용자 삭제 두 폴더 외 engine_v2/data의 남은 일곱 폴더는 열거나 검사하지 않는다. 원본 실서류·기존 업로드·DB도 접근하지 않는다.
- 작업 공간은 `/tmp/own_adapter_work-67fp4sm5/`이다. 격리 소스·합성 PDF·목록·pytest·DB·업로드를 이곳에 둔다. 모델·설치 의존성만 링크한다.
- 영구 보존 위치는 `/Users/zohijin/Desktop/own_adapter_runs/before/`이다. 이전 숫자 기록 3개·로그 2개는 prior_ 구분으로 바이트 검증 후 이곳으로 이동했다. 새 측정 결과·집계·재현 정보·로그도 이곳에 쓴다.
- engine 기존 1748 passed / 3 skipped / 3 xfailed 결과를 사용하며 이번 0단계에서는 다시 돌리지 않는다.
- 순서는 backend → 시나리오 18개 → 프런트 세 명령 → 410쌍 → 합성 OCR이다. 각 묶음이 기준과 같아야 다음으로 진행한다.
- backend에는 작업 공간 내부 `--basetemp`를 지정한다. 시작 전 가용 공간 15GiB 미만이면 중단한다. 각 작업 전후 `df -h /`, 작업 공간 크기와 실행 중 표본 최대 크기·최소 가용량을 보존한다. ENOSPC 발견 시 즉시 중단한다.
- 도구·운영 코드·기존 시험·fixture를 바꾸지 않는다. 임시 파일 누적 개선도 이번 범위가 아니다.
- 410쌍 own 0/235, 참조 전체 15/235·납부 5/50과 다르면 1단계 진입 없이 중단한다. 이상이 없으면 승인된 1단계를 수행하고 종료 보고·커밋 승인 요청에서 멈춘다.
- 이번 작업이 만든 공간만 결과 보존을 검증한 뒤 삭제할 수 있다. 그 외 파일은 삭제하지 않는다.

이하 A~B 명령의 예전 `/tmp/own_adapter_before` 위치와 engine 재실행 부분은 역사적 계획이며 위 재개 절차로 대체한다. 실제 실행 명령과 종료 상태는 영구 보존 폴더의 작업별 execution JSON에 기록한다.

### 1단계 목록 입력 추가 승인

0단계 완료와 첫 진단/회귀 뒤 사용자가 사람 폴더 ID와 상대 PDF 경로 혼합 목록, 빈 줄·주석 무시, 잘못되거나 없는 줄 건너뜀, 비대상 문서 숫자 집계를 추가 승인했다. 새 진단 CLI와 새 시험만 보강하고 최종 검토·진단·회귀를 고정 소스로 다시 검증한다. 공용 도구·운영 코드·기존 시험은 바꾸지 않는다. 실제 입력 두 경로는 열기·목록 조회·존재 확인하지 않으며 커밋 파일에 전사하지 않는다.

사용자가 커밋 전 다섯 패턴을 채팅으로 다시 제공했다. 패턴 문자열은 이 문서에 적지 않고 staged diff 전체의 패턴별 숫자와 파일 목록만 보고한다. 영구 결과 및 외부 작업 공간은 커밋 후보에 포함하지 않는다.

## 0단계 시작 상태

| 확인 | 결과 |
| --- | --- |
| 최초 작업 트리 | 깨끗함 |
| main 최신 | 원격 main과 같은 `2b4ab5949a2d7455a3da7da3ab0fd7c1f687e4d8` |
| baseline main 이력 | `1a60da8` 확인 |
| 브랜치 | main에서 `work/own-adapter` 생성 완료 |

계획 승인 후 계획 파일 외 다른 dirty 파일이 없는지 재확인하고 main/운영 코드 변경이 있으면 기준선 소스부터 다시 확인한다. 반영된 조건과 문맥을 확인한 뒤 `task.py start`로 실행 상태로 전환한다. 문서 계획은 실행 결과가 아니다.

## A. 회귀 환경과 순서

기존 backend 시험 모듈은 import 시 samples를 탐색하므로 추적 소스만 복제한 격리 공간을 사용한다. 기존 ignored 데이터·업로드·DB·샘플 폴더를 읽거나 복제하지 않는다. 링크는 설치 의존성·모델·합성 글꼴에만 한정한다. 아래 폴더가 이미 있으면 덮어쓰지 않고 중단·보고한다. TMPDIR는 격리 checkout 밖으로 둔다. 새 Git 경계는 lint가 상위 ignore를 상속하지 않도록 하기 위한 것이며 커밋하지 않는다.

```sh
cd /Users/zohijin/Desktop/26-2-savings-officer
set -euo pipefail
test ! -e /tmp/own_adapter_before
mkdir -p /tmp/own_adapter_before/source /tmp/own_adapter_before/tmp /tmp/own_adapter_before/logs
git archive main | tar -x -C /tmp/own_adapter_before/source
git -C /tmp/own_adapter_before/source init -q
ln -s /Users/zohijin/Desktop/26-2-savings-officer/.venv /tmp/own_adapter_before/source/.venv
mkdir -p /tmp/own_adapter_before/source/engine_v2/models /tmp/own_adapter_before/source/engine_v2/data
ln -s /Users/zohijin/Desktop/26-2-savings-officer/engine_v2/models/own /tmp/own_adapter_before/source/engine_v2/models/own
ln -s /Users/zohijin/Desktop/26-2-savings-officer/engine_v2/data/synth_fonts /tmp/own_adapter_before/source/engine_v2/data/synth_fonts
ln -s /Users/zohijin/Desktop/26-2-savings-officer/demo/frontend/node_modules /tmp/own_adapter_before/source/demo/frontend/node_modules
export TMPDIR=/tmp/own_adapter_before/tmp
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=.
cd /tmp/own_adapter_before/source
```

필요 자산 부재/용량 부족/환경 오류는 다운로드나 기존 입력 재사용으로 해결하지 않고 먼저 숫자·코드로 보고한다. 새 격리 samples만 기존 합성 함수로 생성한다. 출력에 파일명이 섞이는 원래 시험/생성기 로그는 외부 합성 전용 로그로 보관하고 채팅에는 집계만 보고한다. 진단 도구의 출력은 이 예외 없이 수치·코드만이어야 한다.

아래 1~4를 순차 실행하고 각 결과를 검토한 다음 다음 묶음으로 넘어간다. 동시 실행으로 타이밍을 오염시키지 않는다. `set -o pipefail` 상태에서 tee 실패도 잡는다.

| 순서 | 명령 | 기대 결과 / 로그 |
| --- | --- | --- |
| 1 | `.venv/bin/python -m pytest engine_v2/tests 2>&1 \| tee /tmp/own_adapter_before/logs/engine.txt` | 1,748 passed / 3 skipped / 3 xfailed / 실패 0 |
| 2 | `.venv/bin/python -m pytest demo/backend/tests 2>&1 \| tee /tmp/own_adapter_before/logs/backend.txt` | 1,410 passed / 2 xfailed / 실패 0 |
| 3 | 아래 순차 루프 | 18모듈 / 1,885 counted checks / 실패 0 |
| 4 | `cd /tmp/own_adapter_before/source/demo/frontend && npx --no-install tsc -b && npx --no-install oxlint && npx --no-install vite build` | 세 명령 exit 0; stdout/stderr는 logs/frontend.txt로 보관 |

`--no-install`은 의존성 누락 때 내려받지 않도록 하며 실제 실행기는 기존 `tsc -b`, `oxlint`, `vite build`와 같다. 프런트 종료 후 저장소 루트로 돌아온다.

```sh
for f in demo/backend/tests/run_p*_scenarios.py; do
  module=$(basename "$f" .py)
  if ! .venv/bin/python -m "demo.backend.tests.$module" > "/tmp/own_adapter_before/logs/$module.txt" 2>&1; then
    echo SCENARIO_ERROR
    exit 1
  fi
done
```

루프는 실패 즉시 다음 모듈을 실행하지 않는다. 결과 수·exit code를 별도 회귀 집계에 남긴다. P14는 8종 빈 서식 검증을 하지만 numeric assertion counter가 없으므로 18모듈과 나머지 17모듈 합계 1,885를 구별한다.

**중단 규칙:** failed/XPASS, 예상치와 다른 passed/skipped/xfail 수, 시나리오 수·검사 수 차이, 프런트 비정상 종료가 하나라도 있으면 기준값 측정과 구현을 중단한다. 실패한 노드·예상/실제 숫자·소스/환경 근거·기대값 변경 필요 목록을 먼저 보고한다. 기존 시험/기대값을 수정하거나 환경을 조용히 고친 뒤 성공만 보고하지 않는다. 환경 변경 후 재시도도 사유 보고 후 승인된 다음 행동으로 한다.

## B. 수정 전 기준값 저장

### B1. 410쌍 — PR #7과 동일한 n=5, seed

회귀 전부가 일치한 뒤, 동일 격리 소스 루트에서 다음을 실행한다. 출력이 있으면 원래 도구가 거부하므로 기존 실패/중단 결과를 완료 결과로 재사용하지 않는다.

```sh
cd /tmp/own_adapter_before/source && PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.documentai_staged --samples 5 --seed 20261113 --output /tmp/own_adapter_before/paired.json
```

원 도구 산출물은 `/tmp/own_adapter_before/paired.json`, `paired.md`, `paired.rows.jsonl`이다. 생성 PNG는 도구의 임시 폴더에서 종료 후 삭제된다. 실행 경로는 원본 코퍼스·변환·독립 truth·지표를 유지하며 filename fixture나 AV로 대체하지 않는다.

다음 고정 숫자 집계 명령으로 `/tmp/own_adapter_before/paired_counts.json`을 남긴다. 기존 보고문 전체를 stdout에 내보내지 않는다.

```sh
cd /tmp/own_adapter_before/source && .venv/bin/python -B - <<'PY'
import json
import sys
sys.excepthook = lambda *_: sys.stderr.write('SUMMARY_ERROR\n')
from pathlib import Path
p = Path('/tmp/own_adapter_before/paired.json')
r = json.loads(p.read_text())
assert len(r['rows']) == 410
assert sum(x['expected'] == 'FAIL' for x in r['rows']) == 235
assert sum(x['expected'] == 'VALID' for x in r['rows']) == 175
out = {}
for engine in ('own', 'reference'):
    x = r['summary']['overall'][engine]
    out[engine] = {
        'ATTEMPTED': x['attempted'], 'ERROR': x['failed'],
        'FALSE_PASS': x['false_accept_count'], 'NEGATIVE': x['expected_fail_count'],
        'FALSE_FAIL': x['false_reject_count'], 'VALID': x['valid_count'],
        'REVIEW': x['status_counts'].get('NEEDS_REVIEW', 0),
        'PASS': x['status_counts'].get('PASS', 0),
        'FAIL': x['status_counts'].get('FAIL', 0),
        'X': x['status_counts'].get('X', 0),
    }
assert all(x['ATTEMPTED'] == 410 and x['ERROR'] == 0 for x in out.values())
payload = json.dumps(out, indent=2, allow_nan=False) + '\n'
Path('/tmp/own_adapter_before/paired_counts.json').write_text(payload)
print(payload, end='')
PY
```

동시에 stage × type × group × condition 집계와 각 사례의 상태/음성 PASS를 보관한다. 전후에는 모든 case·source/input fingerprint 일치를 요구하며 전체 합계로 새 오통과를 숨기지 않는다. 기존 PR 최종 기록과 다르면 원본 무변경 상태에서 원인을 보고하고 다음 측정을 중단한다.

오통과는 기대 FAIL에서 PASS, 확실한 오FAIL은 기대 VALID이면서 최종 FAIL이고 기존 allowlist의 확실한 재제출 코드가 있는 경우다. REVIEW는 어느 쪽에도 세지 않는다. 410 = VALID 175 + NEGATIVE 235, 총 820경로를 확인한다. 새 측정의 own 0/235, 참조 전체 15/235·납부 5/50 재현을 확인한 뒤에만 1단계로 진행한다. 이후 기준은 새 값이며 엔진별 × 종류별 오통과 증가와 참조 경로 수치 변화는 중단 조건이다.

### B2. 합성 글자층 PDF와 OCR baseline

완전한 생성 명령은 `research/corpus-command.md`에 있다. 기존 셀/Source 렌더러에 사전에 정한 가상 입력을 전달하는 임시 래퍼이며 생성기 소스·410쌍 입력은 바꾸지 않는다. 입력 PDF는 `/tmp/own_adapter_before/pdfs/`, 진단할 legacy 50건의 상대 ID 목록은 `/tmp/own_adapter_before/payment.ids`다. 계획은 15종·111 PDF·114쪽이며 실제 생성 수를 기록한다.

```sh
cd /tmp/own_adapter_before/source && PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.ocr_baseline --root /tmp/own_adapter_before/pdfs --out /tmp/own_adapter_before/ocr --engines own applevision --variants clean scan phone
```

`/tmp/own_adapter_before/ocr/`의 run.json, results.jsonl, summary.json, summary.txt를 저장한다. 기존 baseline은 상대 ID를 저장하는 예외가 있지만 이번 입력은 숫자 이름의 새 합성 PDF뿐이다. 새 진단 CLI에는 이 예외를 옮기지 않는다.

모든 등록 필드의 분자/분모를 보존하며 참조 부재·분류 실패·미지원·ERROR·빈 OCR을 구별한다. 인식 CER·쪽 CER·pooled CER, 단어 F1, own OCR 시간/처리 시간을 저장한다. 설정·seed·합성 입력 bytes와 추적 소스의 지문, 환경의 고정 수치를 별도 재현 기록으로 남긴다. 합성 입력 지문은 비교용이며 새 진단 출력에는 넣지 않는다. 원시 토큰·값·좌표는 저장하지 않는다.

예상 시간은 과거 합성 1쪽×2엔진×3변형 wall 16.69초를 근거로 114쪽 약 32분, 일정 예상은 30~60분이다. 실제 합성 pilot 뒤 갱신하고 시험과 동시에 측정한 시간은 채택하지 않는다. AV 빈 출력은 동일 합성 입력의 정상 native 실행과 비교해 환경 문제를 보고하며 모델/글꼴을 자동으로 내려받지 않는다.

0단계 재측정이 PR #7 own 0/235, 참조 전체 15/235·납부 5/50과 다르면 1단계에 진입하지 않고 중단·보고한다. 이후 전후 비교는 새 기준값 대비 엔진별 × 종류별 오통과 비증가, own 0/235 유지, 참조 수치 완전 동일을 모두 요구한다. 개별 음성 사례의 새 PASS도 감시한다.

## C. 1단계 순서

1. 먼저 `ocr_baseline_runtime.extract`에서 시작하는 납부 가입구분·고지월·발급일의 호출을 함수 이름으로 확인·보고하고, 진단도 동일 함수를 그대로 호출하도록 고정한다. 이어 source-map.md의 파일을 읽어 8항목 own/AV/공유 추출기 비교표를 만든다. 납부 가입구분·고지월·발급일의 실제 검색/정규식을 기록한다. 정부형 가입구분 미출력과 참조 부재를 구분한다.
2. `engine_v2/tools/own_adapter_diag.py`를 추가한다. 필요하면 진단 전용 helper만 분리한다. design.md의 입출력·닫힌 스키마·판정 우선순위를 따른다. 기존 엔진·운영 어댑터·추출기·규칙·시험은 바꾸지 않는다.
3. 아래 새 합성 시험을 추가해 독립적으로 정한 기대값으로 검증한다. 실패 코드 구현으로 기대값을 자동 생성하지 않는다.
4. legacy 50쪽과 별도 정부형 20쪽 clean 진단을 실행하고 서식별로 집계한다. 정부형 고지월·발급일 출력 여부를 코드로 확인한다. 실서류와 합성의 서식 동일성을 확인하지 못하거나 차이가 있으면 “합성·실서류 서식 차이 가능”이라고 근거와 함께 보고한다. 필드별 유효 참조가 50 미만이면 사유와 분모를 보고한다. 추측값을 채우거나 추출 성공에 맞춰 양식을 조정하지 않는다. 기존 셀 생성 범위에서 추가 표본이 필요하면 먼저 보고한다.

```sh
cd /Users/zohijin/Desktop/26-2-savings-officer && PYTHONPATH=. .venv/bin/python -B -m engine_v2.tools.own_adapter_diag --root /tmp/own_adapter_before/pdfs --ids /tmp/own_adapter_before/payment_all.ids --out /tmp/own_adapter_before/diag --engines own applevision
```

5. 새 시험을 먼저 실행한 뒤 격리 소스에 이번 새 도구/시험만 반영해 네 회귀를 다시 실행한다. engine 통과 증가분은 새 시험 수와 같아야 하며 backend·시나리오·프런트는 기준과 같아야 한다. 기존 시험 실패는 수정 없이 즉시 보고한다.
6. 새 지식의 spec 반영 필요성을 검토한다. 필요하면 진단 전용 규약만 추가한다. 전체 변경을 검토하고 운영 코드·기존 시험 무변경과 AV 경로 불변을 확인한다.
7. 아래 보고를 완성하고 멈춘다. 커밋과 2단계 시작은 실행하지 않는다.

## D. 추가 시험 목록

예정 파일은 `engine_v2/tests/test_own_adapter_diag_codes.py`, `test_own_adapter_diag.py`다. 필요하면 같은 prefix로 스키마/누출 시험만 분리한다. 모두 가짜 값/직접 만든 PDF를 사용하고 실제 엔진이 필수인 단위 시험은 만들지 않는다.

| 묶음 | 사례 |
| --- | --- |
| 12코드 | OK부터 OTHER까지 각 1개 이상 손으로 만든 토큰/상자/줄과 독립 기대값 |
| 우선순위 | 라벨 부재/공백/분할, 값 부재/다른 줄/합침, 순서/정규화/문법/오인식의 충돌, OK 우선, 후순위 코드 도달 |
| 의미/참조 | 라벨 없는 가입구분 본문, 월 목록 구성 요소, 무라벨 발급일, 정상적인 아래 칸, 참조 부재/비literal/구조값 |
| 구조 | 이웃 열의 같은 값 오채택 방지, 다른 열에서 라벨 조립 금지, 다중 후보 OTHER, 90/180/270 회전과 DPI 변화 |
| Unicode | NFC/NFD·NFKC, 전각 숫자/괄호/마침표/물결표, 한글 사이 공백, 기존 NFKC에서 해결된 경우 OK |
| 입력 | 폴더/목록/한도, 중복/탈출/비PDF/잘못된 인자, 암호/열기 오류/빈 문서/글자층 없음/짧음/혼합/여러 쪽, 이름 변경 시 판별 불변 |
| 분모/수치 | 0 분모 null, 코드 배타성, 처리/건너뜀/엔진 오류, 참조 부재·오분류·빈 OCR, 중복 엔진/미등록 필드 거부 |
| 출력 보호 | stdout/stderr/모든 결과/native/예외/argparse sentinel 부재, 임의 key/값/경로/좌표/hash 거부, alias/덮어쓰기/쓰기·DB·네트워크 차단 |
| 호출 계약 | clean 설정 재사용, 양 엔진 원 토큰/신뢰도 불변, 예외 시 wrapper 복원, 원 AV 호출과 추출 입력 일치 |

정확한 pytest 수는 구현 후 collection으로 보고한다. 아직 시험을 만들지 않았으므로 증가분을 확정 수치로 쓰지 않는다. 2단계의 어댑터 성공·보호 필드·신뢰도 최솟값·표 경계 고정 사례는 다음 승인 계획에 남기고 이번에는 구현하지 않는다.

## E. 1단계 종료 보고와 중단

| 보고 항목 | 내용 |
| --- | --- |
| 조건부 승인 반영 | 새 기준값·엔진별/종류별 증가 중단·참조 완전 동일·baseline 추출 함수 동일·정부형 20쪽 추가·서식 차이 표시를 보고 맨 앞에 짧게 적음 |
| 수행/변경 | 모든 변경 파일, 운영 코드 무변경 증거, 네 회귀의 기준→실측→증가분 |
| 기준값 | 410쌍 엔진별 오통과/오FAIL/REVIEW/PASS/ERROR와 분모, 과거 PR과 차이 |
| OCR 표 | 모든 종류×필드×2엔진×3변형, CER/단어 F1/own 시간, 제외 종류/참조 부재 |
| 경로 비교 | 8항목과 납부 3필드의 실제 검색 방식 |
| 합성 진단 | 쪽 수, 제외/오류 수, 종류×필드×엔진의 코드 수/비율과 분모 |
| 원인 가설 | 관측 코드/비율만 근거로 사용. 실제 서류의 원인은 아직 미확정으로 표시 |
| 수정안 | own 경계의 후보 위치와 계약, 다른 서류 영향, AV 불변·신뢰도 보존 검증, 남은 불확실성 |
| 사용자 명령 | 지정된 납부 목록/전체를 따로 한 줄·절대 cd·&&·인용한 glob·주석 없이 제시. 목록 존재 여부는 사용자 명령 안에서만 확인. 목록/전체는 동일 진단 출력 루트의 별도 하위 폴더로 결과 충돌 방지. 예상 시간은 합성 실측으로 갱신 |
| 다음 승인 | 진단 도구+시험+문서의 1단계 커밋안. 수정 계획은 실제 서류 진단 결과를 받은 후 별도로 승인 |

스테이징 전에 파일 목록을 검토하고 커밋 전 지정 다섯 패턴 검사 결과를 숫자로만 보고한다. 패턴 문자열 자체와 실제 서류 경로는 이 커밋 대상 문서에 전사하지 않는다. 하나라도 0이 아니면 커밋하지 않는다. 계획 승인은 커밋 승인이 아니다. amend·push·공저자 trailer는 금지한다.

## 실행 완료 조건

네 회귀 기준 일치 → 410쌍 재현 확인 → 합성 OCR 기준값 저장 → 동일 추출 경로의 진단·시험 → 1단계 종료 보고 순서다. 어느 중단 조건이든 그 지점에서 보고하고 후속 단계는 실행하지 않는다. 1단계 완료 시 커밋 승인을 요청하며 실서류 결과와 수정 계획 승인 전에는 2단계를 시작하지 않는다.

## 실행 기록 — 0단계 중단

- engine 회귀: 1,748 passed / 3 skipped / 3 xfailed / exit 0, 기준과 일치.
- backend 회귀: ENOSPC로 exit 120. 마지막 진행 표시는 89%이나 정상 최종 집계가 없으므로 통과/실패 총수를 확정하지 않는다.
- 약 52% 진행 확인 시 가용 공간 0.3GB를 관측해 중단을 알렸으나 중단 신호 시도 때에는 이미 비정상 종료했다.
- 종료 확인 후 이번 작업이 만든 외부 pytest 임시 폴더만 정리했다. 로그와 숫자 기록은 보존했고 가용 공간 약 14.4GB를 확인했다. 시험 코드·기대값은 바꾸지 않았다.
- backend 재실행, 시나리오, 프런트, 410쌍, 합성 PDF/OCR 기준값, 1단계 진단 구현은 실행하지 않는다. 사용자 지시를 기다린다.
- 상세: stage0-stop.md. 이 기록은 1단계 완료 보고가 아니며 커밋 승인을 요청하지 않는다.

## 최종 1단계 실행 결과

목록 입력 추가 조건까지 반영한 고정 소스로 새105개 시험, 전체 engine1853/3skip/3xfail, backend1410/2xfail, 시나리오18/1885/0, 프런트세명령exit0을 확인했다. 합성70쪽420필드기록의실행오류는0이며 이전합성분포와동일하다. 기존보호소스403개와 새소스4개의지문을확인했다. 실제입력경로와목록은읽거나존재확인하지않았다. 최종수치·한계·다음제안은 stage1-report.md, 독립검토는 review-stage1.md에 기록했다. 외부결과·작업공간은커밋대상이아니다. staged전체의사용자지정5패턴과파일목록을보고하고커밋승인요청에서멈춘다.

## Approved dispatch follow-up

The two requested aggregates were absent from diagnostic output. Add completed-page route distributions and reference-versus-engine route cross-tabulations to both summaries. Add ROUTE_MISMATCH after OK, with absent-reference and unavailable-path populations preserved. Extend only the existing new diagnostic files, tests, usage/spec and task documents. Inspect existing recognition predicates and persist their literal/number/layout cues in research/adapter-contract.md. Run the focused suite, the exact preserved 70-page corpus and full engine_v2 suite sequentially in a fresh tracked-source isolation. Verify added engine passes equal collected new tests, compare field flags and code transitions against diag_final, repeat the five-pattern staged-diff scan and report all staged paths. Stop for renewed commit approval.

## Dispatch follow-up verification

Focused tests pass 127, including 22 additions. Full engine_v2 passes 1875 / 3 skipped / 3 xfailed. The 70-page native rerun preserves the prior 420 comparison flags and dispatch observations, with government own billing-month 20 and issue-date 10 now ROUTE_MISMATCH. Summary outputs include route page distributions and cross-tabulations. Source/input identity and the recognition-predicate review are recorded. An initial sandbox Apple empty-OCR run is retained as superseded evidence. The candidate remains 20 files and waits for renewed approval after the staged-pattern scan.

## Stage 2-1 proposed implementation sequence

1. Obtain approval for the current stage-2-1 planning artifacts and regression scope. Reactivate the same Trellis task with task.py start after approval. Record the 95d9ef7 baseline and original protected source identities.
2. Add the diagnostic-only route helper and primary-call observation plumbing. Preserve the three-item extraction API, original words/confidence, original field codes and output rows. Implement condition decomposition, original-result parity, one observation per page/engine and explicit missing/error populations.
3. Extend closed summaries with O/X counts, fixed bins and ordered pattern-to-route counts. Add summary_brief.txt and static value-free help. Implement the approved error matrix without modifying shared selector/runtime/provider files.
4. Add a separate independent route diagnostic test file under engine_v2/tests. Cover each atom, threshold and bin boundary, combined predicates, actual dispatch parity, prospective OTHER cases, field deduplication, counterfactual exclusion, restoration, sentinel leakage, each error code, help exit 0 and brief self-containment. Run focused tests first. On any existing-test failure, report its cause and stop before repairs or expectation edits.
5. Create tracked-source isolation, link installed dependencies/models only and restore the exact preserved synthetic corpus. Verify the 70-page selection bytes against prior hashes. Run both original engines under the known native execution conditions. Compare all prior results.jsonl rows and existing summary sections with the accepted stage-one corpus run. Record legacy/government tables for every new aggregate family. Generator changes count zero.
6. Run engine_v2/tests and count newly collected tests relative to baseline 1875/3skip/3xfail. Apply the tools-outside regression condition agreed during plan review. If the literal interpretation remains, run backend/scenarios/frontend sequentially in the same tracked-source isolation with synthetic-only runtime trees and the existing free-space monitoring procedure.
7. Review source boundaries and schemas, update the diagnostic spec/usage documents, retain long-lived numeric artifacts and exact source/input identities outside Git, then freeze the candidate. Use the five patterns already supplied by the user at this gate. Report counts over the whole staged diff and the exact staging list. Propose one coherent stage-2-1 commit and stop for separate approval.
8. Include two filled operator commands solely in the final chat report. The execution command uses absolute cd, &&, caffeinate -i, the user-supplied whole-root input, the designated fresh output and own applevision. The viewing command prints only summary_brief.txt. Stage 2-2 follows user-provided expanded results and separate instructions.

Proposed changed files are own_adapter_diag.py, own_adapter_diag_evidence.py if needed, a new own_adapter_route_diag.py helper, a new test_own_adapter_route_diag.py, the diagnostic usage/spec documents and this task's planning/research/review/report/context files. Classifier, extractor, adapter, decision, generator and shared runtime files have zero planned edits.

## Stage 2-1 implementation approval

On 2026-11-15 the user approved implementation. Changes under engine_v2/tools/, engine_v2/tests/, engine_v2/docs/ and .trellis/ require engine_v2 tests only. A changed path outside this set triggers backend, all 18 scenario modules and frontend checks as well. Report both git diff --name-only main...HEAD and working-tree paths to prove the decision. For H1/H2, report supporting/refuting synthetic numbers and exact summary_brief row families the operator should inspect. The five supplied patterns are available for the final staged-diff scan.

## Stage 2-1 verification complete

New108 and existing focused127 tests pass. Full engine1983/3skip/3xfail reconciles to the108 added tests. Native70-page diagnosis preserves all420 prior field rows, all prior summary sections and run metadata, with210 MEASURED condition paths and zero diagnostic/parity errors. The approved four-directory path condition selects engine-only verification. Detailed H1/H2 evidence, operator brief row guidance and both Git path lists are in stage21-report.md. Final staged five-pattern counts are 0/0/0/0/0 across 13 files. Separate commit approval remains.

## 2-2단계 실행 계획 — 구현 승인 대기

1. research/route-stage22.md와 PRD의 추천안 A, 2순위 보류 및 알려진 fixture/기대값 변경 범위를 승인받는다. 같은 Trellis 작업을 다시 시작한다. 현재 설계 단계에서는 운영 코드와 시험을 수정하지 않는다.
2. cdbe672와 원 before 결과를 고정하고 보호 소스/원 합성 입력 바이트를 확인한다. 작업 공간과 장기 결과를 분리하고 설치 의존성·모델·글꼴만 링크한 새 추적 소스 격리를 준비한다. 허용된 구조자료는 복제하지 않는다.
3. 정부형 인식 밴드와 진단의 관찰을 같은 helper로 연결한다. 추천 식과 HEADER_HEIGHT_RATIO 의미를 구현하고 승인받은 정상 fixture와2개 시험 영향만 함께 조정한다. 실제 재현3쪽/구조 패딩 회귀, legacy50·정부형20의 분기 시험을 추가한다. 다른 기존 실패는 고치기 전에 이유를 보고한다.
4. 기존 원 결과 검증·요약을 재사용한 읽기 전용 ocr_baseline_compare.py와 독립 시험을 추가한다. 파일 경로/ID·값 노출, 음수차이·0분모·미측정·CER>1·훼손·코호트 차이와 정상 CLI 진입점을 확인한다.
5. 새 focused 및 전체 engine 시험을 실행하고 증가분=새시험 수를 확인한다. backend 직전 df -h /가용15GiB 이상을 확인한 뒤 backend,18시나리오,프런트3명령을 순차 실행한다. 새시험이 없는 그룹은 기존 수와 같아야 한다. 환경 실패/기존 실패는 보고하고 중단한다.
6. 원410쌍을 같은 원 도구로 측정해 before와 엔진×종류별 잘못된PASS·FAIL·담당자확인·PASS를 비교한다. 개별 새 음성 PASS 또는 잘못된PASS 증가 하나라도 즉시 멈춘다. 모든 reference 결과가 같아야 한다.
7. 원 전체 합성111PDF/114쪽·동일settings/seed에 대해 own/AV × clean/scan/phone OCR baseline을 새 폴더에서 측정한다. 새 비교 CLI로 before와 모든 종류/필드의 비율·인식·시간을 표로 비교한다. own2%p 초과 저하·AV/참조 변화는 이유를 보고하고 사용자 기준에 따라 승인 대기한다.
8. 합성70쪽과 실제 OCR 재현3쪽을 새진단으로 재실행해 경로 교차표를 전후 비교한다. 글자층/AV 경로가 바뀌면 목록과 이유를 보고하고 승인을 기다린다. 추천A의 예상은 원70쪽 경로 유지와 재현3쪽 own→LEGACY다. 정부형 own20쪽 미해결을 명시한다.
9. 한국어 표 보고와 소스/시험/부작용 경계 검토, spec/문서 갱신을 완료한다. staged diff 전체 사용자5패턴을 숫자로 보고하고 비영인 경우 파일/줄번호만 보고한다. 정확한 git diff --cached --name-only 목록과 커밋안을 제시하고 승인에서 멈춘다. 공저자 줄·amend·push는 실행하지 않는다.
10. 채팅에만 실제 경로를 채운 사용자 명령을 제시한다. 진단/결과brief보기, 전체 OCR 재측정, before/after 비교를 각각 한 줄로 적고 절대 cd 및 && 연결을 사용한다. 실행 명령은 caffeinate -i를 포함한다. 사용자의 실서류 실행 중에는 작업하지 않는다.

예상 운영 변경은 nhis_payment_gov.py의 인식 밴드와 최소 내부 helper다. 진단 helper, 비교 도구, 새 합성 시험 fixture/회귀, 승인된 기존 진단 시험 영향, 문서/Trellis 기록이 함께 변경된다. 기존 서비스 판정·threshold·재업로드·쪽수 검증, 원 OCR/어댑터와 원 생성기 파일은 변경 범위에 포함되지 않는다.
