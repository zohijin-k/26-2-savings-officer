"""건강보험료 납부확인서 판독기. 월별 고지 열을 기준으로 보험료를 검증한다."""

from __future__ import annotations

import re
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from ..pipeline.layout import line_text, squash
from ..pipeline.ocr import OcrResult
from ..pipeline.preprocess import PageImage
from ..schemas.models import DocType, ExtractedField
from . import nhis_common as common
from .format_text import normalize_format_text

MONTH_RE = re.compile(r"(?<!\d)(20\d{2})\s*(?:(?:[-./]\s*)|(?:년\s*)|\s)(0?[1-9]|1[0-2])\s*월?\s*\.?(?!\d)")
COMPACT_MONTH_RE = re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(?!\d)")
MONEY_RE = re.compile(r"(?<!\d)([-−]?\s*\d[\d,\s]*)(?:원)?(?!\d)")
MONTH_ONLY_RE = re.compile(r"(?<!\d)(0?[1-9]|1[0-2])\s*월(?!\d)")
PERIOD_RE = re.compile(r"(20\d{2})\s*년\s*(0?[1-9]|1[0-2])\s*월\s*[~～\-]\s*(20\d{2})\s*년\s*(0?[1-9]|1[0-2])\s*월")
CARE = ("장기요양보험료", "장기요양", "노인장기요양")
HEALTH = ("건강보험료", "건강보험")
OUTSIDE_HEALTH = ("보수외소득월액(건강)", "보수외소득월액건강", "보수외건강")
MONTH_LABELS = ("년월", "월별", "보험료월", "납부월", "납부년월", "청구월", "보험료연월")
TABLE_LABELS = MONTH_LABELS + ("고지금액", "고지보험료", "납부금액", "납부보험료", "실납부",
                               "건강보험료", "장기요양보험료", "장기요양")
TABLE_LABEL_FRAGMENTS = ("고지", "금액", "납부", "보험료", "건강", "장기요양", "실납부", "년", "월")
REVIEW_VALIDATIONS = frozenset({
    "document_type", "성명_consistent", "생년월일_consistent", "발급일_consistent", "page_names_match",
    "monthly_rows_found", "monthly_amounts_numeric", "months_continuous", "monthly_total_matches", "paid_total_matches",
})


def has_failed_payment_validation(fields) -> bool:
    """Recognize critical failed checks in fresh or persisted Korean field data."""
    failed = str(fields.get("판독검증실패", ""))
    return bool({name.strip() for name in failed.split(",")} & REVIEW_VALIDATIONS)


@dataclass
class PaymentResult:
    detected_type: DocType
    type_confidence: float
    fields: dict[str, ExtractedField]
    validations: list[common.Validation]
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict[str, str] = field(default_factory=dict)
    form_kind: str | None = None
    structure_complete: bool | None = None
    # Independent zero/blank evidence; low-confidence annual placeholders do
    # not invalidate a complete form or unrelated requested billing months.
    billing_absence_states: dict[str, str] = field(default_factory=dict)


def _money_words(line):
    found = []
    row_text = " ".join(word.text for word in line)
    has_month = bool(MONTH_RE.search(normalize_format_text(row_text)) or COMPACT_MONTH_RE.search(normalize_format_text(row_text)))
    i = 0
    while i < len(line):
        accepted = None
        date_prefix = False
        for end in range(i + 1, min(len(line), i + 4) + 1):
            words = line[i:end]
            raw = "".join(word.text for word in words).replace("원", "")
            if MONTH_RE.fullmatch(normalize_format_text(raw)) or COMPACT_MONTH_RE.fullmatch(normalize_format_text(raw)):
                date_prefix = True
                break
            if has_month and re.fullmatch(r"20\d{2}", raw.strip()):
                continue
            match = MONEY_RE.fullmatch(re.sub(r"\s+", "", raw))
            if not match:
                continue
            token = match.group(1).replace("−", "-").replace(",", "").replace(" ", "")
            negative = token.startswith("-")
            digits = token.lstrip("-")
            if digits in ("", "-"):
                continue
            if raw.rstrip().endswith(",") and end < len(line):
                next_word = line[end]
                gap = next_word.x0 - max(word.x1 for word in words)
                height = max(max(word.y1 - word.y0, 0.3) for word in words + [next_word])
                if gap <= height * 2:
                    continue
            x0, y0 = min(w.x0 for w in words), min(w.y0 for w in words)
            x1, y1 = max(w.x1 for w in words), max(w.y1 for w in words)
            px = (min(w.px[0] for w in words), min(w.px[1] for w in words),
                  max(w.px[2] for w in words), max(w.px[3] for w in words))
            merged = common.Word(raw, min(w.conf for w in words), words[0].page, x0, y0, x1, y1, px)
            accepted = (merged, -int(digits) if negative else int(digits))
            i = end
            break
        if accepted:
            found.append(accepted)
        elif date_prefix:
            i += 1
        else:
            i += 1
    return found


