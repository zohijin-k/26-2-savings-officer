import assert from 'node:assert/strict'
import test from 'node:test'
import { pdfLoadError } from '../src/pages/officer/pdf-error.ts'

test('PDF authorization, absence, network and decoding failures have distinct safe copy', () => {
  const cases: [unknown, string][] = [
    [{ status: 401 }, '로그인 시간이 끝났습니다.'],
    [{ status: 403 }, '열람할 권한이 없습니다.'],
    [{ status: 404 }, '서류를 찾을 수 없습니다.'],
    [{ status: 0 }, '네트워크 연결'],
    [new TypeError('private URL'), '네트워크 연결'],
    [{ name: 'UnknownErrorException' }, '네트워크 연결'],
    [{ status: 500 }, '잠시 후'],
    [{ name: 'InvalidPDFException' }, 'PDF를 표시하지 못했습니다.'],
    [null, 'PDF를 표시하지 못했습니다.'],
  ]
  for (const [error, copy] of cases) {
    const result = pdfLoadError(error)
    assert.ok(result.message.includes(copy))
    assert.ok(!result.message.includes('private URL'))
  }
})
