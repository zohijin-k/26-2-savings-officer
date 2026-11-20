import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

/**
 * pdf.js 보조 자원(wasm 디코더·CMap·표준 글꼴)을 `/pdfjs/<폴더>/`로 내보낸다.
 *
 * 실제 발급 서류(정부24·건보공단 PDF)는 스캔 이미지를 JBIG2로 압축한 경우가 많다.
 * pdf.js v5는 JBIG2/JPEG2000을 wasm으로 디코드하므로 `wasmUrl`이 없으면 이미지를
 * 못 풀고 흰 페이지만 그린다. 그래서 개발 서버에서는 node_modules에서 바로 서빙하고,
 * 빌드 때는 같은 경로로 파일을 내보낸다.
 */
const PDFJS_DIRS = ['wasm', 'cmaps', 'standard_fonts']
const PDFJS_ROOT = resolve(__dirname, 'node_modules/pdfjs-dist')

const MIME: Record<string, string> = {
  '.wasm': 'application/wasm',
  '.js': 'text/javascript',
  '.bcmap': 'application/octet-stream',
  '.pfb': 'application/octet-stream',
  '.ttf': 'font/ttf',
}

function pdfjsAssets(): Plugin {
  return {
    name: 'pdfjs-assets',
    configureServer(server) {
      server.middlewares.use('/pdfjs', (req, res, next) => {
        const [dir, file] = decodeURIComponent((req.url ?? '').split('?')[0]).replace(/^\//, '').split('/')
        if (!PDFJS_DIRS.includes(dir) || !file || file.includes('..')) return next()
        const path = join(PDFJS_ROOT, dir, file)
        if (!existsSync(path)) return next()
        const ext = file.slice(file.lastIndexOf('.'))
        res.setHeader('Content-Type', MIME[ext] ?? 'application/octet-stream')
        res.end(readFileSync(path))
      })
    },
    generateBundle() {
      for (const dir of PDFJS_DIRS) {
        for (const file of readdirSync(join(PDFJS_ROOT, dir))) {
          if (file.startsWith('LICENSE')) continue
          this.emitFile({
            type: 'asset',
            fileName: `pdfjs/${dir}/${file}`,
            source: readFileSync(join(PDFJS_ROOT, dir, file)),
          })
        }
      }
    },
  }
}

export default defineConfig({
  plugins: [react(), pdfjsAssets()],
  server: {
    // 백엔드는 8000. 프론트에서 /api 를 그대로 부르면 프록시된다.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