def _month_header(lines):
    def exact_header(block):
        return [(label, words) for label, words in common.label_hits(block, MONTH_LABELS)
                if squash("".join(word.text for word in words)) == squash(label)]

    found = [i for i, line in enumerate(lines) if exact_header([line])]
    for i in range(1, len(lines)):
        current_ids = {id(word) for word in lines[i]}
        prior_ids = {id(word) for line in lines[max(0, i - 2) : i] for word in line}
        if any(any(id(word) in current_ids for word in words) and
               any(id(word) in prior_ids for word in words) for _, words in exact_header(lines[max(0, i - 2) : i + 1])):
            found.append(i)
    return sorted(set(found))


def _header_block(lines, index):
    included = {index}
    cursor = index - 1
    while cursor >= 0:
        line = lines[cursor]
        flat = squash(line_text(line))
        neighbor = lines[cursor + 1]
        partial_label = common.label_hits([line, neighbor], TABLE_LABELS)
        full_label = any(label in flat for label in TABLE_LABELS) or flat in TABLE_LABEL_FRAGMENTS
        if not partial_label and not full_label:
            break
        if MONTH_RE.search(normalize_format_text(line_text(line))) or COMPACT_MONTH_RE.search(re.sub(r"\s+", "", line_text(line))):
            break
        included.add(cursor)
        cursor -= 1
    cursor = index + 1
    while cursor < len(lines):
        line = lines[cursor]
        flat = squash(line_text(line))
        neighbor = lines[cursor - 1]
        partial_label = common.label_hits([neighbor, line], TABLE_LABELS)
        full_label = any(label in flat for label in TABLE_LABELS) or flat in TABLE_LABEL_FRAGMENTS
        if not partial_label and not full_label:
            break
        if MONTH_RE.search(normalize_format_text(line_text(line))) or COMPACT_MONTH_RE.search(re.sub(r"\s+", "", line_text(line))):
            break
        included.add(cursor)
        cursor += 1
    return [lines[i] for i in sorted(included)]


def _header_x(pages, labels, page_no=None):
    positions = []
    for page, result in pages:
        if page_no is not None and page.page != page_no:
            continue
        lines = common.page_lines(page, result)
        for index in _month_header(lines):
            block = _header_block(lines, index)
            for _, words in common.label_hits(block, labels):
                if words:
                    positions.append((min(w.x0 for w in words) + max(w.x1 for w in words)) / 2)
    return positions


def _closest_amount(amounts, x):
    return min(amounts, key=lambda item: abs((item[0].x0 + item[0].x1) / 2 - x)) if amounts else None


#: Printed label of one combined health+care column; such forms keep the group-header path.
EXPLICIT_COMBINED = "건강보험료및장기요양보험료합계"
#: Months whose 고지금액 decide the income check (same months as ``_average``).
AMOUNT_GUARD_MONTHS = ((2025, 10), (2025, 11), (2025, 12))
#: 11-19 guard reasons: a 0원 pick, a pick 12-14% of another amount in its row, a pick under a
#: 장기요양 header or an unreadable header, a larger amount under a 건강 header in its row.
AMOUNT_GUARD_CODES = ("ZERO_AMOUNT", "CARE_RATIO", "HEADER_CARE", "HEADER_UNCERTAIN", "LARGER_HEALTH")
HEADER_CONFIDENCE = .85
HEADER_LABELS = TABLE_LABELS + HEALTH + CARE + OUTSIDE_HEALTH + ("보수외소득월액(요양)", "합계")


def _header_blocks(pages):
    """(page number, header block lines) for every month header, in page and reading order."""
    blocks = []
    for page, result in pages:
        lines = common.page_lines(page, result)
        for index in _month_header(lines):
            blocks.append((page.page, _header_block(lines, index)))
    return blocks


def _header_boxes(pages, labels):
    """Boxes (x0, y0, x1, y1) of header label hits in the same order as ``_header_x``."""
    boxes = []
    for _, block in _header_blocks(pages):
        for _, words in common.label_hits(block, labels):
            if words:
                boxes.append((min(w.x0 for w in words), min(w.y0 for w in words),
                              max(w.x1 for w in words), max(w.y1 for w in words)))
    return boxes


