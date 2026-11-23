import assert from 'node:assert/strict'
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import test from 'node:test'
import { build, createServer } from 'vite'

test('PDF.js auxiliary resources retain the exact distribution notices in builds and development', async () => {
  const root = resolve('node_modules/pdfjs-dist')
  const paths = ['LICENSE']
  for (const dir of ['wasm', 'cmaps', 'standard_fonts']) {
    for (const file of await readdir(join(root, dir))) paths.push(`${dir}/${file}`)
  }
  assert.equal(JSON.parse(await readFile(join(root, 'package.json'), 'utf8')).version, '5.7.284')
  assert.equal(paths.filter(path => /(^|\/)LICENSE/.test(path)).length, 10)
  const output = await mkdtemp(join(tmpdir(), 'pdfjs-notices-'))
  let server: Awaited<ReturnType<typeof createServer>> | undefined
  try {
    const entry = join(output, 'entry.js')
    await writeFile(entry, 'export {}\n')
    await build({ build: { outDir: join(output, 'dist'), copyPublicDir: false, rolldownOptions: { input: entry } }, logLevel: 'error' })
    for (const path of paths) {
      assert.deepEqual(await readFile(join(output, 'dist', 'pdfjs', path)), await readFile(join(root, path)), `build: ${path}`)
    }
    server = await createServer({ server: { host: '127.0.0.1', port: 0 }, logLevel: 'error' })
    await server.listen()
    const address = server.httpServer!.address()
    assert(address && typeof address !== 'string')
    for (const path of paths.filter(path => /(^|\/)LICENSE/.test(path))) {
      const response = await fetch(`http://127.0.0.1:${address.port}/pdfjs/${path}`)
      assert.equal(response.status, 200, path)
      assert.deepEqual(Buffer.from(await response.arrayBuffer()), await readFile(join(root, path)), `HTTP: ${path}`)
    }
  } finally {
    await server?.close()
    await rm(output, { recursive: true, force: true })
  }
})
