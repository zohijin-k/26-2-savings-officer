# Final original-baseline paired comparison

410 pairs / 820 stages; same source metadata and all input fingerprints; violations: 0. No interrupted candidate is included.

| Stage | Subset | False PASS before→after | False reject before→after | Review before→after |
| --- | --- | --- | --- | --- |
| own | ALL | 0/235 → 0/235 | 0/175 → 0/175 | 255 → 250 |
| own | nhis_payment | 0/50 → 0/50 | 0/35 → 0/35 | 65 → 60 |
| reference | ALL | 20/235 → 15/235 | 0/175 → 0/175 | 250 → 250 |
| reference | nhis_payment | 10/50 → 5/50 | 0/35 → 0/35 | 40 → 40 |

Gross review transitions are separate from net counts.
- own: new review transitions 0, resolved reviews 5, corrected existing false passes 0.
- reference: new review transitions 0, resolved reviews 0, corrected existing false passes 5.

| Payment stage | Exact raw / normalized before→after | Raw CER before→after | Normalized CER before→after | Missing before→after | Unextracted before→after |
| --- | --- | --- | --- | --- | --- |
| own | 492/910 / 492/910 → 492/910 / 492/910 | 0.708425 → 0.708425 | 0.691447 → 0.691447 | 365 → 365 | 195 → 195 |
| reference | 765/845 / 765/845 → 765/845 / 765/845 | 0.133903 → 0.133903 | 0.131073 → 0.131073 | 80 → 80 | 260 → 260 |

## Payment per-field exact totals

| Stage | Field | Raw exact before→after | Normalized exact before→after |
| --- | --- | --- | --- |
| own | 건강보험료 | 6/70 → 6/70 | 6/70 → 6/70 |
| own | 납부자번호 | 50/70 → 50/70 | 50/70 → 50/70 |
| own | 납부총액 | 50/70 → 50/70 | 50/70 → 50/70 |
| own | 문서확인번호 | 50/70 → 50/70 | 50/70 → 50/70 |
| own | 발급일 | 70/70 → 70/70 | 70/70 → 70/70 |
| own | 사업장명칭 | 50/70 → 50/70 | 50/70 → 50/70 |
| own | 생년월일 | 55/70 → 55/70 | 55/70 → 55/70 |
| own | 성명 | 55/70 → 55/70 | 55/70 → 55/70 |
| own | 용도구분 | 50/70 → 50/70 | 50/70 → 50/70 |
| own | 월별고지금액 | 0/70 → 0/70 | 0/70 → 0/70 |
| own | 월별장기요양보험료 | 0/70 → 0/70 | 0/70 → 0/70 |
| own | 장기요양보험료 | 6/70 → 6/70 | 6/70 → 6/70 |
| own | 조회기간 | 50/70 → 50/70 | 50/70 → 50/70 |
| reference | 건강보험료 | 55/65 → 55/65 | 55/65 → 55/65 |
| reference | 납부자번호 | 60/65 → 60/65 | 60/65 → 60/65 |
| reference | 납부총액 | 60/65 → 60/65 | 60/65 → 60/65 |
| reference | 문서확인번호 | 60/65 → 60/65 | 60/65 → 60/65 |
| reference | 발급일 | 65/65 → 65/65 | 65/65 → 65/65 |
| reference | 사업장명칭 | 60/65 → 60/65 | 60/65 → 60/65 |
| reference | 생년월일 | 60/65 → 60/65 | 60/65 → 60/65 |
| reference | 성명 | 60/65 → 60/65 | 60/65 → 60/65 |
| reference | 용도구분 | 60/65 → 60/65 | 60/65 → 60/65 |
| reference | 월별고지금액 | 55/65 → 55/65 | 55/65 → 55/65 |
| reference | 월별장기요양보험료 | 55/65 → 55/65 | 55/65 → 55/65 |
| reference | 장기요양보험료 | 55/65 → 55/65 | 55/65 → 55/65 |
| reference | 조회기간 | 60/65 → 60/65 | 60/65 → 60/65 |
