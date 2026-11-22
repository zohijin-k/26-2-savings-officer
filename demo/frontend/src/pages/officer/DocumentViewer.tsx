/**
 * 원본 뷰어 — 분할 심사 뷰의 좌측 55% (R4.1/R4.2/R4.3).
 *
 * 이 컴포넌트의 금칙은 하나다: **원본을 로컬에 저장하는 경로를 만들지 않는다.**
 * pdf.js가 `/api/files/{id}`(항상 `inline`)를 그대로 읽어 캔버스에 그린다. 저장
 * 버튼도, blob 링크도 없다. 담당자가 심사 1건을 처리하는 동안 파일이 개인 PC로
 * 내려가는 일이 없어야 보관·파기 책임이 옮겨가지 않는다.
 *
 * PDF는 모든 쪽을 세로로 이어 붙여 스크롤로 넘겨 본다. 쪽마다 자리(크기)는 열자마자
 * 잡아두고, 실제 캔버스는 화면 근처에 온 쪽만 그린다 — 수십 쪽짜리 서류를 열어도
 * 캔버스 메모리가 쪽 수만큼 불어나지 않게 하기 위해서다. 툴바의 ‹ › 는 해당 쪽으로
 * 스크롤하고, 쪽 번호는 스크롤 위치를 따라간다.
 *
 * bbox 하이라이트는 판독값 좌표를 화면 좌표로 옮겨 얹는다. 좌표계는 PyMuPDF와
 * 같은 **좌상단 원점 PDF 포인트**이므로 y를 뒤집지 않는다. 회전은 오버레이에서
 * 같이 돌린다 — 원본을 돌려놓고 근거를 클릭해도 자리가 맞아야 한다.
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode, RefObject } from 'react'
import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

import type { BBox, OfficerDocument } from '../../api.ts'
import { officerSessionResponse } from '../../officer-session.ts'
import { pdfLoadError } from './pdf-error.ts'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

type Rotation = 0 | 90 | 180 | 270

interface Size {
  width: number
  height: number
}

const ZOOM_STEPS = [0.6, 0.8, 1, 1.25, 1.5, 2, 2.5, 3]
/** `.viewer__stage`의 padding과 같아야 쪽 이동 시 위 여백이 맞는다. */
const STAGE_PADDING = 12

type ViewerDocument = Pick<OfficerDocument, 'file_url' | 'file_name' | 'file_format' | 'label'>

interface Props {
  doc: ViewerDocument
  /** 심사표 항목 클릭이 채우는 하이라이트 위치. */
  highlight: BBox | null
  /** 하이라이트 옆에 띄울 설명 (어느 항목의 근거인지). */
  highlightLabel?: string
}

interface Box {
  left: number
  top: number
  width: number
  height: number
}

/** 열린 PDF와 쪽별 원본 크기(배율 1, 회전 0). url로 어느 서류의 것인지 구분한다. */
interface LoadedPdf {
  url: string
  pdf: pdfjs.PDFDocumentProxy
  sizes: Size[]
}

/** 좌상단 원점 좌표 → 회전·배율이 적용된 화면 좌표. */
function place(
  bbox: BBox,
  pageWidth: number,
  pageHeight: number,
  scale: number,
  rotation: Rotation,
): Box {
  const w = (bbox.x1 - bbox.x0) * scale
  const h = (bbox.y1 - bbox.y0) * scale
  switch (rotation) {
    case 90:
      return { left: (pageHeight - bbox.y1) * scale, top: bbox.x0 * scale, width: h, height: w }
    case 180:
      return {
        left: (pageWidth - bbox.x1) * scale,
        top: (pageHeight - bbox.y1) * scale,
        width: w,
        height: h,
      }
    case 270:
      return { left: bbox.y0 * scale, top: (pageWidth - bbox.x1) * scale, width: h, height: w }
    default:
      return { left: bbox.x0 * scale, top: bbox.y0 * scale, width: w, height: h }
  }
}

/** 회전·배율을 적용한 화면상 쪽 크기 (pdf.js 뷰포트와 같은 내림). */
function displaySize(size: Size, scale: number, rotation: Rotation): Size {
  const turned = rotation === 90 || rotation === 270
  const w = (turned ? size.height : size.width) * scale
  const h = (turned ? size.width : size.height) * scale
  return { width: Math.floor(w), height: Math.floor(h) }
}

