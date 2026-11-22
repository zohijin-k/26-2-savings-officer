import { test } from 'node:test'
import assert from 'node:assert/strict'
import { fitDocumentScale } from '../src/pages/officer/viewer-layout.ts'

test('fits the widest page of mixed sizes at narrow widths', () => {
  const sizes = [{ width: 595, height: 842 }, { width: 842, height: 595 }]
  const scale = fitDocumentScale(sizes, 264, 0)
  assert.equal(scale * 842, 264)
  assert.ok(scale * 595 < 264)
  assert.ok(scale * 842 * 2 > 264, 'zoom remains available within the stage')
})
test('fits rotated geometry, large image originals, and preserves small originals', () => {
  assert.equal(fitDocumentScale([{ width: 600, height: 1200 }], 300, 90), 0.25)
  assert.equal(fitDocumentScale([{ width: 600, height: 1200 }], 300, 270), 0.25)
  assert.equal(fitDocumentScale([{ width: 1240, height: 1754 }], 310, 180), 0.25)
  assert.equal(fitDocumentScale([{ width: 200, height: 300 }], 700, 0), 1)
})
test('loading and zero-sized containers have a finite fallback', () => {
  assert.equal(fitDocumentScale([], 300, 0), 1)
  assert.equal(fitDocumentScale([{ width: 595, height: 842 }], 0, 0), 1)
})
