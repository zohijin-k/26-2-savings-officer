"""주민등록표 초본 추출기 (레퍼런스 구현).

실측 레이아웃 (2026-11-10, 정부24 초본 브라우저 인쇄본, Apple Vision OCR) — 좌표는 페이지 대비 %
  y≈3      문서확인번호 ####-####-####-#####  /  우측 x≈79 쪽번호 "n/N"
  y≈7~10   제목 "주민등록표 ( 초 본 )"  ← 글자가 띄어져 읽힘 → 공백 제거 후 판별
  y≈12.8   발급일 "YYYY년 MM월 DD일" (x≈58)       ← 매 쪽 반복
  y≈14.5   발급기관 "○○○○ ○○시장"
  y≈17.7   성명(x≈23) / 주민등록번호(x≈68)        ← 매 쪽 반복
  표 머리  "번호 | 주소 | 발생일/신고일 | 세대주 및 관계"
  표 본문  한 건이 2줄:  주소(x≈13) 발생일(x≈54) 신고일(x≈68) 세대주·관계(x≈79)
                         순번(x≈9)  주소 상세(x≈13)  변동사유(x≈62~73)
           순번은 윗줄/아랫줄 어디에도 올 수 있음 → 줄이 아니라 '신고일 칸'으로 건을 나눈다
           "[...]" 메모 줄 = 도로명주소 전환, 행정구역 변경 안내 → 다음 건에 붙임
  끝       "== 이하 여백 ==" 또는 병역사항, 또는 y≈78 이후 안내문

개인정보 최소화
  - 주민등록번호 원문은 결과에 남기지 않는다. 생년월일과 성별 자리만 쓴다.
  - 병역사항, 담당자 연락처는 읽지 않는다. 첫 쪽의 신청인 성명·생년월일은 본인 대조용으로 읽는다.
"""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime
from statistics import median
from zoneinfo import ZoneInfo

from ..pipeline.layout import Word, group_lines, line_text, normalize, squash
from ..pipeline.ocr import OcrResult
from ..pipeline.preprocess import PageImage
from ..schemas.models import BBox, DocType, ExtractedField, FieldSource

from .format_text import normalize_format_text

# --- 패턴 ---------------------------------------------------------------
ISO_DATE = re.compile(r"(\d{4})\s*[-.]\s*(\d{1,2})\s*[-.]\s*(\d{1,2})")
KOR_DATE = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
APPLICANT_DATE = re.compile(
    r"(\d{4}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}|"
    r"\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일|\d{8})"
)
RRN = re.compile(r"(?<!\d)(\d{6})\s*(?:-\s*|(?=[0-9](?:\s*[\d*]){6}(?![\d*])))([0-9])")
DOC_NO = re.compile(r"\d{4}-\d{4}-\d{4}-\d{4,5}")
PAGE_NO = re.compile(r"^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$")
ISSUER = re.compile(r"(시장|군수|구청장)")

# --- 영역 (페이지 대비 %) — 실측값. 양식이 바뀌면 여기만 고친다 ------------
HEADER_MAX_Y = 16.0
#: Minimum horizontal distance (page-width %) between two header markers of one 2-up sheet.
SHEET_SPREAD = 25.0
#: 쪽마다 되풀이되는 머리 상자(제목·쪽표기·성명·주민등록번호 줄) 아래부터 본문으로 본다.
BODY_TOP_Y = 26.0
#: 본문 영역 글자가 이 수 이하이면 내용 없는 쪽(스캔 잡티 허용).
BLANK_BODY_MAX_CHARS = 3
#: 빈 쪽 판정에서 글자로 세지 않는 것 (11-18 L1 보완): 쪽표기·쪽 번호("2/3", "- 3 -"),
#: 한글·영문·숫자가 아닌 잡티, 쪽 테두리가 글자로 읽힌 한 글자.
_PAGE_MARK_TEXT = re.compile(r"^[\-–—(]*\d{1,2}(?:/\d{1,2})?[\-–—)]*$")
_FRAME_GLYPHS = frozenset("|lI1!/\\")
COL_NO_MAX_X = 11.5
COL_ADDR_MAX_X = 50.0
COL_OCCUR_X = (50.0, 61.0)
COL_REPORT_X = (61.0, 73.0)
COL_REASON_X = (58.0, 77.5)
COL_HOLDER_MIN_X = 77.5
FOOTER_Y = 77.5

SIDO = {
    "전북특별자치도": "전북", "전라북도": "전북",
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원",
    "충청북도": "충북", "충청남도": "충남", "전라남도": "전남",
    "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주", "제주도": "제주",
}


KST = ZoneInfo("Asia/Seoul")


def kst_today() -> date:
    """판정 기준일은 항상 한국 시간. 서버가 UTC면 오전 9시 전 당일 발급 서류가 '미래'로 잘못 판정된다."""
    return datetime.now(KST).date()


# --- 결과 구조 ------------------------------------------------------------
@dataclass
class HistoryEntry:
    no: int | None = None
    address: list[str] = field(default_factory=list)
    occurred: date | None = None      # 발생일
    reported: date | None = None      # 신고일
    reason: list[str] = field(default_factory=list)
    holder: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    page: int = 0
    words: list[Word] = field(default_factory=list)

    @property
    def address_text(self) -> str:
        return " ".join(self.address)

    @property
    def effective(self) -> date | None:
        return self.occurred or self.reported

    @property
    def sido(self) -> str | None:
        s = squash(self.address_text)
        for name, short in SIDO.items():
            if s.startswith(name):
                return short
        return None


