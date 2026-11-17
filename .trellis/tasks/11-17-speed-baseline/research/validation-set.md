# G1·G2 검증 세트와 수정 전 기준값 (11/17)

## 만드는 방법

- 생성기: 발표용 세트와 같은 `engine_v2.tools.documentai_staged`(내부 `documentai_corpus_v2.sources`, `cases_for_source`). 코드를 바꾸지 않았다.
- 명령: `cd <REPO> && .venv/bin/python -B -m engine_v2.tools.documentai_staged --samples 10 --seed 20261117 --output <WORK>/validation_s10.json`
- 검증 세트 = 그 결과의 `normal_baseline` 그룹(조건 original) 중 **sample 6~10**, 25건(주민등록초본·납부확인서·자격확인서·자격득실확인서·4대보험 각 5건, 발표용 세트와 같은 구성).
- seed만 바꾸면 원본이 바뀌지 않는다: seed는 흔들림 변형(회전·촬영 등)의 난수에만 쓰이고(documentai_corpus_v2.py:165, 206), 원본은 sample 번호로만 정해진다
  (documentai_corpus_v2.py:38-51, 210-211). 실제로 seed 20261117의 sample 1~5 원본 25건은 발표용 세트(seed 20261113)와 입력 지문 25/25가 같았다.
  그래서 sample 번호 6~10(가상 이름·발급일 값이 다른 원본)을 검증 세트로 쓴다. 발표용 세트와 겹치는 입력은 0건이다.
- 한계: 같은 생성기라 **서식 배치(제목·표 위치)는 발표용 세트와 같고 가상 이름·날짜 값만 다르다.** 배치에 맞춘 수정은 검증 세트에서도 함께 오를 수 있으므로,
  검증 세트가 오른 것만으로 일반화를 단정하지 않는다.
- 생성된 그림·PDF는 도구의 임시 폴더에서 지워지며 커밋하지 않는다. 아래 지문으로 같은 입력인지 확인한다.

## 두 번째 검증

두 번째 합성 검증 세트(다른 배치·글꼴)는 생성기 변경이 필요해 이번 주 만들지 않음. 대신 G1은 실서류 4대보험 판별률, G2는 실서류 납부확인서 120쪽 월별 필드(ocr_baseline, 값 유무 포함)를 그림자 평가로 두 번째 검증에 씀.

## 수정 전 기준값 (own, normal_baseline, 커밋 345aa0f)

| 세트 | G1 서류 분류 | G2 핵심 항목 (추출기 불린 항목 기준) | 작성 항목 전체 기준 | 글자층 참조(A) G1 / G2 |
| --- | --- | --- | --- | --- |
| 발표용 (seed 20261113, sample 1~5) | 20/25 (80.0%) | 145/165 (87.9%) | 145/190 (76.3%) | 20/25 / 165/165 |
| 검증 (seed 20261117, sample 6~10) | 20/25 (80.0%) | 145/165 (87.9%) | 145/190 (76.3%) | 20/25 / 165/165 |

놓친 항목은 두 세트가 같다:

| 서류 종류 | 항목 | 발표용 | 검증 | 원인 코드 |
| --- | --- | --- | --- | --- |
| nhis_payment | 월별고지금액 | 5 | 5 | 구조 |
| nhis_payment | 월별장기요양보험료 | 5 | 5 | 구조 |
| nhis_payment | 건강보험료 | 5 | 5 | 구조 |
| nhis_payment | 장기요양보험료 | 5 | 5 | 구조 |
| insurance_4 | 성명·생년월일·발급일·발급번호·가입내역 (분모 밖) | 25 | 25 | 판별 |

원인 근거는 research/d1-findings.md c절.

## 검증 세트 지문