def _short_health_boxes(pages):
    """A sub-header printed only as '건강' (11-19). Exact word only: '(건강)' is 보수외소득월액(건강)."""
    return [(w.x0, w.y0, w.x1, w.y1) for _, block in _header_blocks(pages)
            for line in block for w in line if w.text.strip() == "건강"]


def _char_span(line, key):
    """x-span of the characters of ``key`` inside a line, splitting a fused OCR box by characters."""
    chars = [(word, index, len(squash(word.text))) for word in line for index in range(len(squash(word.text)))]
    start = "".join(squash(word.text) for word in line).find(key)
    if start < 0:
        return None

    def edge(word, index, count, right):
        return word.x0 + (index + right) / count * (word.x1 - word.x0)
    return edge(*chars[start], 0), edge(*chars[start + len(key) - 1], 1)


def _fused_component_xs(pages):
    """Health/care centres when one OCR box holds both sub-headers ('건강보험료장기요양보험료')."""
    for _, block in _header_blocks(pages):
        for line in block:
            for word in line:
                text = squash(word.text)
                if not (any(squash(h) in text for h in HEALTH) and any(squash(c) in text for c in CARE)):
                    continue
                health = next((span for h in HEALTH if (span := _char_span([word], squash(h)))), None)
                care = next((span for c in CARE if (span := _char_span([word], squash(c)))), None)
                if health and care:
                    return sum(health) / 2, sum(care) / 2
    return None


def _column_words(header_lines, x):
    """Header words of the column at ``x``: the nearest word of each header line, top to bottom."""
    found = []
    for line in header_lines:
        chunks = []
        for word in sorted((w for w in line if squash(w.text) not in MONTH_LABELS), key=lambda w: w.x0):
            # Close words forming part of one known label are one label ('고지' '금액'); two
            # neighbouring column headers ('건강보험료' '장기요양보험료') stay apart.
            joined = "".join(squash(w.text) for w in chunks[-1]) + squash(word.text) if chunks else ""
            if (chunks and word.x0 - chunks[-1][-1].x1 <= 2 * max(word.y1 - word.y0, chunks[-1][-1].y1 - chunks[-1][-1].y0)
                    and any(joined in squash(label) for label in HEADER_LABELS)):
                chunks[-1].append(word)
            else:
                chunks.append([word])
        if chunks:
            found.extend(min(chunks, key=lambda c: abs((c[0].x0 + c[-1].x1) / 2 - x)))
    return found


def _health_family(words):
    """A 건강보험료 column header; never 보수외소득월액(건강) nor a 장기요양 column."""
    text = "".join(squash(w.text) for w in words)
    return (not any(part in text for part in ("요양", "보수", "소득")) and
            any(squash(w.text) in ("건강", "건강보험", "건강보험료") or squash(w.text).startswith("건강보험")
                for w in words))


def amount_guard_reasons(billed, others, billed_header=None, other_headers=None):
    """11-19 guard on one billed month: reason codes (empty when none apply).

    ``billed``: picked amount; ``others``: the other amounts in its row. ``billed_header``: the
    picked column's header words, or None when the header is fixed by the form (government form,
    exact header match). ``other_headers``: header words per other amount (same order) or None.
    """
    reasons = set()
    if billed == 0:
        reasons.add("ZERO_AMOUNT")
    if any(value > 0 and billed > 0 and .12 <= billed / value <= .14 for value in others):
        reasons.add("CARE_RATIO")
    if billed_header is not None:
        text = "".join(squash(w.text) for w in billed_header)
        if "요양" in text:
            reasons.add("HEADER_CARE")
        if (not billed_header or any(w.conf < HEADER_CONFIDENCE for w in billed_header) or
                not ("건강" in text or "고지" in text)):
            reasons.add("HEADER_UNCERTAIN")
    # A negative pick is a refund/adjustment row; income already rejects it (PREMIUM_AMOUNT_INVALID).
    if other_headers is not None and billed >= 0:
        if any(value > billed and _health_family(words) for value, words in zip(others, other_headers)):
            reasons.add("LARGER_HEALTH")
    return reasons


class _Monthly(tuple):
    """The 16-value parse; ``amount_guard`` carries the 11-19 guard reasons per target month."""
    amount_guard: dict = {}


def charge_grouped(pages) -> bool:
    """고지금액 is a group header: a component sub-header is printed below it (11-19).

    Its centre is then not a column and falls on the 장기요양 column of a four-column group.
    """
    charge = _header_boxes(pages, ("고지금액", "고지보험료"))
    components = (_header_boxes(pages, HEALTH) + _short_health_boxes(pages) + _header_boxes(pages, CARE) +
                  _header_boxes(pages, OUTSIDE_HEALTH))
    return bool(charge) and any(box[1] >= charge[0][3] - .25 * (charge[0][3] - charge[0][1]) for box in components)