@dataclass
class Validation:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ResidentAbstractResult:
    detected_type: DocType
    type_confidence: float
    fields: dict[str, ExtractedField]
    history: list[HistoryEntry]
    validations: list[Validation]
    warnings: list[str] = field(default_factory=list)
    # 미판독(None)과 읽힌 누락을 분리한다. 중복 쪽·서로 다른 총수도 보존한다.
    page_markers: list[tuple[int, int] | None] = field(default_factory=list)
    page_marker_confidence: float = 0.0
    #: Header-band markers per sheet when several pages are printed side by side (S1, held).
    sheet_markers: list[list[tuple[int, int]]] | None = None
    classification_evidence: str = ""
    #: 11-26: 주소 이력 끝 근거 (BLANK_MARKER / NEXT_SECTION / NONE / NA)와 그 끝 표시가 있는 쪽(스캔 순서, 1부터).
    history_end: str = "NA"
    history_end_page: int | None = None
    #: 쪽 수 확인에서 뺀 내용 없는 쪽 수 (page_markers에 들어 있지 않다).
    blank_pages: int = 0
    #: page_markers(또는 sheet_markers)의 각 항목을 읽은 쪽 번호(PageImage.page), 같은 순서 (11-19 D10).
    marker_pages: list[int] = field(default_factory=list)
    #: 주소 이력 순번 상태 (11-18): CONTIGUOUS(1..N 모두), GAP(빠진 번호·1로 시작 안 함·중복),
    #: UNREADABLE(번호 없는 이력이 있어 연속성 확인 불가), NA(이력 없음).
    history_numbers: str = "NA"
    #: 주소 표 머리글은 찾았는데 이력 줄을 0건 읽은 쪽이 있음 (쪽 수에서 뺀 중복 빈 쪽 제외).
    history_empty_page: bool = False
    #: Fixed-vocabulary risks from unread continuation tables; no source values.
    history_table_issues: list[str] = field(default_factory=list)


# --- 유틸 ---------------------------------------------------------------
def _to_date(m: re.Match | None) -> date | None:
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _bbox(words: list[Word], pages: dict[int, PageImage]) -> BBox | None:
    if not words:
        return None
    p = pages[words[0].page]
    x0 = min(w.px[0] for w in words); y0 = min(w.px[1] for w in words)
    x1 = max(w.px[2] for w in words); y1 = max(w.px[3] for w in words)
    a, b = p.px_to_pt(x0, y0)
    c, d = p.px_to_pt(x1, y1)
    return BBox(page=words[0].page, x0=round(a, 1), y0=round(b, 1), x1=round(c, 1), y1=round(d, 1))


INCONSISTENT_CAP = 0.6  # 쪽마다 값이 다르게 읽힘 = 오독 신호 → 자동 부적합 판정에 쓰지 않도록 상한


def _confidence(checks: list[bool], hard_fail: bool = False, consistent: bool = True) -> float:
    """OCR 점수가 아니라 검증 통과율로 신뢰도를 매긴다 (실측: OCR 점수는 정답 여부와 무관)."""
    if hard_fail:
        return 0.2
    if not consistent:
        return min(INCONSISTENT_CAP, round(0.4 + 0.6 * sum(checks) / max(len(checks), 1), 2))
    if not checks:
        return 0.5
    return round(0.4 + 0.6 * sum(checks) / len(checks), 2)


def _birth_from_rrn(front6: str, g: str) -> date | None:
    century = {"1": 1900, "2": 1900, "5": 1900, "6": 1900,
               "3": 2000, "4": 2000, "7": 2000, "8": 2000,
               "9": 1800, "0": 1800}.get(g)
    if century is None:
        return None
    try:
        return date(century + int(front6[:2]), int(front6[2:4]), int(front6[4:6]))
    except ValueError:
        return None


# --- 페이지 단위 파싱 -----------------------------------------------------
def _parse_header(lines: list[list[Word]]) -> dict:
    out: dict = {"title": "", "issue": None, "issue_words": [], "doc_no": None,
                 "page_no": None, "page_confidence": 0.0, "header_markers": [], "doc_nos": set(), "issuer": None, "name": None, "name_words": [],
                 "birth": None, "gender": None, "birth_words": []}
    title_parts = []
    for line in lines:
        y = line[0].cy
        t = line_text(line)
        if y < HEADER_MAX_Y:
            title_parts.append(t)
            if (m := DOC_NO.search(normalize_format_text(t))) and out["doc_no"] is None:
                out["doc_no"] = m.group(0)
            out["doc_nos"].update(DOC_NO.findall(normalize_format_text(t)))
            for w in line:
                if (hm := PAGE_NO.match(w.text)):
                    out["header_markers"].append((w.x0, (int(hm.group(1)), int(hm.group(2))), w.conf))
            for w in line:
                if w.x0 > 70 and (m := PAGE_NO.match(w.text)):
                    out["page_no"] = (int(m.group(1)), int(m.group(2)))
                    out["page_confidence"] = w.conf
            ws = [w for w in line if w.x0 > 50 and KOR_DATE.search(w.text)]
            if ws and out["issue"] is None:
                out["issue"] = _to_date(KOR_DATE.search(ws[0].text))
                out["issue_words"] = ws
            if out["issuer"] is None and any(w.x0 > 55 for w in line) and ISSUER.search(t) and "증명" not in t:
                out["issuer"] = t.strip()
        if y < 26 and "주민등록번호" in squash(t) and (m := RRN.search(normalize_format_text(t))):
            out["birth"] = _birth_from_rrn(m.group(1), m.group(2))
            out["gender"] = m.group(2)
            out["birth_words"] = [w for w in line if RRN.search(normalize_format_text(w.text))]
            nws = [w for w in line if 15 <= w.x0 < 36 and "성명" not in w.text and not w.text.strip().startswith("(")]
            name = re.sub(r"[\s()（）]", "", "".join(w.text for w in nws))
            if name:
                out["name"] = name
                out["name_words"] = nws
        if y < 26 and "성명" in squash(t) and out["name"] is None:
            remainder = re.split(r"성명\s*[:：]?", t, maxsplit=1)[-1]
            # "성명(한자)" 머리글의 괄호 속 '한자'는 이름이 아니다 (11-26: 주민번호를 못 읽은 쪽에서
            # 성명이 '한자'로 읽혔다). 괄호 머리글만 떼고, 이름 자체는 그대로 둔다.
            remainder = re.sub(r"^\s*[(（]\s*한\s*자\s*[)）]", "", remainder)
            candidate = re.search(r"[가-힣]{2,6}", remainder)
            if candidate and candidate.group() not in {"주민등록", "생년월일"}:
                out["name"] = candidate.group()
                out["name_words"] = [w for w in line if candidate.group() in w.text] or line
        if y < 26 and "생년월일" in squash(t) and out["birth"] is None:
            found = APPLICANT_DATE.search(normalize_format_text(t))
            if found:
                digits = re.sub(r"\D", "", found.group(1))
                if len(digits) == 8:
                    try:
                        out["birth"] = date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
                        out["birth_words"] = [w for w in line if found.group(1) in w.text] or line
                    except ValueError:
                        pass
    out["title"] = squash(" ".join(title_parts))
    return out


