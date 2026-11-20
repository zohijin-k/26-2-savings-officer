# 두배적금 담당자 화면

전북청년 함께 두배적금 담당자가 제출 서류의 원본과 기존 판정 사유를 확인하는 저장소입니다. 앱을 열면 담당자 화면으로 바로 이동합니다.

첫 화면은 신청 건 단위 표입니다. 위쪽에서 역할(읍·면·동 / 시군 / 도·청년허브센터)을 고르면 보이는 범위와 처리 버튼이 바뀝니다. 탭은 **확인 필요**(담당자 판단 전, AI 판정이 적합이 아닌 건), **적합**(판단 전, AI 판정 적합), **처리 완료**(담당자 판단 있음)입니다. 행을 펼치면 확인 필요 사유를 미리 보고, 행을 누르면 왼쪽에 원본, 오른쪽에 판정·심사표·판독 결과가 표시됩니다. 탭 분류는 저장된 판정을 바꾸지 않습니다.

## 관련 저장소

이 저장소는 다음 안내 저장소에서 분리한 네 화면 저장소 중 하나입니다.

| 구분 | 저장소 |
|---|---|
| 전체 안내 | [26-2-capstone](https://github.com/zohijin-k/26-2-capstone) |
| 두배적금 담당자 — 현재 저장소 | [26-2-savings-officer](https://github.com/zohijin-k/26-2-savings-officer) |
| 두배적금 신청자 | [26-2-savings-applicant](https://github.com/zohijin-k/26-2-savings-applicant) |
| 청년 취업지원 신청자·담당자 | [26-2-youth](https://github.com/zohijin-k/26-2-youth) |

## 설치와 실행

Python 3.12 이상, Node.js 20.19 이상이 필요합니다. 저장소 루트에서 설치합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r demo/backend/requirements.txt
python -m pip install -r engine_v2/requirements.txt
cd demo/frontend
npm install
cd ../..
```

처음 한 번 `.env.example`을 `.env`로 복사하고 담당자 로그인 값 두 개(`OFFICER_PASSWORD`, `OFFICER_SESSION_SECRET`)를 채웁니다. `.env`는 커밋하지 않습니다. 그다음 터미널 두 개에서 실행하고 <http://localhost:5173>을 엽니다.

```bash
# 저장소 루트
python -m uvicorn demo.backend.main:app --env-file .env --reload --port 8000
```

```bash
cd demo/frontend
npm run dev
```

API 문서는 <http://localhost:8000/docs>에서 확인합니다. Vite가 `/api` 요청을 백엔드로 전달합니다.

## 담당자 로그인과 접근 제어

담당자 화면은 `.env`의 `OFFICER_PASSWORD`로 로그인해야 열립니다. 로그인은 8시간 유지되고, 머리글 오른쪽의 로그아웃으로 끝냅니다. 두 값 중 하나라도 비어 있으면 담당자 API가 503을 내고 화면에 설정 안내가 나옵니다. `?mock=1` 예시 화면은 로그인 없이 열립니다. 신청자 API는 신청을 만든 브라우저에만 열리고, 원본 서류(`/api/files/…`)는 그 신청자와 로그인한 담당자만 볼 수 있습니다. 역할·지역 선택은 로그인 뒤 화면 범위를 고르는 것이고 인증 수단이 아닙니다. 자세한 내용은 [개발 안내](docs/DEVELOPMENT.md#담당자-로그인과-접근-제어)에 있습니다.

## 신청자 화면과 연결

이 저장소의 백엔드는 두배적금 신청자 화면([26-2-savings-applicant](https://github.com/zohijin-k/26-2-savings-applicant))의 API도 함께 제공합니다. 백엔드를 `--env-file .env`로 8000번에 띄우고 신청자 프런트(5173)와 담당자 프런트(`npm run dev -- --port 5174`)를 함께 실행하면, 신청자 화면에서 제출한 건이 이 저장소의 DB에 쌓여 담당자 화면(로그인 뒤)에 바로 보입니다. 신청자 저장소의 백엔드는 띄우지 않습니다. 순서와 주의점은 [개발 안내](docs/DEVELOPMENT.md#신청자-화면과-연결해서-실행)에 있습니다.

## 시연용 데이터

가상 정보로 만든 저장소의 합성 PDF만 사용합니다. 저장소 루트에서 다음 명령을 실행합니다.

```bash
python -m demo.fixtures.make_samples
python -m demo.backend.tools.seed_officer_demo
```

도구는 로컬 데모 DB에 정상 1건(모든 업로드 서류 `PASS`)과 확인 필요 1건(`PASS` 이외 서류 포함)을 생성합니다. 같은 명령을 다시 실행하면 자체 생성 표시를 확인하여 중복 생성하지 않습니다. 화면을 새로고침하면 확인 필요 탭과 적합 탭에 한 건씩 보입니다. 시연 신청번호는 `DS-DEMO-` 뒤에 8자리 무작위 값이 붙습니다.

```bash
# 도구가 생성한 신청과 그 저장 파일만 정리
python -m demo.backend.tools.seed_officer_demo --clean
```

도구는 외부 DB나 서류 경로를 받지 않으며 기존 신청과 판정을 수정하지 않습니다. `demo/demo.db`, `demo/storage/`, 생성된 `demo/fixtures/samples/`는 커밋하지 않습니다. DB에 데이터가 없으면 빈 목록이 표시됩니다. 프런트 예시만 보려면 <http://localhost:5173/?mock=1>을 사용합니다.

이 합성 시연은 시연 고정 OCR 응답을 사용하므로 OCR 모델을 내려받을 필요가 없습니다. 로컬 OCR 자체를 사용할 때의 별도 모델 설치는 [개발 안내](docs/DEVELOPMENT.md)를 참고하세요.

## 개발 문서

- [개발 안내](docs/DEVELOPMENT.md): 환경·구조·검증 명령
- [데모 안내](demo/README.md): 시연 데이터와 보존된 백엔드 기능
- [엔진 안내](engine_v2/README.md): OCR·추출 도구
- [제3자 고지](THIRD_PARTY_NOTICES.md): 모델·글꼴·패키지 출처와 라이선스
