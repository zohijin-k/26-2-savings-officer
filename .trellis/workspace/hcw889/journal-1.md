# Journal - hcw889 (Part 1)

> AI development session journal
> Started: 2026-09-14

---



## Session 1: 현황 대시보드 초안
<!-- trellis-session: v=2 fp=99580ec87009e60f -->

**Date**: 2026-09-15
**Task**: 현황 대시보드 초안
**Branch**: `main`

### Summary

두배적금 신청·심사 현황 대시보드 프론트엔드 초안 작성(Vite+React+TS+ECharts, '26년 규모 기반 목업 데이터, 전북 14개 시군 지도, 기준일 슬라이더). 피드백 반영: 작성 시작 데이터 제거, 배점·커트라인 정보를 하단 담당자용 영역으로 분리

### Git Commits

| Hash | Message |
|------|---------|
| `1ef266d` | 대시보드 데모 생성 (목업데이터) |

### Status

[OK] **Completed**


## Session 2: 신청자·담당자 연결 (백엔드 통합)
<!-- trellis-session: v=2 fp=513e3c609e4ec65f -->

**Date**: 2026-11-17
**Task**: 신청자·담당자 연결 (백엔드 통합)
**Branch**: `feat/unified-backend`

### Summary

이 저장소의 백엔드가 두배적금 신청자 화면과 담당자 화면의 API를 함께 제공하도록, 신청자 저장소의 신청자 API 변경을 3방향 규칙으로 합쳤다. 신청자 화면에서 제출한 건이 이 저장소의 DB에 쌓여 담당자 화면에 바로 보인다. PR #16으로 main에 병합됐다.

### Main Changes

- 제품 코드 5개: 신청·서류·제출 API 3개는 신청자 저장소 것으로 교체, common.py와 verify_upload.py는 병합(충돌 0)
- 시험 36개와 시연 기대값 9개: 신청자 저장소 것을 들이고, 이 저장소 시험 3개의 단언 6곳은 저장된 판정을 확인하도록 수정
- 규격 unified-backend.md와 연결 실행 문서 추가. 엔진, 프런트, DB 구조, 담당자 API는 변경 없음

### Git Commits

| Hash | Message |
|------|---------|
| `528eb57` | feat(backend): 신청자 API를 합쳐 한 백엔드가 두 화면을 제공 |
| `e114a21` | test: 신청자 경계 시험을 들이고 저장된 판정으로 확인하도록 수정 |
| `ceae894` | docs: 연결 실행 안내와 규격, 태스크 기록 추가 |

### Testing

- [OK] 엔진·백엔드·시나리오: 같은 Windows PC의 변경 전 결과와 비교해 새 실패 0, 백엔드 통과 1,256에서 1,368로 증가
- [OK] 임시 DB의 격리 서버에 두 프런트를 붙여 제출, 담당자 목록·상세, 담당자 결정, 마이페이지 반영 확인(합성 서류)

### Status

[OK] **Completed**

### Next Steps

- fcntl을 쓰는 13개 시험 모듈은 Windows에서 돌지 않으므로 리눅스나 맥에서 확인
- 신청자 API 코드가 두 저장소에 있으므로 한쪽을 고치면 다른 쪽에도 반영