def _parse_applicant(lines: list[list[Word]]) -> dict:
    """첫 쪽 머리 상자의 '신청인: 성명 (생년월일)'을 읽는다."""
    for line in lines:
        flat = squash(line_text(line))
        marker = re.search(r"신청인[:：]?", flat)
        if not marker:
            continue
        remainder = flat[marker.end():]
        date_match = APPLICANT_DATE.search(normalize_format_text(remainder))
        if not date_match:
            continue
        name = re.sub(r"[^가-힣]", "", remainder[:date_match.start()])
        if not re.fullmatch(r"[가-힣]{2,6}", name):
            continue
        date_digits = re.sub(r"\D", "", date_match.group(1))
        try:
            if len(date_digits) != 8:
                continue
            birth = date(int(date_digits[:4]), int(date_digits[4:6]), int(date_digits[6:8]))
        except ValueError:
            continue
        return {"name": name, "birth": birth, "words": line}
    return {"name": None, "birth": None, "words": []}


def _content_chars(lines: list[list[Word]], top: float) -> int:
    """Letters and digits between top and FOOTER_Y, without page marks, frame glyphs or 이하 여백."""
    count = 0
    for line in lines:
        if "이하여백" in squash(line_text(line)):
            continue
        for word in line:
            text = re.sub(r"\s+", "", word.text)
            if not top <= word.cy < FOOTER_Y or _PAGE_MARK_TEXT.match(text) or text in _FRAME_GLYPHS:
                continue
            count += len(re.findall(r"[가-힣A-Za-z0-9]", text))
    return count


def _table_bounds(lines: list[list[Word]], *, allow_split: bool = True,
                  corroborated: bool = False) -> tuple[float, float] | None:
    start = None
    for line in lines:
        t = squash(line_text(line))
        if line[0].cy > HEADER_MAX_Y and "번호" in t and ("세대주" in t or "신고일" in t or "발생일" in t):
            start = line[0].cy + 1.5   # 바로 아래 세로쓰기 소제목 줄 건너뜀
            break
    split = start is None
    if split:
        start = _split_header_start(lines) if allow_split else None
        if start is None:
            return None
    end = _table_end(lines, start)
    if split:
        draft: list[HistoryEntry] = []
        notes: list[int] = []
        observed: list[int] = []
        _parse_rows(lines, start, end, 0, draft, [], notes, observed)
        numbers = [entry.no for entry in draft]
        anchors, dated, paired = _history_body_evidence(lines, start, end)
        if (len(draft) < (1 if corroborated else 2)
                or any(entry.no is None or not entry.address for entry in draft)
                or len(set(numbers)) != len(numbers)
                or sorted(numbers + notes) != sorted(observed)
                or anchors != len(draft) or dated != len(draft) or paired != len(draft)
                or not _report_cells_readable(lines, start, end)):
            return None
    return start, end


def _table_end(lines: list[list[Word]], start: float) -> float:
    end = FOOTER_Y
    for line in lines:
        text = squash(line_text(line))
        if line[0].cy > start and ("이하여백" in text or ("병역" in text and line[0].x0 < 12)):
            end = min(end, line[0].cy)
    return end


