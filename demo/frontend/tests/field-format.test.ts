import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { checkPhrase, fieldLabel, formatField, plainText, reasonTitle } from '../src/pages/officer/field-format.ts'

test('reason codes never reach the officer: Korean title only, codes stripped from sentences', () => {
  assert.equal(reasonTitle({ code: 'REQUIRED_FIELD_UNREADABLE', title: '필수 항목 판독 안 됨' }), '필수 항목 판독 안 됨')
  assert.equal(reasonTitle({ code: 'REQUIRED_FIELD_UNREADABLE' }), null)
  assert.equal(reasonTitle({ code: 'NEW_CODE', title: 'NEW_CODE' }), null)
  assert.equal(plainText('REQUIRED_FIELD_UNREADABLE 건강보험 자격득실확인서 (LOW_OCR_CONFIDENCE) 확인'), '건강보험 자격득실확인서 확인')
})

test('reading warnings split into one sentence per line without duplicates', () => {
  assert.deepEqual(formatField('판독경고', '월별 고지금액 합계가 표의 합계와 맞지 않습니다. 월별 납부금액 합계가 표의 납부총액과 맞지 않아 담당자 확인이 필요합니다. 월별 고지금액 합계가 표의 합계와 맞지 않습니다.'), {
    kind: 'list', items: ['월별 고지금액 합계가 표의 합계와 맞지 않습니다.', '월별 납부금액 합계가 표의 납부총액과 맞지 않아 담당자 확인이 필요합니다.'],
  })
  assert.deepEqual(formatField('판독경고', '자격확인 통보서의 필수 정보 또는 표 구조를 완전히 확인하지 못했습니다.'),
    { kind: 'text', text: '자격확인 통보서의 필수 정보 또는 표 구조를 완전히 확인하지 못했습니다.' })
  assert.equal(fieldLabel('판독경고'), '판독 시 주의할 점')
})

test('insurance maps become readable label/value rows, not JSON text', () => {
  const view = formatField('보험별가입자종별', '{"국민연금": "사업장가입자", "건강보험": "직장가입자", "산재보험": "사업장가입자", "고용보험": "사업장가입자"}')
  assert.deepEqual(view, { kind: 'pairs', rows: [
    ['국민연금', '사업장가입자'], ['건강보험', '직장가입자'], ['산재보험', '사업장가입자'], ['고용보험', '사업장가입자'],
  ] })
  assert.deepEqual(formatField('보험별가입여부', '{"국민연금":true,"고용보험":false}'),
    { kind: 'pairs', rows: [['국민연금', '가입'], ['고용보험', '미가입']] })
})

test('monthly amounts become a month/won table sorted by month', () => {
  assert.deepEqual(formatField('월별고지금액', '{"2025-11":"83920","2025-10":"200000"}'), {
    kind: 'table', head: ['월', '금액'], rows: [['2025년 10월', '200,000원'], ['2025년 11월', '83,920원']],
  })
})

test('enrolment rows drop bbox and confidence', () => {
  const view = formatField('가입내역', JSON.stringify([{ 보험: '국민연금', 성명: '가상', 가입자종별: '사업장가입자', 상태: '가입',
    자격취득일: '2025-09-05', 자격취득일신뢰도: 0.99, 사업장명칭: '가상기업', bbox: { page: 0 } }]))
  assert.deepEqual(view, { kind: 'table', head: ['보험', '가입자 종별', '상태', '자격취득일', '사업장'],
    rows: [['국민연금', '사업장가입자', '가입', '2025-09-05', '가상기업']] })
})

test('verification payloads read as sentences with Korean labels', () => {
  assert.deepEqual(formatField('주소날짜검증자료', '{"status": "UNDETERMINED", "confidence": 0.0}'),
    { kind: 'text', text: '판단 불가 (원본 확인 필요)' })
  assert.deepEqual(formatField('쪽표기자료', '{"markers": [[1, 2], [2, 2]], "confidence": 0.99}'), { kind: 'text', text: '1/2쪽, 2/2쪽' })
  assert.deepEqual(formatField('일용근로선택자료', '{"version":1,"status":"COMPLETE","copies":[{"status":"READABLE","total":9,"selected":9,"confidence":1.0},{"status":"READABLE","total":9,"selected":9,"confidence":1.0}],"copies_consistent":true}'),
    { kind: 'pairs', rows: [['결과', '모든 근로 내역이 선택됨'], ['사본 1', '9건 중 9건 선택'], ['사본 2', '9건 중 9건 선택'], ['사본 내용 일치', '예']] })
  assert.equal(fieldLabel('자격이력자료'), '건강보험 자격 이력')
  assert.equal(fieldLabel('성명'), '성명')
})