export default function DocumentViewer({ doc, highlight, highlightLabel }: Props) {
  const stageRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<(HTMLDivElement | null)[]>([])
  const markRef = useRef<HTMLDivElement>(null)
  /** 배율·회전을 바꿔도 보던 자리를 유지하려고 스크롤 비율을 들고 있는다. */
  const scrollRatioRef = useRef(0)
  const scrollRafRef = useRef(0)

  const [loaded, setLoaded] = useState<LoadedPdf | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [zoomIndex, setZoomIndex] = useState(2)
  const [rotation, setRotation] = useState<Rotation>(0)
  const [imageSize, setImageSize] = useState<Size>({ width: 0, height: 0 })
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)

  const scale = ZOOM_STEPS[zoomIndex]
  const isPdf = doc.file_format === 'pdf'
  // 탭을 바꾼 직후엔 이전 서류의 PDF가 아직 상태에 남아 있다. url이 다르면 없는 셈 친다.
  const pdfDoc = isPdf && loaded?.url === doc.file_url ? loaded : null
  const pageCount = pdfDoc?.sizes.length ?? 1

  // 서류 탭이 바뀌면 배율·회전은 유지하고 쪽 표시만 1쪽으로 되돌린다.
  // effect가 아니라 렌더 중에 조정해 이전 서류 상태로 한 번 그려지는 깜빡임을 막는다.
  const [prevDocUrl, setPrevDocUrl] = useState(doc.file_url)
  if (prevDocUrl !== doc.file_url) {
    setPrevDocUrl(doc.file_url)
    setCurrentPage(1)
    setError('')
  }

  // --- PDF 열기. 탭이 바뀔 때마다 이전 문서를 닫아 워커 메모리를 정리한다.
  useEffect(() => {
    if (!isPdf) return
    let cancelled = false
    setError('')
    setLoaded(null)
    // 실제 발급 서류는 JBIG2 스캔 이미지가 많아 wasm 디코더가 없으면 흰 페이지가
    // 된다. 경로는 vite.config.ts의 pdfjsAssets 플러그인이 제공한다.
    const base = import.meta.env.BASE_URL
    const url = doc.file_url
    const task = pdfjs.getDocument({
      url,
      withCredentials: true,
      wasmUrl: `${base}pdfjs/wasm/`,
      cMapUrl: `${base}pdfjs/cmaps/`,
      cMapPacked: true,
      standardFontDataUrl: `${base}pdfjs/standard_fonts/`,
    })
    task.promise
      .then(async (pdf) => {
        // 스크롤 영역 높이를 처음부터 맞추려고 모든 쪽의 크기를 먼저 읽는다.
        // 크기만 읽는 것이라 그리기보다 훨씬 가볍다.
        const sizes = await Promise.all(
          Array.from({ length: pdf.numPages }, async (_, i) => {
            const page = await pdf.getPage(i + 1)
            const vp = page.getViewport({ scale: 1, rotation: 0 })
            return { width: vp.width, height: vp.height }
          }),
        )
        if (cancelled) return
        setLoaded({ url, pdf, sizes })
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          const failure = pdfLoadError(e)
          if (failure.status !== null) officerSessionResponse(url, { status: failure.status })
          setError(failure.message)
        }
      })
    return () => {
      cancelled = true
      void task.destroy()
    }
  }, [doc.file_url, isPdf, retry])

  // --- 탭이 바뀌면 맨 위부터 본다.
  useLayoutEffect(() => {
    const stage = stageRef.current
    if (stage) stage.scrollTop = 0
    scrollRatioRef.current = 0
  }, [doc.file_url])

  // --- 배율·회전이 바뀌면 보던 위치를 같은 비율로 되살린다.
  //     근거 하이라이트가 떠 있으면 아래 effect가 하이라이트로 옮겨주므로 건너뛴다.
  const hasHighlight = highlight !== null
  useLayoutEffect(() => {
    const stage = stageRef.current
    if (!stage || hasHighlight) return
    stage.scrollTop = scrollRatioRef.current * stage.scrollHeight
  }, [scale, rotation, hasHighlight])

  // --- 스크롤 위치로 현재 쪽 번호를 계산한다 (프레임당 1번).
  const onScroll = useCallback(() => {
    if (scrollRafRef.current) return
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = 0
      const stage = stageRef.current
      if (!stage) return
      scrollRatioRef.current = stage.scrollHeight ? stage.scrollTop / stage.scrollHeight : 0
      const pages = pageRefs.current
      if (pages.length === 0) return
      // 맨 끝까지 내렸으면 마지막 쪽이 짧아도 마지막 쪽으로 친다.
      if (stage.scrollTop + stage.clientHeight >= stage.scrollHeight - 2) {
        setCurrentPage(pages.length)
        return
      }
      // 화면 위쪽 40% 선을 넘어선 마지막 쪽을 '지금 보는 쪽'으로 본다.
      const line = stage.getBoundingClientRect().top + stage.clientHeight * 0.4
      let n = 1
      pages.forEach((el, i) => {
        if (el && el.getBoundingClientRect().top <= line) n = i + 1
      })
      setCurrentPage(n)
    })
  }, [])

  useEffect(() => () => cancelAnimationFrame(scrollRafRef.current), [])

  const goToPage = (n: number) => {
    const stage = stageRef.current
    const el = pageRefs.current[n - 1]
    if (!stage || !el) return
    const offset = el.getBoundingClientRect().top - stage.getBoundingClientRect().top
    stage.scrollTop += offset - STAGE_PADDING
    setCurrentPage(n)
  }

  // --- 하이라이트: 근거가 있는 쪽의 그 자리로 스크롤한다 (R4.3).
  //     쪽 자리는 크기만으로 잡히므로 캔버스가 다 그려지기 전에도 위치가 맞다.
  const highlightReady = isPdf ? pdfDoc !== null : imageSize.width > 0
  useEffect(() => {
    if (!highlight || !highlightReady) return
    markRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [highlight, highlightReady, scale, rotation])

  const highlightPage = highlight ? Math.min(highlight.page, pageCount - 1) : -1

  const renderMark = (box: Box) => (
    <div
      ref={markRef}
      className="viewer__mark"
      style={{
        left: `${box.left}px`,
        top: `${box.top}px`,
        width: `${box.width}px`,
        height: `${box.height}px`,
      }}
    >
      {highlightLabel && <span className="viewer__mark-tag">{highlightLabel}</span>}
    </div>
  )

  // 이전 서류가 더 길었으면 남은 쪽 참조를 잘라 현재 쪽 계산에 끼지 않게 한다.
  useLayoutEffect(() => {
    pageRefs.current.length = pdfDoc ? pdfDoc.sizes.length : 0
  }, [pdfDoc])

  return (
    <div className="viewer">
      <div className="viewer__bar">
        <span className="viewer__name">{doc.file_name}</span>
        {isPdf && pageCount > 1 && (
          <span className="viewer__pages">
            <button
              type="button"
              onClick={() => goToPage(Math.max(1, currentPage - 1))}
              disabled={currentPage <= 1}
              aria-label="이전 쪽"
            >
              ‹
            </button>
            {currentPage} / {pageCount}
            <button
              type="button"
              onClick={() => goToPage(Math.min(pageCount, currentPage + 1))}
              disabled={currentPage >= pageCount}
              aria-label="다음 쪽"
            >
              ›
            </button>
          </span>
        )}
        <span className="viewer__spacer" />
        <button
          type="button"
          onClick={() => setZoomIndex((i) => Math.max(0, i - 1))}
          aria-label="축소"
        >
          −
        </button>
        <span className="viewer__zoom">{Math.round(scale * 100)}%</span>
        <button
          type="button"
          onClick={() => setZoomIndex((i) => Math.min(ZOOM_STEPS.length - 1, i + 1))}
          aria-label="확대"
        >
          ＋
        </button>
        <button
          type="button"
          onClick={() => setRotation((r) => (((r + 90) % 360) as Rotation))}
          aria-label="회전"
        >
          ↻
        </button>
        {/* 저장 버튼을 두지 않는 것이 이 화면의 요구사항이다 (R4.1). */}
        <span className="viewer__inline-badge" title="원본은 브라우저 안에서만 열립니다">
          브라우저 인라인 열람
        </span>
      </div>

      {error && <p className="viewer__error" role="alert">{error}{' '}
        <button type="button" className="btn btn--sm" onClick={() => setRetry((value) => value + 1)}>다시 시도</button>
      </p>}
      {isPdf && !pdfDoc && !error && <p role="status">서류를 불러오는 중입니다.</p>}

      <div className="viewer__stage" ref={stageRef} onScroll={onScroll}>
        {isPdf ? (
          <div className="viewer__doc">
            {pdfDoc?.sizes.map((size, i) => (
              <PdfPage
                key={`${pdfDoc.url}#${i}`}
                pdf={pdfDoc.pdf}
                pageNo={i + 1}
                size={size}
                scale={scale}
                rotation={rotation}
                rootRef={stageRef}
                pageRef={(el) => {
                  pageRefs.current[i] = el
                }}
                onError={setError}
              >
                {highlight &&
                  i === highlightPage &&
                  renderMark(place(highlight, size.width, size.height, scale, rotation))}
              </PdfPage>
            ))}
          </div>
        ) : (
          <div className="viewer__paper">
            <ImagePage doc={doc} scale={scale} rotation={rotation} onSize={setImageSize} />
            {highlight &&
              imageSize.width > 0 &&
              renderMark(place(highlight, imageSize.width, imageSize.height, scale, rotation))}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * PDF 한 쪽. 자리(크기)는 항상 차지하고, 캔버스는 스크롤 영역 근처에 왔을 때만 그린다.
 *
 * 다시 그릴 때마다 새 캔버스에 그린 뒤 다 그려지면 갈아 끼운다. 그래서 배율을 바꾸는
 * 동안에도 이전 그림이 늘어난 채로 남아 있어 흰 화면이 번쩍이지 않고, pdf.js의
 * "같은 캔버스에 동시 render 금지" 제약에도 걸리지 않는다.
 */
function PdfPage({
  pdf,
  pageNo,
  size,
  scale,
  rotation,
  rootRef,
  pageRef,
  onError,
  children,
}: {
  pdf: pdfjs.PDFDocumentProxy
  pageNo: number
  size: Size
  scale: number
  rotation: Rotation
  rootRef: RefObject<HTMLDivElement | null>
  pageRef: (el: HTMLDivElement | null) => void
  onError: (message: string) => void
  children?: ReactNode
}) {
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const holderRef = useRef<HTMLDivElement>(null)
  const [near, setNear] = useState(false)

  // 화면 위아래로 한 화면 반 이내에 들어오면 그린다.
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => setNear(entry.isIntersecting),
      { root: rootRef.current, rootMargin: '150% 0px' },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [rootRef])

  useEffect(() => {
    const holder = holderRef.current
    if (!holder) return
    if (!near) {
      // 멀어진 쪽은 캔버스를 비워 메모리를 돌려준다.
      for (const c of holder.querySelectorAll('canvas')) {
        c.width = 0
        c.height = 0
      }
      holder.replaceChildren()
      return
    }
    let cancelled = false
    let task: pdfjs.RenderTask | null = null
    const canvas = document.createElement('canvas')
    canvas.className = 'viewer__canvas'

    const draw = async () => {
      const page = await pdf.getPage(pageNo)
      if (cancelled) return
      const viewport = page.getViewport({ scale, rotation })
      // 캔버스 픽셀을 CSS 크기와 같게 잡으면 72dpi로 그려진다. 고배율 모니터에선
      // 브라우저가 그걸 늘려 흐려지고, 300dpi 스캔 원본의 잔글씨도 뭉개진다.
      // 그래서 기기 배율과 최소 2배 중 큰 값으로 그리고 CSS 크기만 화면에 맞춘다.
      // 브라우저 캔버스 한도를 넘지 않도록 총 픽셀 수는 제한한다.
      const MAX_PIXELS = 16_000_000
      let outputScale = Math.max(window.devicePixelRatio || 1, 2)
      const pixels = viewport.width * viewport.height * outputScale * outputScale
      if (pixels > MAX_PIXELS) outputScale *= Math.sqrt(MAX_PIXELS / pixels)
      canvas.width = Math.floor(viewport.width * outputScale)
      canvas.height = Math.floor(viewport.height * outputScale)
      task = page.render({
        canvas,
        viewport,
        transform: outputScale === 1 ? undefined : [outputScale, 0, 0, outputScale, 0, 0],
      })
      await task.promise
      if (cancelled) return
      for (const old of holder.querySelectorAll('canvas')) {
        old.width = 0
        old.height = 0
      }
      holder.replaceChildren(canvas)
    }

    draw().catch(() => {
      if (cancelled) return
      onError('PDF를 표시하지 못했습니다. 다시 시도해 주세요.')
    })
    return () => {
      cancelled = true
      task?.cancel()
    }
  }, [near, pdf, pageNo, scale, rotation, onError])

  const shown = displaySize(size, scale, rotation)
  return (
    <div
      ref={(el) => {
        wrapRef.current = el
        pageRef(el)
      }}
      className="viewer__page"
      style={{ width: `${shown.width}px`, height: `${shown.height}px` }}
      aria-label={`${pageNo}쪽`}
    >
      <div ref={holderRef} className="viewer__page-canvas" />
      {children}
    </div>
  )
}

/** 스캔 이미지(jpg/png)는 픽셀 좌표를 그대로 쓴다. */
function ImagePage({
  doc,
  scale,
  rotation,
  onSize,
}: {
  doc: ViewerDocument
  scale: number
  rotation: Rotation
  onSize: (size: Size) => void
}) {
  return (
    <img
      className="viewer__image"
      src={doc.file_url}
      alt={`${doc.label} 원본`}
      style={{ transform: `rotate(${rotation}deg) scale(${scale})` }}
      onLoad={(e) =>
        onSize({
          width: e.currentTarget.naturalWidth,
          height: e.currentTarget.naturalHeight,
        })
      }
    />
  )
}