def _split_header_start(lines: list[list[Word]], *, require_address: bool = True) -> float | None:
    """Prove a compact, ordered header band, without changing OCR line grouping."""
    end = _table_end(lines, HEADER_MAX_Y)
    words = [word for line in lines for word in line if HEADER_MAX_Y < word.cy < end]
    numbers = [word for word in words if squash(word.text) == "번호"
               and word.x0 < COL_NO_MAX_X and HEADER_MAX_Y < word.cy < 65]
    starts = []
    for number in numbers:
        radius = min(3.5, 3 * max(number.y1 - number.y0, .3))
        band = [word for word in words if abs(word.cy - number.cy) <= radius]
        address = [word for word in band if COL_NO_MAX_X <= word.x0 < COL_ADDR_MAX_X
                   and squash(word.text) in {"주", "소", "주소"}]
        dates = [word for word in band if COL_OCCUR_X[0] <= word.x0 < COL_HOLDER_MIN_X
                 and squash(word.text) in {"발", "생", "신", "고", "일", "발생", "신고",
                                           "발생일", "신고일", "발생일/신고일"}]
        holders = [word for word in band if word.x0 >= COL_HOLDER_MIN_X
                   and squash(word.text) in {"세대주", "및", "관계", "세대주및관계"}]

        def joined(cell):
            return squash("".join(line_text(line) for line in group_lines(cell)))

        date_label = (any(squash(word.text) in {"발생일", "신고일", "발생일/신고일"} for word in dates)
                      or any(joined([word for word in dates if left <= word.x0 < right])
                             in {"발생일", "신고일"} for left, right in (COL_OCCUR_X, COL_REPORT_X)))
        holder_label = joined(holders) in {"세대주", "세대주및관계"}
        if (require_address and joined(address) != "주소") or not (date_label or holder_label):
            continue
        selected = [number, *address, *(dates if date_label else []), *(holders if holder_label else [])]
        height = median(max(word.y1 - word.y0, .3) for word in selected)
        centers = sorted({word.cy for word in selected})
        if ((address and number.x1 >= min(word.x0 for word in address))
                or (address and max(word.x1 for word in address) >= min(word.x0 for word in dates + holders))
                or centers[-1] - centers[0] > min(3.5, 3 * height)
                or any(b - a > 1.5 * height for a, b in zip(centers, centers[1:]))):
            continue
        starts.append(max(word.y1 for word in selected))
    return starts[0] if len(starts) == 1 else None


def _history_body_evidence(lines: list[list[Word]], start: float, end: float,
                           *, require_region: bool = False) -> tuple[int, int, int]:
    """Count independent ordinal/address/date alignments, never inferred rows."""
    end = min(end, _table_end(lines, start))
    body = [word for line in lines for word in line if start <= word.cy < end]
    numbers = [word for word in body if word.x0 < COL_NO_MAX_X
               and re.fullmatch(r"[0-9]{1,3}", word.text.strip())]
    dates = [word for word in body if COL_REPORT_X[0] <= word.x0 < COL_REPORT_X[1]
             and _to_date(ISO_DATE.fullmatch(normalize_format_text(word.text))) is not None]

    def near(a, b):
        return abs(a.cy - b.cy) <= 1.5 * max(a.y1 - a.y0, b.y1 - b.y0, .3)

    def address_at(anchor):
        return any(COL_NO_MAX_X <= word.x0 < COL_ADDR_MAX_X and near(anchor, word)
                   and not word.text.strip().startswith("[") and re.search(r"[가-힣]", word.text)
                   and (not require_region or any(squash(word.text).startswith(region) for region in SIDO))
                   for word in body)

    anchors = [word for word in numbers if address_at(word)]
    dated = [word for word in dates if address_at(word)]
    paired = sum(len([number for number in anchors if near(number, word)]) == 1 for word in dated)
    return len(anchors), len(dated), paired


def _report_cells_readable(lines: list[list[Word]], start: float, end: float) -> bool:
    """Fragmented/conflicting date-shaped cells are uncertainty, not corrected values."""
    tokens = [word for line in lines for word in line if start <= word.cy < end
              and COL_REPORT_X[0] <= word.x0 < COL_REPORT_X[1]
              and (re.search(r"[0-9]", normalize_format_text(word.text))
                   or re.fullmatch(r"[OoIl]{4}[-.][OoIl]{1,2}[-.][OoIl]{1,2}", word.text.strip()))]
    return all(len(row) == 1 and _to_date(ISO_DATE.fullmatch(normalize_format_text(row[0].text))) is not None
               for row in group_lines(tokens))


def _join_note_numbers(lines: list[list[Word]], start: float, end: float) -> list[list[Word]]:
    """Associate a uniquely adjacent isolated number with a bracketed note row."""
    scoped = [line for line in lines if start <= line[0].cy < end]
    dated = [line[0].cy for line in scoped if any(
        COL_REPORT_X[0] <= word.x0 < COL_REPORT_X[1] and ISO_DATE.fullmatch(normalize_format_text(word.text))
        for word in line)]
    pitch = median(b - a for a, b in zip(dated, dated[1:])) if len(dated) > 1 else float('inf')
    numbers = [index for index, line in enumerate(scoped) if len(line) == 1 and
               line[0].x0 < COL_NO_MAX_X and re.fullmatch(r"\d{1,3}", line[0].text.strip())]
    proposals = {}
    for index, line in enumerate(scoped):
        if not any(COL_NO_MAX_X <= word.x0 < COL_ADDR_MAX_X and word.text.strip().startswith("[")
                   for word in line):
            continue
        if any(word.x0 < COL_NO_MAX_X for word in line) or any(
                COL_REPORT_X[0] <= word.x0 < COL_REPORT_X[1] and ISO_DATE.fullmatch(normalize_format_text(word.text))
                for word in line):
            continue
        candidates = []
        for number_index in numbers:
            between = scoped[min(index, number_index) + 1:max(index, number_index)]
            if between:
                continue
            pair = line + scoped[number_index]
            height = max(word.y1 - word.y0 for word in pair)
            note_y = sum(word.cy for word in line) / len(line)
            if abs(note_y - scoped[number_index][0].cy) <= min(height * .85, pitch * .45):
                candidates.append(number_index)
        if len(candidates) == 1:
            proposals[index] = candidates[0]
    assigned = Counter(proposals.values())
    merged = {index: number for index, number in proposals.items() if assigned[number] == 1}
    consumed = set(merged.values())
    return [sorted(line + scoped[merged[index]], key=lambda word: word.x0) if index in merged else line
            for index, line in enumerate(scoped) if index not in consumed]


