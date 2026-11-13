# 두배적금 담당자 화면

전북청년 함께 두배적금 담당자가 제출 서류의 원본과 기존 판정 사유를 확인하는 저장소입니다. 앱을 열면 담당자 화면으로 바로 이동합니다.

첫 화면은 **적합 서류**(문서 상태 `PASS`)와 **확인 필요 서류**(`PASS` 이외) 두 목록입니다. 확인 필요 항목을 선택하면 왼쪽에 원본, 오른쪽에 기존 사유 코드와 안내가 표시됩니다. 목록 분류는 저장된 판정을 바꾸지 않습니다.

## 관련 저장소

이 저장소는 다음 안내 저장소에서 분리한 네 화면 저장소 중 하나입니다.

| 구분 | 저장소 |
|---|---|
| 전체 안내 | [26-2-capstone](https://github.com/zohijin-k/26-2-capstone) |
| 두배적금 담당자 — 현재 저장소 | [26-2-savings-officer](https://github.com/zohijin-k/26-2-savings-officer) |
| 두배적금 신청자 | [26-2-savings-applicant](https://github.com/zohijin-k/26-2-savings-applicant) |
| 청년 취업지원 신청자 | [26-2-youth-applicant](https://github.com/zohijin-k/26-2-youth-applicant) |
| 청년 취업지원 담당자 | [26-2-youth-officer](https://github.com/zohijin-k/26-2-youth-officer) |

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

터미널 두 개에서 실행하고 <http://localhost:5173>을 엽니다.

```bash
# 저장소 루트
uvicorn demo.backend.main:app --reload --port 8000
```

```bash
cd demo/frontend
npm run dev
```

API 문서는 <http://localhost:8000/docs>에서 확인합니다. Vite가 `/api` 요청을 백엔드로 전달합니다.

## 시연용 데이터

가상 정보로 만든 저장소의 합성 PDF만 사용합니다. 저장소 루트에서 다음 명령을 실행합니다.

```bash
python -m demo.fixtures.make_samples
python -m demo.backend.tools.seed_officer_demo
```

도구는 로컬 데모 DB에 정상 1건(모든 업로드 서류 `PASS`)과 확인 필요 1건(`PASS` 이외 서류 포함)을 생성합니다. 같은 명령을 다시 실행하면 자체 생성 표시를 확인하여 중복 생성하지 않습니다. 화면을 새로고침하면 두 목록에 분류된 서류를 볼 수 있습니다.

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