def amount_layout(pages) -> str:
    """Legacy table layout code for diagnostics: SINGLE/GROUP × how the 건강 sub-header was found."""
    if EXPLICIT_COMBINED in squash(" ".join(result.text for _, result in pages)):
        return "COMBINED"
    if not _header_x(pages, ("고지금액", "고지보험료")):
        return "NO_CHARGE_HEADER"
    health, care = _header_x(pages, HEALTH), _header_x(pages, CARE)
    sub = ("FUSED" if health and care and health[0] == care[0] else "HEALTH" if health else
           "SHORT" if _short_health_boxes(pages) else "MISSING")
    return ("GROUP_" if charge_grouped(pages) else "SINGLE_") + sub


def _extract_monthly(pages):
    parsed, guard = _extract_monthly_detail(pages)
    result = _Monthly(parsed)
    result.amount_guard = guard
    return result


def _extract_monthly_detail(pages):
    """``_extract_monthly`` plus the 11-19 guard reasons per target month."""
    charge_xs = _header_x(pages, ("고지금액", "고지보험료"))
    paid_xs = _header_x(pages, ("납부금액", "납부보험료", "실납부"))
    health_xs = _header_x(pages, HEALTH)
    care_xs = _header_x(pages, CARE)
    all_text = " ".join(result.text for _, result in pages)
    flat = squash(all_text)
    explicit_combined = EXPLICIT_COMBINED in flat
    if not explicit_combined:
        # 11-19: locate the 건강보험료 sub-column of a 고지금액 group instead of using the group centre.
        if not health_xs:
            health_xs = [(b[0] + b[2]) / 2 for b in _short_health_boxes(pages)]
        if health_xs and care_xs and health_xs[0] == care_xs[0]:
            fused = _fused_component_xs(pages)
            if fused is not None:
                health_xs = [fused[0]] + health_xs[1:]
                care_xs = [fused[1]] + care_xs[1:]
    grouped = not explicit_combined and charge_grouped(pages)
    blocks = _header_blocks(pages)
    header_lines = blocks[0][1] if blocks else []
    guard: dict[tuple[int, int], set[str]] = {}
    separate_components = bool(health_xs and care_xs and health_xs[0] != care_xs[0])
    combined = (explicit_combined or
                ("합계" in flat and any(word in flat for word in CARE) and not separate_components))

    monthly: dict[tuple[int, int], tuple[int, list[common.Word]]] = {}
    care_monthly: dict[tuple[int, int], tuple[int, list[common.Word]]] = {}
    outside_health_monthly: dict[tuple[int, int], tuple[int, list[common.Word]]] = {}
    totals: list[int] = []
    paid_monthly: dict[tuple[int, int], tuple[int, list[common.Word]]] = {}
    paid_totals: list[int] = []
    settlement_billed = 0
    settlement_paid = 0
    has_settlement_billed = False
    has_settlement_paid = False
    all_months: list[tuple[int, int]] = []
    target_seen: set[tuple[int, int]] = set()
    target_words: dict[tuple[int, int], list[common.Word]] = {}
    money_numeric = True
    nonpositive = False
    period_start = period_end = None
    for _, result in pages:
        match = PERIOD_RE.search(normalize_format_text(result.text))
        if match:
            period_start = (int(match.group(1)), int(match.group(2)))
            period_end = (int(match.group(3)), int(match.group(4)))
            break

    def label_year(month):
        # 연도 없는 'N월' 줄의 연도는 조회기간 제목에서 정한다. 같은 해 안의 조회기간이면 1~12월
        # 고정 표의 모든 줄이 그 해다. 해를 넘는 조회기간이면 시작 월 앞의 달이 다음 해다.
        if period_end is not None and period_end[0] == period_start[0]:
            return period_start[0]
        return period_start[0] if month >= period_start[1] else period_start[0] + 1
    for page, result in pages:
        # 쪽별 표 인식이 머리글 일부를 빠뜨려도 같은 양식의 다른 쪽에서 찾은
        # 열 위치를 쓴다. 페이지마다 같은 표 너비·열 순서를 유지하는 서식이다.
        page_charge_xs = charge_xs[:1]
        page_paid_xs = paid_xs[:1]
        page_health_xs = health_xs[:1]
        page_care_xs = care_xs[:1]
        page_outside_health_xs = _header_x(pages, OUTSIDE_HEALTH)[:1]
        lines = common.page_lines(page, result)
        header_indices = _month_header(lines)
        if not header_indices:
            continue
        table_start = max(header_indices)
        for line in lines[table_start + 1 :]:
            text = line_text(line)
            flat_line = squash(text)
            if "확인합니다" in flat_line or "국민건강보험공단" in flat_line:
                break
            if "연말정산" in flat_line:
                settlement_amounts = _money_words(line)
                if settlement_amounts and page_charge_xs:
                    settlement_charge = _closest_amount(settlement_amounts, page_charge_xs[0])
                    if settlement_charge:
                        settlement_billed += settlement_charge[1]
                        has_settlement_billed = True
                if len(settlement_amounts) > 1 and page_paid_xs:
                    settlement_payment = _closest_amount(settlement_amounts, page_paid_xs[0])
                    if settlement_payment:
                        settlement_paid += settlement_payment[1]
                        has_settlement_paid = True
                continue
            if "합계" in flat_line or "납부총액" in flat_line:
                amounts = _money_words(line)
                if amounts and page_charge_xs:
                    chosen = _closest_amount(amounts, page_charge_xs[0])
                    if chosen:
                        totals.append(chosen[1])
                if len(amounts) > 1 and page_paid_xs:
                    chosen_paid = _closest_amount(amounts, page_paid_xs[0])
                    if chosen_paid:
                        paid_totals.append(chosen_paid[1])
                break
            compact = COMPACT_MONTH_RE.findall(normalize_format_text(text))
            matches = MONTH_RE.findall(normalize_format_text(text)) + compact
            months = [(int(y), int(m)) for y, m in matches]
            calendar_row = False
            if not months:
                labels = MONTH_ONLY_RE.findall(text)
                if labels and period_start:
                    months = [(label_year(int(label)), int(label)) for label in labels]
                    calendar_row = True
            if not months:
                if "합계" in squash(text):
                    amounts = _money_words(line)
                    if amounts and page_charge_xs:
                        chosen = _closest_amount(amounts, page_charge_xs[0])
                        if chosen:
                            totals.append(chosen[1])
                continue
            for ym in months:
                all_months.append(ym)
            target = months
            if calendar_row and period_end is not None:
                # 1~12월 고정 표에서 조회기간 밖 줄은 고지월·월별 금액에 넣지 않는다.
                target = [ym for ym in months if period_start <= ym <= period_end]
                if not target:
                    continue
            target_seen.update(target)
            for ym in target:
                target_words.setdefault(ym, list(line))
            amounts = _money_words(line)
            if not amounts:
                money_numeric = False
                continue
            if any(value < 0 for _, value in amounts):
                nonpositive = True
            if any(value == 0 for _, value in amounts):
                pass
            charge_x = page_charge_xs[0] if page_charge_xs else None
            paid_x = page_paid_xs[0] if page_paid_xs else None
            care_x = page_care_xs[0] if page_care_xs else None
            component_columns = bool(page_health_xs and care_x is not None and page_health_xs[0] != care_x)
            health_x = page_health_xs[0] if component_columns else charge_x
            if not component_columns and grouped:
                # Never the group centre: the 건강보험료 sub-header or no value (review).
                health_x = page_health_xs[0] if page_health_xs else None
            if charge_x is None or (paid_x is None and len(amounts) > 1 and not component_columns):
                money_numeric = False
                continue
            if health_x is None:
                money_numeric = False
                continue
            billed = _closest_amount(amounts, health_x)
            if billed and component_columns and not combined:
                # _closest_amount has no distance bound: when the 건강보험료 cell is unread the nearest
                # remaining cell can be the 장기요양보험료 cell (11-18 A3). 장기요양보험료 is a fraction
                # of 건강보험료, so a row is kept only with a distinct care cell not above a non-negative
                # billed one (negative rows are refunds/adjustments and keep the existing checks).
                care_check = _closest_amount([item for item in amounts if item is not billed], care_x)
                if care_check is None or 0 <= billed[1] < care_check[1]:
                    billed = None
                    money_numeric = False
            paid = _closest_amount(amounts, paid_x) if paid_x is not None else None
            if billed and paid_x is not None and len(amounts) > 1:
                if paid is billed:
                    billed = None
            if paid and paid is not billed:
                for ym in target:
                    paid_monthly[ym] = (paid[1], [paid[0]])
            if billed:
                for ym in target:
                    monthly[ym] = (billed[1], [billed[0]])
                if any(ym in AMOUNT_GUARD_MONTHS for ym in target):
                    others = [item for item in amounts if item is not billed]

                    def centre(item):
                        return (item[0].x0 + item[0].x1) / 2
                    reasons = amount_guard_reasons(
                        billed[1], [value for _, value in others], _column_words(header_lines, centre(billed)),
                        [_column_words(header_lines, centre(item)) for item in others])
                    for ym in target:
                        if ym in AMOUNT_GUARD_MONTHS:
                            guard[ym] = reasons
            if care_x is not None and len(amounts) > 1 and not combined:
                care_amount = _closest_amount([item for item in amounts if item is not billed], care_x)
                if care_amount:
                    for ym in target:
                        care_monthly[ym] = (care_amount[1], [care_amount[0]])
            if page_outside_health_xs and len(amounts) > 1 and not combined:
                outside_amount = _closest_amount(amounts, page_outside_health_xs[0])
                if outside_amount and outside_amount is not billed:
                    for ym in target:
                        outside_health_monthly[ym] = (outside_amount[1], [outside_amount[0]])

    return ((monthly, care_monthly, outside_health_monthly, totals, paid_monthly, paid_totals,
             settlement_billed, settlement_paid, has_settlement_billed, has_settlement_paid, all_months, target_seen,
             target_words, money_numeric, combined, nonpositive),
            {ym: reasons for ym, reasons in guard.items() if ym in monthly})