def _parse_rows(lines: list[list[Word]], start: float, end: float, page: int,
                entries: list[HistoryEntry], pending_notes: list[str], note_numbers: list[int],
                observed_numbers: list[int]) -> None:
    for line in _join_note_numbers(lines, start, end):
        if not (start <= line[0].cy < end):
            continue
        no = None; addr: list[str] = []; occ = rep = None
        reason: list[str] = []; holder: list[str] = []
        for w in line:
            t = w.text.strip()
            if w.x0 < COL_NO_MAX_X:
                if m := re.fullmatch(r"(\d{1,3})\s*(.*)", t):
                    no = int(m.group(1))
                    observed_numbers.append(no)
                    if m.group(2):
                        addr.append(m.group(2))
                continue
            if w.x0 < COL_ADDR_MAX_X:
                addr.append(t)
            elif COL_OCCUR_X[0] <= w.x0 < COL_OCCUR_X[1] and ISO_DATE.fullmatch(normalize_format_text(t)):
                occ = _to_date(ISO_DATE.fullmatch(normalize_format_text(t)))
            elif COL_REPORT_X[0] <= w.x0 < COL_REPORT_X[1] and ISO_DATE.fullmatch(normalize_format_text(t)):
                rep = _to_date(ISO_DATE.fullmatch(normalize_format_text(t)))
            elif COL_REASON_X[0] <= w.x0 < COL_REASON_X[1]:
                reason.append(t)
            elif w.x0 >= COL_HOLDER_MIN_X:
                holder.append(t)

        notes = [a for a in addr if a.startswith("[")]
        addr = [a for a in addr if not a.startswith("[")]
        pending_notes.extend(notes)
        if notes and rep is None and no is not None:
            # 실측: "[도로명주소 ...]", "[행정구역 변경 ...]" 메모 줄도 자기 순번을 가진다
            note_numbers.append(no)
            no = None

        if rep is not None:  # 신고일이 있는 줄 = 새 건의 첫 줄
            e = HistoryEntry(no=no, address=addr, occurred=occ, reported=rep,
                             reason=reason, holder=holder, notes=list(pending_notes),
                             page=page, words=list(line))
            pending_notes.clear()
            entries.append(e)
        elif entries and (no is not None or addr or reason or holder):  # 이어지는 줄
            e = entries[-1]
            if e.no is None and no is not None:
                e.no = no
            e.address += addr; e.reason += reason; e.holder += holder
            e.words += list(line)


