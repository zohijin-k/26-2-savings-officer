# PDF.js distribution notices

The npm lock resolves `pdfjs-dist` 5.7.284. The package root `LICENSE` contains Apache License 2.0. Auxiliary resources carry additional upstream copyright and license text. The build copies that text verbatim from the installed, lock-verified package; it does not apply the project license to third-party files.

The Vite plugin emits and serves these ten notice paths:

- `/pdfjs/LICENSE`
- `/pdfjs/cmaps/LICENSE`
- `/pdfjs/standard_fonts/LICENSE_FOXIT`
- `/pdfjs/standard_fonts/LICENSE_LIBERATION`
- `/pdfjs/wasm/LICENSE_JBIG2`
- `/pdfjs/wasm/LICENSE_OPENJPEG`
- `/pdfjs/wasm/LICENSE_PDFJS_JBIG2`
- `/pdfjs/wasm/LICENSE_PDFJS_OPENJPEG`
- `/pdfjs/wasm/LICENSE_PDFJS_QCMS`
- `/pdfjs/wasm/LICENSE_QCMS`

All files in `wasm`, `cmaps` and `standard_fonts` are emitted together, including their notices. The unused `iccs` directory is not distributed by this plugin. The package contains no separate root NOTICE file; no replacement license or notice text is invented. Keep package source/integrity in package-lock.json and review upstream notices whenever upgrading the package.

After `npm ci`, run `npm test`, `npm run lint` and `npm run build`. The PDF.js regression test checks every emitted auxiliary file against the installed package bytes and retrieves all ten notices from a temporary local development server. A full application build also requires the existing institution assets. A source snapshot that intentionally omits unapproved assets is incomplete for that build.

Upstream distribution: https://registry.npmjs.org/pdfjs-dist/-/pdfjs-dist-5.7.284.tgz

This notice repair does not select a license for the application or authorize public source redistribution. PRODUCTION_NOT_READY.