| 서류 종류 | sample | 원본 지문(source_fingerprint) | 입력 그림 지문(input_fingerprint) |
| --- | --- | --- | --- |
| insurance_4 | 6 | `a08fb095df4b833bd9e9f7675d30d42d9fe364a55a3f87cac36d05f555a95c6a` | `8733e977087a310fefe33754642b340d9cbb8f1fb4929dbd9b707ce76bb34955` |
| insurance_4 | 7 | `5aef3c27b02140c8e31c5ee6441ac7b35296d0d5f3a9249fc0e0aa3410b63c51` | `255de89325ae292ee4500a6e9cb3d05602a01c85bdc13d2024c85fb14af2a625` |
| insurance_4 | 8 | `cc2aa686924c7abc69fd50bbfeeeee7c459c68d4437eb674b15bfdcaec15dcd5` | `c5acd84754925e36181ce6552f00a756f41e1da1d3d5d67bbede4fb74369f914` |
| insurance_4 | 9 | `6c72ec5105203669cee87193a383ffa502987e5812140ce4c1eada132239662d` | `76b8d91b861e35bec919bc47578f079641d3b74ed1acdb35f2a1ffbdc4a59ecb` |
| insurance_4 | 10 | `8d2980ed2abe1bf50d7f93c33c7ed1f2b2419d81e17f4841e93ebb7784eb945e` | `53a45e524920765a6bf2fee5a0adb9d2cf1a82d5c373777501f21ecea642d39b` |
| nhis_acquisition_loss | 6 | `c098b8913d0f2b7f2d08777abbf611320c94ee80937b964a97a1cdc0087d3155` | `7821b78da0c87accb488ea485f1a0bd6c1f21b3cfea35e531da6265d647809e8` |
| nhis_acquisition_loss | 7 | `8aa9913b4c32b9ffdac1361a53bdfa28d4a2fe70bbec8b26324cafb2d58ccb5c` | `0b604eced21e232c8970be850d3ef51627bb736fffec02a63fbadb9e8a991394` |
| nhis_acquisition_loss | 8 | `58c949c6b9d74ebcf87cb9839da526e53adcbefdbdfe3e06ccfbf5bc3e597c9c` | `a3084e893fcf1b4de8c78df4e3279914a609d3a98a30facabd3e3a839fe70490` |
| nhis_acquisition_loss | 9 | `ae2aacb798e631a691afe21883299a4e830d063f93125b3cf7901b92a6d234f3` | `06c062b113dc6cb28f432139539c475be6ac944a401e4a6081a1cd15d42a25c7` |
| nhis_acquisition_loss | 10 | `3481ed2daef520deb04012ce1fada637092cd6ccee0c6ac409b8e8e2b48f806e` | `836187d0842e0ebfbc34e695c9292f2dd21ef3bde60871be28b2676baf681235` |
| nhis_payment | 6 | `132ae1fcae1781b164cec8d8c60bded4315e58a702410da59fc36d422fc2047a` | `5e2328c012dd4ef4f42c3f7ee4e8c43a5d05bc3e799f28da2e3c3aa8bbade99f` |
| nhis_payment | 7 | `b6ae9f94a8c743afd94ded67df1d49f066053a661f5d6b686852d9cd3fc31434` | `ae77c65daf395c8746d9cd2b1ae372d4346ea25b51d24df2bb1d4310fb542686` |
| nhis_payment | 8 | `d3212f17239ddd4d6abc06b0d36a8f76e564c01872954fe6ad5d69e5d196d8dc` | `b407070ae527cf1103ab1ea05a6cdb9af8ce686ed2bd26de4c07a175b444914e` |
| nhis_payment | 9 | `bf4481835dda10aa3b973f6e15ebe98b49661f6af1e3f3aca53b35be279acfa1` | `54280ce71172558dc4f533a4df211902b0b14b15156db8c017739e13acfc6313` |
| nhis_payment | 10 | `0128239d767a64dfafbde897540e8db85c8dd7c5d46ca337a72ee6b7a7fb9b7d` | `9f3dc5de0943624f9732796ffa4ce9d627a7af48bf9346746e42ed92cfe53116` |
| nhis_qualification | 6 | `3d5bd46b900b58d0d785b2a5036a4c4c0acb02066a5ad426549f680af3ffbb75` | `86604e6e7bdae24a714569d872493da0cbebf7636b57274121b672ea66dc3802` |
| nhis_qualification | 7 | `e68d32f40c06b64e28e670c38f98a5eed2a1072e6387c494af80add609edc7f7` | `407f835adb8d00305bccbcc54fc51286df7a9dda459ab57949af88aaf4215d1c` |
| nhis_qualification | 8 | `e092683072f0b4f3c11fd82efc133de5195736873e603e24e423ce9bf4697578` | `b7e4f361ca75aa968545fdf2c93501a953d1ff6685e743a242084ed640b8b652` |
| nhis_qualification | 9 | `0c996a06a263dd51e9a928fabf3e1617f3e52478b0347828f982118f738e69b8` | `17db39a20783c872a2821fc88a776eda17ef95d6b5574bb55b54a6b8abba68a4` |
| nhis_qualification | 10 | `9207d2e771322f052edf48895130b6482f8059d8b5bfb90450f9f668811bd8c8` | `796943afdac9c0110b505e6d3a5af65974c0af687cba985668334481a2e2aa8c` |
| resident_abstract | 6 | `da4424f9d74536ec148509179a7e3afbc50fd8d82ed86d450fc6b8439868e032` | `ad9277b17b0567925a9c7d40c36b9e3be78d16c90e469415c374f5dffeffd398` |
| resident_abstract | 7 | `ebf772f6994844760dca010d47efb4c987c9e98bff4778caf61804a40aaa105c` | `adda6d452b95a425742d53b80959ffae6289046e5ba880e76d6efa587d316ed1` |
| resident_abstract | 8 | `4447df29c09be28f83113f7e59ec4bc046f2eaea021d86f62e6bfeaaa782aa93` | `34b7b2412fe0574010bb49cd58c9f33ddd345f9dce0092d90220017611028a15` |
| resident_abstract | 9 | `b248c503e563ac205552af8966c4917963f3ced7a8656201cb7e59282a6aee54` | `7315713cff343c1cd8410892b5cb688ca36f365df8be71dbe958a91b77d02bbf` |
| resident_abstract | 10 | `5e1e4affb1c30b7806603cef92f81a3cd481018f2e5540e65465c112659f96bb` | `077619397b12ae57dea9a56d433929fb24a4e400452ac6929949b98741dab877` |