# --- 메인 ---------------------------------------------------------------
def extract(pages: list[tuple[PageImage, OcrResult]], today: date | None = None) -> ResidentAbstractResult:
    today = today or kst_today()
    page_map = {p.page: p for p, _ in pages}
    headers = []
    first_page_lines: list[list[Word]] = []
    entries: list[HistoryEntry] = []
    pending: list[str] = []
    note_numbers: list[int] = []
    observed_numbers: list[int] = []
    warnings: list[str] = []

    table_issues: list[str] = []

    contentless: list[bool] = []
    table_without_rows: list[bool] = []
    #: 표 머리글만 되풀이되고 이력 줄·내용이 없는 쪽 (다른 쪽과 같은 쪽표기일 때만 쪽 수에서 뺀다).
    table_only: list[bool] = []
    prior_table_read = False
    page_lines: list[tuple[int, list[list[Word]]]] = []
    for p, r in pages:
        lines = group_lines(normalize(r.words, p.page, p.pixel_size))
        page_lines.append((p.page, lines))
        if p.page == 0:
            first_page_lines = lines
        headers.append(_parse_header(lines))
        bounds = _table_bounds(lines, allow_split=False)
        previous = bool(entries)
        marker = headers[-1]["page_no"]
        prior_marker = headers[-2]["page_no"] if len(headers) > 1 else None
        compatible = (marker is not None and prior_marker is not None
                      and marker == (prior_marker[0] + 1, prior_marker[1]))
        if bounds is None and previous and compatible:
            bounds = _table_bounds(lines, corroborated=prior_table_read)
        contentless.append(bounds is None and _content_chars(lines, BODY_TOP_Y) <= BLANK_BODY_MAX_CHARS)
        before, notes_before = len(entries), len(note_numbers)
        issue = None
        if bounds:
            # Preserve legacy parsing exactly unless independent evidence exposes a new risk.
            draft, draft_pending = deepcopy(entries), list(pending)
            draft_notes, draft_observed = list(note_numbers), list(observed_numbers)
            _parse_rows(lines, *bounds, p.page, draft, draft_pending, draft_notes, draft_observed)
            draft_numbers = [entry.no for entry in draft if entry.no is not None] + draft_notes
            legacy_sequence_ok = (all(entry.no is not None for entry in draft)
                                  and sorted(draft_numbers) == sorted(draft_observed))
            if (previous and len(draft) > before and legacy_sequence_ok
                    and not _report_cells_readable(lines, *bounds)):
                issue = "ROWS_UNREADABLE"
            else:
                entries, pending = draft, draft_pending
                note_numbers, observed_numbers = draft_notes, draft_observed
        else:
            warnings.append(f"page {p.page}: 주소 이력 표를 찾지 못함")
            if previous and compatible:
                anchors, dated, paired = _history_body_evidence(lines, HEADER_MAX_Y, FOOTER_Y, require_region=True)
                if (paired >= 2 or (paired and _split_header_start(lines, require_address=False) is not None)
                        or (_split_header_start(lines) is not None and (anchors or dated))):
                    issue = "TABLE_NOT_FOUND"
        if issue and issue not in table_issues:
            table_issues.append(issue)
        table_only.append(bool(bounds) and len(entries) == before
                          and _content_chars(lines, bounds[0]) <= BLANK_BODY_MAX_CHARS)
        table_without_rows.append(bool(bounds) and len(entries) == before and len(note_numbers) == notes_before)
        prior_table_read = (bool(bounds) and not issue and len(entries) > before and legacy_sequence_ok
                            and _report_cells_readable(lines, *bounds))

    # --- 서류 종류 ---
    titles = "".join(h["title"] for h in headers)
    is_abs = "(초본)" in titles or "이초본은" in titles
    is_reg = "(등본)" in titles or "이등본은" in titles
    if is_abs and not is_reg:
        detected, tconf = DocType.RESIDENT_ABSTRACT, 0.95
    elif is_reg and not is_abs:
        detected, tconf = DocType.RESIDENT_REGISTER, 0.95
    elif "주민등록표" in titles:
        detected, tconf = DocType.UNKNOWN, 0.4
        warnings.append("주민등록표이나 등본/초본 구분 실패")
    else:
        detected, tconf = DocType.UNKNOWN, 0.1

    classification_evidence = ""
    if detected == DocType.UNKNOWN and not (is_abs or is_reg):
        from ..pipeline.resident_title import classify_resident_title
        kind, evidence = classify_resident_title(pages)
        if kind is not None:
            detected = DocType.RESIDENT_ABSTRACT if kind == "abstract" else DocType.RESIDENT_REGISTER
            tconf = .95
            classification_evidence = evidence
            warnings = [w for w in warnings if w != "주민등록표이나 등본/초본 구분 실패"]

    validations: list[Validation] = []
    fields: dict[str, ExtractedField] = {}
    n = len(headers)

    def consistent(key: str) -> tuple[object, bool, list[Word]]:
        vals = [h[key] for h in headers if h[key] is not None]
        if not vals:
            return None, False, []
        top, cnt = Counter(vals).most_common(1)[0]
        words = next((h.get(f"{key}_words", []) for h in headers if h[key] == top), [])
        return top, cnt == len(vals) and len(vals) == n, words

    # --- 쪽 완전성 ---
    pnos = [h["page_no"] for h in headers if h["page_no"]]
    if pnos:
        total = pnos[0][1]
        seen = sorted({a for a, _ in pnos})
        ok = seen == list(range(1, total + 1))
        validations.append(Validation("pages_complete", ok, f"{seen} / 전체 {total}쪽"))
    else:
        validations.append(Validation("pages_complete", False, "쪽 번호를 읽지 못함"))

    # --- 문서확인번호 ---
    doc_no, doc_same, _ = consistent("doc_no")
    validations.append(Validation("doc_no_consistent", doc_same, "모든 쪽 동일" if doc_same else "쪽마다 다르거나 누락"))

    # --- 발급일 ---
    issue, issue_same, iw = consistent("issue")
    if issue:
        not_future = issue <= today
        validations += [Validation("issue_date_consistent", issue_same),
                        Validation("issue_date_not_future", not_future)]
        fields["issue_date"] = ExtractedField(
            value=issue, raw_text=iw[0].text if iw else "", source=FieldSource.OCR,
            confidence=_confidence([issue_same, not_future, doc_same], hard_fail=not not_future, consistent=issue_same),
            bbox=_bbox(iw, page_map))

    # --- 발급기관 ---
    issuer = next((h["issuer"] for h in headers if h["issuer"]), None)
    if issuer:
        fields["issuer"] = ExtractedField(value=issuer, raw_text=issuer, confidence=0.7, source=FieldSource.OCR)

    # --- 성명 ---
    name, name_same, nw = consistent("name")
    if name:
        plausible = bool(re.fullmatch(r"[가-힣]{2,6}", name))
        validations.append(Validation("name_consistent", name_same))
        fields["name"] = ExtractedField(
            value=name, raw_text=name, source=FieldSource.OCR,
            confidence=_confidence([name_same, plausible], consistent=name_same), bbox=_bbox(nw, page_map))

    # --- 생년월일 (주민번호 원문은 남기지 않음) ---
    birth, birth_same, bw = consistent("birth")
    if birth:
        g = next(h["gender"] for h in headers if h["birth"] == birth)
        validations.append(Validation("birth_consistent", birth_same))
        fields["birth_date"] = ExtractedField(
            value=birth, raw_text=f"{birth:%y%m%d}-{g}******", source=FieldSource.OCR,
            confidence=_confidence([birth_same, birth <= today], consistent=birth_same), bbox=_bbox(bw, page_map))

    # --- 첫 쪽 신청인 대조 정보 ---
    applicant = _parse_applicant(first_page_lines)
    if applicant["name"]:
        fields["applicant_name"] = ExtractedField(
            value=applicant["name"], raw_text=applicant["name"], source=FieldSource.OCR,
            confidence=0.9, bbox=_bbox(applicant["words"], page_map))
    if applicant["birth"]:
        fields["applicant_birth_date"] = ExtractedField(
            value=applicant["birth"], raw_text=applicant["birth"].isoformat(), source=FieldSource.OCR,
            confidence=0.9, bbox=_bbox(applicant["words"], page_map))
    if not applicant["name"] or not applicant["birth"]:
        warnings.append("첫 쪽 신청인 성명·생년월일을 모두 읽지 못함")

    # --- 주소 이력 ---
    entry_nos = [e.no for e in entries if e.no is not None]
    nos = sorted(entry_nos + note_numbers)
    if entries or note_numbers or observed_numbers or detected == DocType.RESIDENT_ABSTRACT:
        # 11-26: 순번이 있는 메모 줄은 다음 건에 붙는다(실측). 마지막 건보다 큰 메모 순번은 뒤따르는 건을
        # 읽지 못했다는 뜻이다 (끝 이력 누락). 순번 없는 덧붙임 안내는 지금처럼 다루지 않는다.
        orphan_notes = sorted(n for n in note_numbers if not entry_nos or n > max(entry_nos))
        seq_ok = (bool(entries) and len(entry_nos) == len(entries) and
                  bool(nos) and nos == list(range(nos[0], nos[0] + len(nos))) and
                  sorted(observed_numbers) == nos and not orphan_notes)
        missing = sorted(set(range(nos[0], nos[-1] + 1)) - set(nos)) if nos else []
        validations.append(Validation(
            "history_numbers_sequential", seq_ok,
            f"순번 {len(nos)}개 (이력 {len(entry_nos)} + 메모 {len(note_numbers)}) / 건 {len(entries)}개"
            + (f", 빠진 번호 {missing}" if missing else "")
            + (f", 뒤따르는 건 없는 메모 순번 {orphan_notes}" if orphan_notes else "")))
    eff = [e.effective for e in entries if e.effective]
    order_ok = all(a <= b for a, b in zip(eff, eff[1:]))
    validations.append(Validation("history_dates_ordered", order_ok))
    occ_ok = all(e.occurred <= e.reported for e in entries if e.occurred and e.reported)
    validations.append(Validation("occurred_before_reported", occ_ok))

    hist_checks = [v.passed for v in validations if v.name.startswith(("history", "occurred"))]
    legacy_history_complete = all(hist_checks)
    history_complete = legacy_history_complete and not table_issues
    if table_issues:
        validations.append(Validation("history_tables_readable", False))
        warnings.append("후속 페이지의 주소 이력 표를 완전히 읽지 못했습니다.")
    if not history_complete:
        warnings.append("주소 이력의 순번 또는 날짜를 완전히 확인하지 못했습니다.")
    if entries:
        fields["address_history_count"] = ExtractedField(
            value=len(entries), raw_text=f"{len(entries)}건", source=FieldSource.OCR,
            confidence=_confidence(hist_checks))
        fields["address_history"] = ExtractedField(
            value=[{"no": e.no, "sido": resolved_sido(entries, i), "address": e.address_text,
                    "occurred": e.occurred, "reported": e.reported,
                    "reason": " ".join(e.reason), "notes": e.notes}
                   for i, e in enumerate(entries)],
            raw_text=f"{len(entries)}건", source=FieldSource.OCR,
            confidence=_confidence(hist_checks))
        last = entries[-1]
        fields["current_address"] = ExtractedField(
            value=last.address_text, raw_text=last.address_text, source=FieldSource.OCR,
            confidence=_confidence(hist_checks + [resolved_sido(entries, len(entries) - 1) is not None]),
            bbox=_bbox(last.words, page_map))

    if not legacy_history_complete:
        for extracted in fields.values():
            extracted.confidence = min(extracted.confidence, .4)
    elif not history_complete:
        for key in ("address_history", "address_history_count", "current_address"):
            if key in fields:
                fields[key].confidence = min(fields[key].confidence, .4)

    # 내용 없는 쪽(빈 쪽, 머리 상자만 되풀이된 쪽)은 쪽표기가 없거나 다른 쪽과 같은 쪽표기일 때만
    # 쪽 수 확인에서 뺀다. 내용이 있는 쪽은 중복이어도 그대로 센다. 표 머리글까지 되풀이된 빈 쪽은
    # 다른 쪽과 같은 쪽표기일 때만 뺀다(쪽표기를 못 읽으면 그대로 세어 판독 불가로 남는다).
    blank = [contentless[i] or table_only[i] for i in range(len(headers))]
    kept = [i for i in range(len(headers)) if not blank[i]]
    kept_markers = {headers[i]["page_no"] for i in kept}
    for i in range(len(headers)):
        marker = headers[i]["page_no"]
        if blank[i] and ((marker is not None and marker not in kept_markers)
                         or (not contentless[i] and marker is None)):
            kept.append(i)
            kept_markers.add(marker)
    kept.sort()
    if not kept:
        kept = list(range(len(headers)))
    # S1 (held): a sheet with two or more header markers at least SHEET_SPREAD apart and one document
    # number holds several printed pages (2-up). Body text never counts (header band only).
    sheets, multi = [], False
    for i in kept:
        found = sorted(headers[i]["header_markers"])
        xs = [x for x, _, _ in found]
        if len(found) >= 2 and max(xs) - min(xs) >= SHEET_SPREAD and len(headers[i]["doc_nos"]) <= 1:
            sheets.append([marker for _, marker, _ in found])
            headers[i]["page_confidence"] = min(conf for _, _, conf in found)
            multi = True
        else:
            sheets.append([headers[i]["page_no"]])
    # 주소 이력 누락 감지 (11-18): 순번은 1부터 빠짐없이 이어져야 하고(메모 줄도 자기 순번을 가진다),
    # 표 머리글을 찾은 쪽은 이력 줄을 한 건 이상 읽어야 한다. 쪽 수에서 뺀 중복 빈 쪽은 보지 않는다.
    numbers = sorted([e.no for e in entries if e.no is not None] + note_numbers)
    history_numbers = ("NA" if not entries else
                       "UNREADABLE" if any(e.no is None for e in entries) else
                       "CONTIGUOUS" if numbers == list(range(1, len(numbers) + 1)) else "GAP")
    history_empty_page = any(table_without_rows[i] for i in kept)
    if history_empty_page and not table_issues:
        # The direct engine also needs the existing adapter's empty-table evidence.
        validations.append(Validation("history_tables_readable", False))
        warnings.append("주소 이력 표가 있는 쪽에서 이력을 읽지 못했습니다.")
        for key in ("address_history", "address_history_count", "current_address"):
            if key in fields:
                fields[key].confidence = min(fields[key].confidence, .4)
    history_end, history_end_page = _history_end(page_lines, entries)
    return ResidentAbstractResult(
        detected, tconf, fields, entries, validations, warnings,
        history_end=history_end, history_end_page=history_end_page,
        history_numbers=history_numbers, history_empty_page=history_empty_page,
        history_table_issues=table_issues,
        sheet_markers=sheets if multi else None,
        page_markers=[headers[i]["page_no"] for i in kept],
        marker_pages=[pages[i][0].page for i in kept],
        classification_evidence=classification_evidence,
        page_marker_confidence=min((headers[i]["page_confidence"] for i in kept), default=0.0),
        blank_pages=len(headers) - len(kept),
    )