def put_amount_guard(fields, guard, page_map, sources):
    """Mark 월별고지금액 uncertain (values unchanged) when a target month has a guard reason."""
    reasons = sorted({code for month_reasons in guard.values() for code in month_reasons},
                     key=AMOUNT_GUARD_CODES.index)
    if not reasons:
        return
    fields["월별고지금액상태"] = common.make_field("불확실", "불확실", None, page_map, .9, sources)
    joined = ",".join(reasons)
    fields["월별고지금액불확실사유"] = common.make_field(joined, joined, None, page_map, .9, sources)


def _average(values: dict[tuple[int, int], tuple[int, list[common.Word]]]):
    months = [(2025, 10), (2025, 11), (2025, 12)]
    if not all(month in values for month in months):
        return None, []
    rows = [values[month] for month in months]
    average = (sum(row[0] for row in rows) * 2 + 3) // 6
    return average, [word for _, words in rows for word in words]


#: Label that may precede a 사업장명칭 value; another label right after it is not a value.
_WORKPLACE = re.compile(r"사업장\s*명칭\s*[:：]?\s*(?![^\s|]*(?:납부자|성명|생년월일|가입|번호))[^\s|:：]+")


def _member_type(pages):
    """가입구분 from the personal-information area only (11-18 A4).

    Lines from the monthly table header (or the confirmation sentence) downward and notice
    lines starting with ※ are never evidence: every form prints "※ 직장가입자의 보수월액보험료
    납부의무자는 …" at the bottom. Both marks or none leave the value empty (no guessing).
    """
    kept = []
    for page, result in pages:
        lines = common.page_lines(page, result)
        headers = _month_header(lines)
        for line in lines[:min(headers) if headers else len(lines)]:
            flat = squash(line_text(line))
            if "확인합니다" in flat:
                break
            if not flat.startswith("※"):
                kept.append(line_text(line))
    flat = squash(" ".join(kept))
    work = "직장가입" in flat or any(_WORKPLACE.search(text) for text in kept)
    local = "지역가입" in flat
    return "직장" if work and not local else "지역" if local and not work else None


