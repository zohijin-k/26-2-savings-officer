# 담당자 시연 데이터 조사와 최소 제안

## 기존 도구: 단독 사용 불가
`demo/backend/tools/seed_application.py`는 기존 로컬 demo DB의 본인인증된 draft 중 2단계 미완료 신청만 고른다. 성명/생년월일/인증은 바꾸지 않고 신청서·동의 등을 채운 뒤 같은 탭의 /apply/upload 진입을 안내한다. 서류 업로드/최종 제출을 하지 않으므로 이 도구만으로는 담당자 접수 목록을 만들 수 없다. 신청자 화면 제거 후 그 UI 절차도 사용할 수 없다.

backend/seed-application.md spec은 인증 생성·변경 금지와 기존 API·검증 재사용을 명시한다. 이 도구의 의미를 바꾸지 않고 코드와 시험을 보존한다. README에서 담당자용 주입 도구인 것처럼 안내하지 않는다.

## 재사용할 수 있는 합성 자료
- `python -m demo.fixtures.make_samples`: demo/fixtures/samples의 가상 PDF를 생성한다. PDF만 생성하며 DB 신청/서류/Review는 넣지 않는다.
- `demo/backend/ocr/fixture.py`: 현재 구현은 고정 합성 파일의 stem으로 FIXTURES를 선택하여 정해진 시연 OCR 응답을 제공한다. 최초 조사에서 본문 표식으로 선택한다고 기록한 부분은 구현 재확인 후 정정했다. 엔진/외부 OCR을 새로 학습하거나 튜닝할 필요가 없다.
- `run_p4_scenarios.py::seed` / `_create`: 두배적금 A/D 정상, B 소득초과, C 저해상도 확인 필요 신청을 생성하고 제출한다. 원본 파일·사유·담당자 API를 한 번에 검증하는 가장 가까운 예제다.
- `run_p6_scenarios.py`: S2 정상, S3–S6 잘못된 문서/이른 발급일/입력 불일치/암호화, S7 소득초과, S8 확인 필요, S9 담당자 상세. S10은 취업지원으로 이번 담당자 시연에는 쓰지 않는다.
- `scenario_support.py::complete_synthetic_work`: 옛 합성 PASS 예제에 명시적인 합성 본인·근로 증거를 보충한다. 실제 신청/기존 판정을 교정하는 도구가 아니다.
- `scenario_support.py::seed_blocked_historical_review`: 현재 제출 API가 소득초과를 400으로 막는 것을 확인한 후에만 과거 상태의 합성 Review를 저장한다. 화면 데모에 FAIL 제출 우회를 일반화하지 않는다.
- 프런트 `?mock=1`: 메모리 합성 자료+SVG 원본을 바로 볼 수 있으나 DB 저장은 하지 않으며 실제 파일 API 검증을 대신하지 않는다. 두배적금 전용으로 정리 후 보조 미리보기로 유지할 수 있다.

시나리오 일반 실행은 임시 DB/storage에서 돌고 정리한다. `run_p6 --live`는 실제 demo DB/storage를 reset하고 끝에도 정리하므로 지속 가능한 주입 명령으로 안내하지 않는다. 이번 조사/검증에서 --live나 demo.backend.reset을 실행하지 않았다.

## 제안만: 별도 최소 CLI
파일 제안: `demo/backend/tools/seed_officer_demo.py` (아직 생성하지 않음).

제안 명령:
```sh
python -m demo.fixtures.make_samples
python -m demo.backend.tools.seed_officer_demo
# 위 도구가 만든 합성 신청/파일만 정리
python -m demo.backend.tools.seed_officer_demo --clean
```

1. P4의 정상(A)·확인 필요(C) 입력/샘플을 재사용하는 두 건만 만든다. 작성·업로드·제출은 기존 API 흐름을 사용하며 판정 규칙과 사유를 수정하지 않는다. 과거 합성 증거 보충이 필요하면 그 출처를 별도 명시하고 새로 만드는 시드 소유 건에만 적용한다.
2. 새 합성 신청만 만들고 고유한 버전 표식/접수번호를 둔다. 기존 신청/문서/Review는 UPDATE하지 않는다. 재실행 시 자기 표식을 찾아 중복 생성하지 않는다. 완성된 신청을 담당자 목록에서 실제로 조회할 수 있는지 확인한다.
3. 기존 로컬 demo DB/storage만 대상으로 한정하고 symlink/외부 경로를 거부한다. 새 DB라면 정상 초기화하되 기존 DB 전체 reset/삭제는 하지 않는다. --clean은 도구 표식이 있는 신청과 소유 파일만 정리한다.
4. FAIL/null/미배정의 화면 분류는 별도 합성 프런트 검증으로 확인한다. CLI의 최소 시연 목표는 PASS와 NEEDS_REVIEW 원본·사유이므로 확정 FAIL 제출을 통과시키거나 저장 판정을 재작성할 필요가 없다.
5. 시험은 임시 SQLite/storage에서 생성·재실행·정리·기존 데이터 보존·경로 제한을 검증한다. 별도 신규 시험 수는 기존 1,227개와 구별해 보고한다.

이 제안은 새 도구를 구현해야 담당자용 주입 절차가 완결된다는 조사 결과다. 사용자 승인 전에는 도구/fixture/DB를 만들지 않는다. 승인하지 않을 경우 기존 API 수동 주입 또는 명시적 목업만 사용할 수 있다는 한계를 README에 정확히 설명해야 한다.