#: 11-26: 주소 이력 끝 근거. address_dates.py가 초본 표 끝으로 쓰는 것과 같은 단독 '이하 여백' 줄
#: (앞뒤 꾸밈 기호만 허용, 부분 문자열 불인정)만 인정한다.
_HISTORY_END_MARKER = re.compile(r"[=＝*＊·.()（）\-–—]*이하여백[=＝*＊·.()（）\-–—]*")


def _history_row_word(word) -> bool:
    """A word that only a history row carries: a number-column ordinal or a report-column date."""
    text = word.text.strip()
    return ((word.x0 < COL_NO_MAX_X and re.fullmatch(r"\d{1,3}", text) is not None)
            or (COL_REPORT_X[0] <= word.x0 < COL_REPORT_X[1]
                and ISO_DATE.fullmatch(normalize_format_text(text)) is not None))


def _history_end(page_lines, entries) -> tuple[str, int | None]:
    """Positive evidence that the last parsed entry is the last history row (11-26).

    BLANK_MARKER / NEXT_SECTION: on the page of the last entry, a standalone 이하 여백 line or the next
    section's heading in the ordinal column (병역사항; both are _table_end's terminators from the 실측
    layout) follows it, with no ordinal or report date between them or below it on that page. NONE: no such evidence (an unread last
    row, a cut page bottom, a missing marker), so the end of the history is unknown. NA: no history.
    The marker's distance from the last row is not judged: authored layouts place it one to several
    rows below, and no observed form fixes it. Returns (kind, 1-based scan page of the marker).
    """
    if not entries:
        return "NA", None
    last = entries[-1]
    order = [number for number, _ in page_lines]
    if last.page not in order or not last.words:
        return "NONE", None
    index = order.index(last.page)
    # Only the entry's words on its own page: continuation lines may carry words from a later page.
    own = [word for word in last.words if word.page == last.page]
    if not own:
        return "NONE", None
    centre = max(word.cy for word in own)
    for line in page_lines[index][1]:
        if not centre < line[0].cy < FOOTER_Y:
            continue
        if any(_history_row_word(word) for word in line):
            return "NONE", None  # a row, or part of one, that no parsed entry holds
        marker = _HISTORY_END_MARKER.fullmatch(squash(line_text(line)))
        # The next section's heading in the ordinal column (병역사항) also ends the table, as _table_end has it.
        section = "병역" in squash(line_text(line)) and line[0].x0 < 12
        if marker or section:
            # Rows below the marker on its own page contradict it. A later page is not judged here:
            # without a table header it is another section (11-18 continuation contract), and with one
            # its rows are already parsed entries, which would have moved the last entry there.
            below = [word for row in page_lines[index][1] for word in row
                     if line[0].cy < word.cy < FOOTER_Y]
            if any(_history_row_word(word) for word in below):
                return "NONE", None
            return ("BLANK_MARKER" if marker else "NEXT_SECTION"), page_lines[index][0] + 1
    return "NONE", None


def resolved_sido(entries: list[HistoryEntry], i: int) -> str | None:
    """시도가 안 적힌 건(도로명 상세만 있는 경우 등)은 바로 앞 건의 시도를 이어받는다."""
    for e in reversed(entries[: i + 1]):
        if e.sido:
            return e.sido
    return None


def trailing_residence_start(entries: list[HistoryEntry], sido: str = "전북") -> date | None:
    """맨 마지막 건부터 거슬러 올라가며 해당 시도에 연속 거주를 시작한 날짜.

    세대주변경·행정구역 명칭 변경(전라북도→전북특별자치도) 같은 건은 시도가 같으므로 끊기지 않는다.
    """
    start = None
    for i in range(len(entries) - 1, -1, -1):
        if resolved_sido(entries, i) != sido:
            break
        start = entries[i].effective or start
    return start


def months_between(a: date, b: date) -> int:
    m = (b.year - a.year) * 12 + (b.month - a.month)
    return m - 1 if b.day < a.day else m