def _body_issue_date(pages):
    """확인 문장 아래·공단명 위의 무라벨 발급일만 읽는다."""
    for page, result in pages:
        lines = common.page_lines(page, result)
        for index, line in enumerate(lines):
            flat = squash(line_text(line))
            if "확인합니다" not in flat:
                continue
            # 표 인식 결과가 확인 문장·날짜·공단명을 한 줄로 합쳐도 날짜를 읽는다.
            if dates := common.dates_in_line(line):
                return dates[0][0], dates[0][1]
            for candidate in lines[index + 1 : index + 7]:
                flat = squash(line_text(candidate))
                if "국민건강보험공단" in flat:
                    break
                dates = common.dates_in_line(candidate)
                if dates:
                    words = dates[0][1]
                    return dates[0][0], words
    return None, []


def extract(pages: list[tuple[PageImage, OcrResult]], today: date | None = None) -> PaymentResult:
    from . import nhis_payment_gov

    if nhis_payment_gov.recognizes(pages):
        return nhis_payment_gov.extract(pages, today=today)
    del today
    headers = common.page_headers(pages)
    page_map = {page.page: page for page, _ in pages}
    sources = common.sources_by_page(pages)
    validations: list[common.Validation] = []
    warnings: list[str] = []
    fields: dict[str, ExtractedField] = {}
    diagnostics: dict[str, str] = {}

    title = squash(" ".join(result.text for _, result in pages))
    detected = DocType.NHIS_PAYMENT if any(k in title for k in ("보험료납부확인", "건강보험료납부확인")) else DocType.UNKNOWN
    type_confidence = 0.95 if detected == DocType.NHIS_PAYMENT else 0.2
    validations.append(common.Validation("document_type", detected == DocType.NHIS_PAYMENT))

    body_issue, body_issue_words = _body_issue_date(pages)

    for key, label in (("name", "성명"), ("birth", "생년월일"), ("issue", "발급일")):
        value, words, same = common.consensus(headers, key)
        if key == "issue" and value is None and body_issue is not None:
            value, words, same = body_issue, body_issue_words, True
        if key == "issue":
            same = bool(value) and all(h.issue in (None, value) for h in headers)
        validations.append(common.Validation(f"{label}_consistent", bool(value) and same))
        if value is not None:
            rendered = value.isoformat() if isinstance(value, date) else str(value)
            fields[label] = common.make_field(value=rendered, raw=rendered, words=words, pages=page_map,
                                              confidence=common.confidence([same], same), sources=sources)
        elif key in ("name", "birth", "issue"):
            warnings.append(f"{label}을 찾지 못해 담당자 확인이 필요합니다.")
            diagnostics[label] = f"라벨 '{label}' 또는 값을 찾지 못함"

    name, _, names_same = common.consensus(headers, "name")
    validations.append(common.Validation("page_names_match", bool(name) and names_same))
    if not names_same:
        warnings.append("쪽마다 성명이 같지 않거나 일부 쪽에서 찾지 못했습니다.")

    insurance_type = _member_type(pages)
    if insurance_type:
        fields["가입구분"] = common.make_field(insurance_type, insurance_type, None, page_map, 0.9, sources)
    else:
        diagnostics["가입구분"] = "가입구분 또는 직장·지역 표기를 못 찾음"
    validations.append(common.Validation("insurance_type_found", insurance_type is not None))

    (monthly, care_monthly, outside_health_monthly, totals, paid_monthly, paid_totals,
     settlement_billed, settlement_paid, has_settlement_billed, has_settlement_paid,
     all_months, found_months_set,
     month_words, numeric, combined, nonpositive) = parsed = _extract_monthly(pages)
    put_amount_guard(fields, getattr(parsed, "amount_guard", {}), page_map, sources)
    # 한 줄짜리 합성·구형 전자문서에서 고지금액 라벨과 금액이 하나만 있는 경우만
    # 분명한 값으로 남긴다. 두 단 표가 있으면 이 우회 경로를 사용하지 않는다.
    flat_text = " ".join(result.text for _, result in pages)
    charge_headers = _header_x(pages, ("고지금액", "고지보험료"))
    simple_amounts = re.findall(r"고지\s*금액\s*[:：]?\s*([-−]?\s*[\d,]+)", flat_text)
    simple_amount = None
    if not charge_headers and not monthly and len(simple_amounts) == 1:
        simple_amount = simple_amounts[0].replace("−", "-").replace(",", "").replace(" ", "")
        fields["건강보험료"] = common.make_field(simple_amount, simple_amount,
            None, page_map, 0.75, sources)
    if monthly:
        serialized_months = {f"{year}-{month:02d}": str(value[0]) for (year, month), value in sorted(monthly.items())}
        fields["월별고지금액"] = common.make_field(json.dumps(serialized_months, ensure_ascii=False, separators=(",", ":")),
            json.dumps(serialized_months, ensure_ascii=False, separators=(",", ":")),
            [word for _, words in monthly.values() for word in words], page_map, 0.9, sources)
    if care_monthly:
        serialized_care = {f"{year}-{month:02d}": str(value[0]) for (year, month), value in sorted(care_monthly.items())}
        fields["월별장기요양보험료"] = common.make_field(json.dumps(serialized_care, ensure_ascii=False, separators=(",", ":")),
            json.dumps(serialized_care, ensure_ascii=False, separators=(",", ":")),
            [word for _, words in care_monthly.values() for word in words], page_map, 0.9, sources)
    if outside_health_monthly:
        serialized_outside = {f"{year}-{month:02d}": str(value[0]) for (year, month), value in sorted(outside_health_monthly.items())}
        raw_outside = json.dumps(serialized_outside, ensure_ascii=False, separators=(",", ":"))
        fields["월별보수외소득월액_건강"] = common.make_field(raw_outside, raw_outside,
            [word for _, words in outside_health_monthly.values() for word in words], page_map, 0.9, sources)
        outside_average, outside_words = _average(outside_health_monthly)
        if outside_average is not None:
            fields["보수외소득월액_건강"] = common.make_field(str(outside_average), str(outside_average),
                outside_words, page_map, 0.9, sources)
    paid_headers = _header_x(pages, ("납부금액", "납부보험료", "실납부"))
    month_headers = _header_x(pages, MONTH_LABELS)
    found_months = sorted(found_months_set)
    month_text = ",".join(f"{year}-{month:02}" for year, month in found_months)
    if month_text:
        fields["고지월"] = common.make_field(month_text, month_text,
            [w for ym in found_months for w in month_words.get(ym, [])], page_map,
            common.confidence([bool(found_months)]), sources)
    validations.append(common.Validation("monthly_rows_found", bool(found_months)))
    all_amounts_found = bool(found_months) and all(month in monthly for month in found_months)
    validations.append(common.Validation("monthly_amounts_numeric", numeric and all_amounts_found))
    if found_months and not all_amounts_found:
        warnings.append("월별 표에서 고지금액을 읽지 못한 행이 있어 담당자 확인이 필요합니다.")
        diagnostics["건강보험료"] = ("라벨 '고지금액' 못 찾음" if not charge_headers else
                                       "고지금액 후보 2개(열 구분 실패)" if not paid_headers else
                                       "고지월 줄은 찾았으나 고지금액 셀을 못 읽음")
    elif not month_headers:
        diagnostics["건강보험료"] = "열 제목 '월별' 또는 '년월' 못 찾음"
    elif not found_months and MONTH_ONLY_RE.search(" ".join(result.text for _, result in pages)) and not PERIOD_RE.search(normalize_format_text(" ".join(result.text for _, result in pages))):
        warnings.append("기간 줄을 찾지 못해 월별 행에 연도를 붙일 수 없습니다.")
        diagnostics["건강보험료"] = "월별 행 제목은 찾았으나 기간 줄의 시작 연·월을 못 찾음"
    if combined:
        warnings.append("건강보험료와 장기요양보험료의 합계만 보여 건강보험료를 분리하지 못했습니다.")
        diagnostics["건강보험료"] = "건강보험료와 장기요양보험료 합계만 확인됨"
    if nonpositive:
        warnings.append("월별 금액에 음수가 있습니다. 정산 또는 환급 여부를 담당자가 확인해 주세요.")

    average, amount_words = _average(monthly)
    if average is not None and not combined:
        fields["건강보험료"] = common.make_field(str(average), str(average), amount_words, page_map,
            common.confidence([numeric, all_amounts_found, not combined]), sources)
    elif average is None or combined:
        warnings.append("조회 대상 중 찾지 못한 달이 있거나 보험료 열을 구분할 수 없어 담당자 확인이 필요합니다.")
        diagnostics.setdefault("건강보험료", "고지금액 라벨 또는 필요한 월별 금액을 확인하지 못함")

    care_average, care_words = _average(care_monthly)
    if care_average is not None:
        fields["장기요양보험료"] = common.make_field(str(care_average), str(care_average), care_words, page_map,
            common.confidence([len(care_monthly) == 3]), sources)
    else:
        care_headers = _header_x(pages, CARE)
        diagnostics["장기요양보험료"] = ("라벨 '장기요양보험료' 못 찾음" if not care_headers else
                                         "장기요양보험료 월별 셀을 모두 읽지 못함")

    ordered = sorted(all_months)
    continuous = all((b[0] - a[0]) * 12 + b[1] - a[1] == 1 for a, b in zip(ordered, ordered[1:]))
    validations.append(common.Validation("months_continuous", bool(ordered) and continuous))
    if ordered and not continuous:
        warnings.append("월별 표의 년월이 연속되지 않아 담당자 확인이 필요합니다.")

    charge_sum = sum(monthly[m][0] for m in found_months if m in monthly) + (settlement_billed if has_settlement_billed else 0)
    # 여러 쪽에 월 구간이 나뉘고 쪽마다 합계가 인쇄되면 부분합을 합쳐 대조한다.
    total_matches = not totals or (all_amounts_found and sum(totals) == charge_sum)
    validations.append(common.Validation("monthly_total_matches", total_matches))
    if not total_matches:
        warnings.append("월별 고지금액 합계가 표의 합계와 맞지 않습니다.")

    paid_total_matches = not paid_totals or (bool(paid_monthly) and
                                              all(month in paid_monthly for month in found_months) and
                                              sum(paid_totals) == sum(paid_monthly[m][0] for m in found_months) +
                                              (settlement_paid if has_settlement_paid else 0))
    validations.append(common.Validation("paid_total_matches", paid_total_matches))
    if not paid_total_matches:
        warnings.append("월별 납부금액 합계가 표의 납부총액과 맞지 않아 담당자 확인이 필요합니다.")

    return PaymentResult(detected, type_confidence, fields, validations,
                         list(dict.fromkeys(warnings)), diagnostics)