test('household, payment table, totals and attachments read as tables or sentences', () => {
  assert.deepEqual(formatField('가구원목록', '[{"성명":"가상가","생년월일":"1999-01-01","자격취득일":"2020-01-01","자격상실일":""}]'), {
    kind: 'table', head: ['성명', '생년월일', '자격취득일', '자격상실일'], rows: [['가상가', '1999-01-01', '2020-01-01', '유지 중']], notes: ['총 1명'],
  })
  const paid = formatField('월별납부내역', JSON.stringify([{ 월: '2025-10',
    고지: { 건강보험료: '83920', 장기요양보험료: '10860', '보수외소득월액(건강)': '0', '보수외소득월액(요양)': '0' },
    납부: { 건강보험료: '83920', 장기요양보험료: '10860', '보수외소득월액(건강)': '0', '보수외소득월액(요양)': '0' } }]))
  assert.deepEqual(paid, { kind: 'table', head: ['월', '건강보험료 (고지 / 납부)', '장기요양보험료 (고지 / 납부)'],
    rows: [['2025년 10월', '83,920원 / 83,920원', '10,860원 / 10,860원']], notes: ['모든 달이 0원인 항목은 생략했습니다.'] })
  assert.deepEqual(formatField('합계자료', '["100","20","0",null,"100","20","0",null]'), { kind: 'table', head: ['항목', '고지 합계', '납부 합계'],
    rows: [['건강보험료', '100원', '100원'], ['장기요양보험료', '20원', '20원'], ['보수외소득월액(건강)', '0원', '0원'], ['보수외소득월액(요양)', '–', '–']] })
  assert.deepEqual(formatField('추가첨부쪽', '[3, 4]'), { kind: 'text', text: '3쪽, 4쪽 (본 서류 표와 별개인 쪽)' })
  assert.deepEqual(formatField('과거주소미포함의심', 'true'), { kind: 'text', text: '예' })
})

test('failed check names become Korean sentences, including patterned names', () => {
  const view = formatField('판독검증실패', 'form_recognized, 성명_consistent, 생년월일_required, daily_2_query_period, payment_column_6_sum, brand_new_check')
  assert.deepEqual(view, { kind: 'list', items: [
    '서식 인식 확인 안 됨',
    '성명 표기 일치 확인 안 됨',
    '필수 항목을 읽지 못함: 생년월일',
    '사본 2: 조회기간 판독 확인 안 됨',
    '납부 장기요양보험료 열 합계 확인 안 됨',
    '그 밖의 자동 검증 확인 안 됨: 1건',
  ] })
  assert.equal(fieldLabel('판독검증실패'), '확인되지 않은 검증 항목')
  assert.deepEqual(formatField('주소이력불확실사유', 'NUMBER_GAP,EMPTY_PAGE'),
    { kind: 'list', items: ['주소 이력 순번이 중간에 빠져 있음', '이력 줄을 하나도 읽지 못한 쪽이 있음'] })
  assert.deepEqual(formatField('구성머리글불완전사유', 'FRAGMENT'), { kind: 'list', items: ['보수외소득월액 머리글 글자 일부가 다르게 읽힘'] })
})

test('every validation name in the engine source has a Korean phrase', () => {
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const sources = ['engine_v2/extractors', 'demo/backend/ocr'].flatMap((dir) =>
    readdirSync(join(root, dir)).filter((file) => file.endsWith('.py')).map((file) => readFileSync(join(root, dir, file), 'utf8')))
  const names = new Set<string>()
  for (const source of sources) for (const match of source.matchAll(/Validation\(\s*(f?)["']([^"']+)["']/g)) {
    // f-string 자리표시자는 실제로 들어올 값의 예로 바꿔 본다.
    names.add(match[1] ? match[2].replace('{number}', '1').replace('{column}', '1').replace('{label}', '성명').replace('{key}', '상호') : match[2])
  }
  assert.ok(names.size > 80, `검증 이름을 ${names.size}개만 찾았습니다`)
  const missing = [...names].filter((name) => checkPhrase(name) === null)
  assert.deepEqual(missing, [])
})

test('no field ever renders JSON syntax, even unknown nested payloads', () => {
  const payloads: Array<[string, string]> = [
    ['모르는자료', '{"version":1,"status":"UNREADABLE","rows":[{"month":"2025-01","bbox":{"page":0}}],"extra":{"a":[1,{"b":2}]}}'],
    ['모르는목록', '[{"x":{"y":[1,2]}},{"z":null}]'],
    ['고지월검증자료', '{"status":"READABLE"}'],
    ['납부표완전성자료', '{"version":1}'],
    ['일용근로내역자료', '{"rows":[{"month":"2025-01","work_dates":[1,2]}]}'],
    ['가입내역', '[{"보험":"국민연금","bbox":{"page":0}}]'],
  ]
  for (const [key, raw] of payloads) {
    const text = JSON.stringify(formatField(key, raw))
    const strings = [...text.matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((match) => JSON.parse(`"${match[1]}"`) as string)
    for (const shown of strings) assert.doesNotMatch(shown, /[{}[\]]|":|^[A-Z_]{4,}$/, `${key} → ${shown}`)
  }
})

test('lists, periods, empties, plain text and technical fields', () => {
  assert.deepEqual(formatField('조회기간', '["2024-08","2026-03"]'), { kind: 'text', text: '2024년 8월 ~ 2026년 3월' })
  assert.deepEqual(formatField('발급번호목록', '["A","B"]'), { kind: 'list', items: ['A', 'B'] })
  assert.deepEqual(formatField('사업장명칭목록', '[]'), { kind: 'text', text: '없음' })
  assert.deepEqual(formatField('국민연금 사업장명칭', ''), { kind: 'text', text: '읽은 값 없음' })
  assert.deepEqual(formatField('성명', '홍길동'), { kind: 'text', text: '홍길동' })
  assert.deepEqual(formatField('원본이미지크기', '[{"page":0,"width":1,"height":1}]'), { kind: 'hidden' })
  assert.deepEqual(formatField('메모', '{깨진 값'), { kind: 'text', text: '{깨진 값' })
})
