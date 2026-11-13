"""Authored fictitious DocumentAI corpus, transformations and numeric reports.

Only this module creates source images. No directory of user inputs is scanned.
Source helpers are existing synthetic fixture providers, never private samples.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import tempfile

import numpy as np
import pymupdf
from PIL import Image, ImageFilter

from .make_synth_eval import phone_capture

CONDITIONS = ("original", "monochrome", "rotate_plus5", "rotate_minus5", "rotate90", "low_resolution", "phone")
DOCS = ("resident_abstract", "nhis_payment", "nhis_qualification", "nhis_acquisition_loss", "insurance_4")
ISSUE = "2026-03-03"
TODAY = "2026-11-13"


@dataclass
class Source:
    doc: str
    # Each page is (cells of x,y,text,font-size in PDF points, page size).
    pages: list
    truth: dict
    identity: dict


def _percent(cells, *, fontsize=8):
    return [(x * 5.95, y * 8.42, text, fontsize) for x, y, text in cells]


def sources(sample=0):
    """Truth is independent of OCR/extraction. Each repetition changes names."""
    from engine_v2.tests import nhis_form_samples as forms
    from engine_v2.tests import p2_payment_samples as payment
    from engine_v2.tests.test_resident_abstract import header, row, table_head, W, H
    name = ("가짜이름", "가상인물", "가짜시험", "가상시험")[sample % 4]
    identity = {"name": name, "birth": "1990-01-01"}
    common = {"성명": name, "생년월일": "1990-01-01", "발급일": ISSUE}
    address = "전북특별자치도 전주시 완산구 가상동 456"
    words = header(1, 1, name=name, issue="2026년03월03일", applicant=f"신청인: {name} (1999-01-01)")
    words += table_head(31.8) + row(34.4, 1, address, "2020-01-01", "2020-01-01")
    # The header fixture's name/relationship and RRN are fictitious source data.
    resident_cells = []
    for word in words:
        x0, y0, x1, y1 = word.bbox_px
        text = word.text.replace("김전북 본인", name + " 본인").replace("990101-1234567", "990101-1******")
        fontsize = 8 if y0 / H > .12 else 9
        resident_cells.append((x0 / W * 595, (y0 / H * 842) + fontsize, text, fontsize))
    yield Source("resident_abstract", [(resident_cells, (595, 842))],
                 {"name": name, "birth_date": "1999-01-01", "issue_date": ISSUE,
                  "applicant_name": name, "applicant_birth_date": "1999-01-01",
                  "current_address": address, "address_history_count": 1},
                 {"name": name, "birth": "1999-01-01"})

    cells, (width, height) = payment.payment(name=name)
    font = pymupdf.Font("cjk")
    rendered = [(530, 30, "1 / 1", 8)]
    for x0, y0, x1, y1, text, _ in cells:
        # Synthetic stamp artifacts are not content and are excluded at authorship.
        if text in {"I상", "가상"}:
            continue
        box_width = (x1 - x0) / width * 595
        size = min((y1 - y0) / height * 842 * .82,
                   box_width / max(font.text_length(text, fontsize=1), .1))
        rendered.append((x0 / width * 595, y1 / height * 842 - size * .1, text, size))
    billed = {f"2025-{month:02}": str({10: 100000, 11: 20000, 12: 30000}.get(month, 0)) for month in range(1, 13)}
    care = {month: str(int(amount) // 10) for month, amount in billed.items()}
    yield Source("nhis_payment", [(rendered, (595, 842))],
                 dict(common, 사업장명칭="", 납부자번호="00000000000", 문서확인번호="0000-0000-0000-00000",
                      용도구분="납부확인용", 조회기간=["2025-10", "2025-12"], 월별고지금액=billed,
                      월별장기요양보험료=care, 건강보험료="50000", 장기요양보험료="5000", 납부총액="165000"), identity)

    def rename(cells):
        return [(x, y, text.replace(forms.NAME, name)) for x, y, text in cells]
    members = [{"성명": name, "생년월일": "1990-01-01", "자격취득일": "2020-01-01", "자격상실일": ""},
               {"성명": "가짜가족", "생년월일": "2001-01-01", "자격취득일": "2021-01-01", "자격상실일": ""}]
    yield Source("nhis_qualification", [(_percent(rename(forms.qualification_cells())), (595, 842))],
                 dict(common, 가구원수="2", 가구원목록=members, 자격확인요청일="2026-03-01", 사업장관리번호="00000000000"), identity)
    yield Source("nhis_acquisition_loss", [(_percent(rename(forms.acquisition_cells())), (595, 842))],
                 dict(common, 가입구분="직장", 취득일="2024-01-01", 변동내역="최근 5년 포함"), identity)
    insurance_rows = []
    for insurance, category in (("국민연금", "사업장가입자"), ("건강보험", "직장가입자"), ("산재보험", "직장가입자"), ("고용보험", "직장가입자")):
        insurance_rows.append({"보험": insurance, "성명": name, "가입자종별": category,
                               "사업장관리번호": "00000000000", "사업장명칭": "가짜상사가짜",
                               "자격취득일": "2020-01-01", "신고접수일": "2020-01-02", "상태": "가입"})
    yield Source("insurance_4", [(_percent(rename(forms.insurance_portal_cells())), (595, 842))],
                 dict(common, 발급번호="00000000000000", 가입내역=insurance_rows), identity)


def pdf_bytes(source):
    with pymupdf.open() as document:
        font = pymupdf.Font("cjk")
        for cells, size in source.pages:
            page = document.new_page(width=size[0], height=size[1])
            for x, y, text, fontsize in cells:
                writer = pymupdf.TextWriter(page.rect)
                writer.append((x, y), text, font=font, fontsize=fontsize)
                writer.write_text(page)
            # Visible authorship mark outside the form's semantic regions.
            page.insert_text((40, size[1] - 12), "SYNTHETIC EVALUATION ONLY - FICTITIOUS", fontsize=7)
        return document.tobytes()


def render(source):
    with pymupdf.open(stream=pdf_bytes(source), filetype="pdf") as document:
        return [Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                for page in document for pix in [page.get_pixmap(dpi=300, alpha=False)]]


def transform(image, condition, rng):
    if condition == "original":
        return image.copy()
    if condition == "monochrome":
        return image.convert("L").point(lambda p: 255 if p >= 180 else 0, mode="1").convert("RGB")
    if condition in {"rotate_plus5", "rotate_minus5"}:
        return image.rotate(5 if condition == "rotate_plus5" else -5, Image.Resampling.BICUBIC,
                            expand=True, fillcolor="white")
    if condition == "rotate90":
        return image.transpose(Image.Transpose.ROTATE_90)
    if condition == "low_resolution":
        return image.resize((round(image.width * .24), round(image.height * .24)), Image.Resampling.LANCZOS)
    if condition == "phone":
        return phone_capture(image, "phone_strong", rng)[0]
    raise ValueError("unknown condition")


def defects(source):
    """Mutate printed content, never engine facts/verdicts after recognition."""
    for label, old, new in (("issued_too_early", "2026", "2024"),
                            ("issued_after_application", "2026", "2027")):
        result = deepcopy(source)
        for cells, _ in result.pages:
            for index, (x, y, text, size) in enumerate(cells):
                # Change source date occurrences only; preserve unrelated identity dates.
                cells[index] = (x, y, text.replace(old, new), size)
        field = "issue_date" if source.doc == "resident_abstract" else "발급일"
        result.truth[field] = "2024-03-03" if label == "issued_too_early" else "2027-03-03"
        yield label, result
    result = deepcopy(source)
    result.identity = {"name": "가짜타인", "birth": "1988-02-02"}
    yield "identity_mismatch", result
    result = deepcopy(source)
    # A visible missing-page claim is a content defect, not a fabricated OCR finding.
    for cells, _ in result.pages:
        for index, (x, y, text, size) in enumerate(cells):
            if text.replace(" ", "") in {"1/1"}:
                cells[index] = (x, y, "1 / 2", size)
    yield "pages_incomplete", result
    # Wrong-type upload: actual content and truth stay intact; expected slot changes.
    result = deepcopy(source)
    yield "wrong_document_type", result
    if source.doc == "resident_abstract":
        result = deepcopy(source)
        for cells, _ in result.pages:
            cells[:] = [cell for cell in cells if cell[2] != "2020-01-01"]
        yield "missing_address_dates", result
    if source.doc == "nhis_payment":
        result = deepcopy(source)
        for cells, _ in result.pages:
            cells[:] = [cell for cell in cells if cell[2] != "11월"]
        yield "missing_billing_months", result
    yield "low_resolution", deepcopy(source)
    yield "low_image_quality", deepcopy(source)
    yield "unreadable_file", deepcopy(source)


def _aggregate(rows):
    fields = defaultdict(lambda: {"count": 0, "correct": 0, "edits": 0, "reference_chars": 0})
    normals = [row for row in rows if row["defect"] == "none"]
    damaged = [row for row in rows if row["defect"] != "none"]
    codes = Counter(code for row in normals for code in set(row.get("confirmed_reupload_codes", [])))
    seconds = sum(row.get("seconds", 0) for row in rows)
    pages = sum(row.get("pages", 0) for row in rows)
    normal_pages = sum(row.get("pages", 0) for row in normals)
    defect_pages = sum(row.get("pages", 0) for row in damaged)
    normal_seconds = sum(row.get("seconds", 0) for row in normals)
    defect_seconds = sum(row.get("seconds", 0) for row in damaged)
    for row in normals:
        for field, metric in row["fields"].items():
            bucket = fields[field]
            bucket["count"] += 1
            bucket["correct"] += metric["match"] == "O"
            bucket["edits"] += metric["edits"]
            bucket["reference_chars"] += metric["reference_chars"]
    for metric in fields.values():
        metric["accuracy"] = metric["correct"] / metric["count"]
        metric["cer"] = metric["edits"] / max(metric["reference_chars"], 1)
    count = sum(metric["count"] for metric in fields.values())
    correct = sum(metric["correct"] for metric in fields.values())
    edits = sum(metric["edits"] for metric in fields.values())
    chars = sum(metric["reference_chars"] for metric in fields.values())
    false_rejects = sum(bool(row.get("confirmed_reupload_codes")) for row in normals)
    false_accepts = sum(row.get("status") == "PASS" for row in damaged)
    return {"attempted": len(rows), "completed": sum(row["failed"] == "X" for row in rows),
            "failed": sum(row["failed"] == "O" for row in rows), "normal_count": len(normals),
            "defect_count": len(damaged), "type_correct": sum(row.get("type_match") == "O" for row in normals),
            "type_accuracy": sum(row.get("type_match") == "O" for row in normals) / len(normals) if normals else None,
            "field_count": count, "field_correct": correct, "field_accuracy": correct / count if count else None,
            "cer": edits / max(chars, 1) if count else None, "fields": dict(fields),
            "false_reject_count": false_rejects, "false_reject_rate": false_rejects / len(normals) if normals else None,
            "false_reject_codes": dict(sorted(codes.items())),
            "false_accept_count": false_accepts, "false_accept_rate": false_accepts / len(damaged) if damaged else None,
            "status_counts": dict(Counter(row.get("status", "X") for row in rows)),
            "normal_status_counts": dict(Counter(row.get("status", "X") for row in normals)),
            "defect_status_counts": dict(Counter(row.get("status", "X") for row in damaged)),
            "normal_pages": normal_pages, "defect_pages": defect_pages,
            "normal_seconds": normal_seconds, "defect_seconds": defect_seconds,
            "normal_seconds_per_page": normal_seconds / normal_pages if normal_pages else None,
            "defect_seconds_per_page": defect_seconds / defect_pages if defect_pages else None,
            "pages": pages, "seconds": round(seconds, 6),
            "seconds_per_page": seconds / pages if pages else None}


def summarize(rows):
    def groups(key, values, pool=None):
        return {value: _aggregate([row for row in (rows if pool is None else pool) if row[key] == value]) for value in values}
    normals = [row for row in rows if row["defect"] == "none"]
    return {"overall": _aggregate(rows), "by_document": groups("doc", DOCS),
            "by_condition": groups("condition", CONDITIONS, normals),
            "by_cell": {doc: {condition: _aggregate([row for row in rows if row["doc"] == doc and row["condition"] == condition and row["defect"] == "none"])
                              for condition in CONDITIONS} for doc in DOCS},
            "by_defect": groups("defect", sorted({row["defect"] for row in rows if row["defect"] != "none"}))}


def markdown(report):
    summary = report["summary"]
    def pct(value):
        return "—" if value is None else f"{value * 100:.2f}%"
    def num(value):
        return "—" if value is None else f"{value:.4f}"
    lines = ["# DocumentAI synthetic measurement", "", f"Seed: {report['seed']}; repetitions per cell: {report['samples']}; own OCR only.",
             "", "NFC and Unicode-whitespace removal apply to CER only; field accuracy uses exact semantic values. Structured lists retain order. Insurance geometry/confidence metadata are excluded. Missing fields count as errors. Rates include failed attempts; NEEDS_REVIEW is neither PASS nor confirmed FAIL.",
             "", "Normal means correct document content before image transformations. Low-resolution/phone rejection can be a valid quality-policy action. This small synthetic corpus is diagnostic, not a population accuracy estimate. Reference source preflight is separate from OCR measurement.",
             "", "Timing includes image/PDF read, own OCR, extraction, file evidence and upload assessment; excludes generation and metrics. First measured case includes model initialization (cold start). Headline/type/condition timing uses normal-content pages only; all-attempt and defect times are stored separately in JSON. Rejected unreadable bytes are excluded from normal timing.", "",
             "## Overall and document types", "", "| Type | Normal n | Defect n | Field exact | CER | Type accuracy | False reject | False accept | Failed | Normal s/page |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for label, group in [("overall", summary["overall"]), *summary["by_document"].items()]:
        lines.append(f"| {label} | {group['normal_count']} | {group['defect_count']} | {pct(group['field_accuracy'])} | {num(group['cer'])} | {pct(group['type_accuracy'])} | {pct(group['false_reject_rate'])} ({group['false_reject_count']}/{group['normal_count']}) | {pct(group['false_accept_rate'])} ({group['false_accept_count']}/{group['defect_count']}) | {group['failed']} | {num(group['normal_seconds_per_page'])} |")
    lines += ["", "## Complete type × condition matrix", "", "| Type | Condition | n | Exact | CER | Type | Reupload FAIL | Status (PASS/review/FAIL) | Failed | s/page |", "|---|---|---:|---:|---:|---:|---:|---|---:|---:|"]
    for doc, conditions in summary["by_cell"].items():
        for condition, group in conditions.items():
            counts = group["normal_status_counts"]
            lines.append(f"| {doc} | {condition} | {group['normal_count']} | {pct(group['field_accuracy'])} | {num(group['cer'])} | {pct(group['type_accuracy'])} | {group['false_reject_count']} | {counts.get('PASS',0)}/{counts.get('NEEDS_REVIEW',0)}/{counts.get('FAIL',0)} | {group['failed']} | {num(group['seconds_per_page'])} |")
    lines += ["", "## Fields by document", "", "| Type | Field | Correct/n | Exact | CER |", "|---|---|---:|---:|---:|"]
    for doc, group in summary["by_document"].items():
        for field, metric in group["fields"].items():
            lines.append(f"| {doc} | {field} | {metric['correct']}/{metric['count']} | {pct(metric['accuracy'])} | {num(metric['cer'])} |")
    lines += ["", "## Confirmed normal reupload FAIL codes", "", "| Code | Documents |", "|---|---:|"]
    from .documentai_bench import REUPLOAD_CODES
    for code in sorted(REUPLOAD_CODES):
        lines.append(f"| {code} | {summary['overall']['false_reject_codes'].get(code,0)} |")
    lines += ["", "Code totals may exceed document totals. Only code severity FAIL with final document FAIL counts.", "", "## Defects", "", "| Defect | n | PASS (false accept) | NEEDS_REVIEW | FAIL | Execution errors |", "|---|---:|---:|---:|---:|---:|"]
    for defect, group in summary["by_defect"].items():
        counts = group["defect_status_counts"]
        lines.append(f"| {defect} | {group['defect_count']} | {group['false_accept_count']} | {counts.get('NEEDS_REVIEW',0)} | {counts.get('FAIL',0)} | {group['failed']} |")
    lines += ["", "A zero false-accept rate can reflect extensive manual review. It does not establish successful automatic defect recognition.",
              "", "## Reupload codes by normal type × condition", "", "| Type | Condition | Code | Documents |", "|---|---|---|---:|"]
    for doc, conditions in summary["by_cell"].items():
        for condition, group in conditions.items():
            for code, count in group["false_reject_codes"].items():
                lines.append(f"| {doc} | {condition} | {code} | {count} |")
    lines += ["", "Unlisted type/condition/code combinations have zero occurrences.", "", "## Fields by type × condition", "",
              "| Type | Condition | Field | Correct/n | Exact | CER |", "|---|---|---|---:|---:|---:|"]
    for doc, conditions in summary["by_cell"].items():
        for condition, group in conditions.items():
            for field, metric in group["fields"].items():
                lines.append(f"| {doc} | {condition} | {field} | {metric['correct']}/{metric['count']} | {pct(metric['accuracy'])} | {num(metric['cer'])} |")
    lines += ["", "## Weakest diagnostic groups", ""]
    for dimension in ("by_document", "by_condition"):
        lines.append(f"### {dimension}")
        lines += ["", "| Group | Field exact | CER | Type accuracy | n |", "|---|---:|---:|---:|---:|"]
        for label, group in sorted(summary[dimension].items(), key=lambda item: (item[1]["field_accuracy"] if item[1]["field_accuracy"] is not None else 1, -(item[1]["cer"] or 0)))[:5]:
            lines.append(f"| {label} | {pct(group['field_accuracy'])} | {num(group['cer'])} | {pct(group['type_accuracy'])} | {group['normal_count']} |")
        lines.append("")
    weakest = [(doc, field, metric) for doc, group in summary["by_document"].items() for field, metric in group["fields"].items()]
    lines += ["### Fields", "", "| Type | Field | Correct/n | CER |", "|---|---|---:|---:|"]
    for doc, field, metric in sorted(weakest, key=lambda item: (item[2]["accuracy"], -item[2]["cer"], item[0], item[1]))[:15]:
        lines.append(f"| {doc} | {field} | {metric['correct']}/{metric['count']} | {num(metric['cer'])} |")
    lines += ["", "## Improvement candidates (not implemented)", "", "- Investigate the lowest-ranked type/condition cells using further independent synthetic templates and fonts before drawing production conclusions.",
              "- Separate orientation, title recognition and coordinate/table-layout losses through the reported classification and field metrics.",
              "- Inspect semantic table fields with high CER and missing-field rates; test row/column completeness with additional authored layouts.",
              "- Calibrate quality-policy reuploads separately from text-content mistakes, especially for intentionally small originals and phone photographs.",
              "- Increase independent templates and sample diversity; report warm/cold timing and confidence intervals in a future evaluation.",
              "", "No OCR, extractor or verdict logic was changed. Private-document mode was not executed on real documents.", ""]
    return "\n".join(lines)


def run(output: Path, samples=1, seed=20261113):
    """Execute every matrix cell and content defect; persist only safe metrics."""
    from .documentai_bench import measure, failure_result
    if not 1 <= samples <= 20:
        raise ValueError("invalid sample count")
    rows = []
    rng = np.random.default_rng(seed)
    def checked_measure(path, source, doc=None, truth=None):
        import time
        started = time.perf_counter()
        kind = doc or source.doc
        expected = source.truth if truth is None else truth
        try:
            return measure(path, kind, expected, identity=source.identity)
        except Exception:
            return failure_result(kind, expected, time.perf_counter() - started)
    with tempfile.TemporaryDirectory(prefix="documentai-synthetic-") as directory:
        directory = Path(directory)
        for repetition in range(samples):
            for source in sources(repetition):
                images = render(source)
                for condition in CONDITIONS:
                    image = transform(images[0], condition, rng)
                    path = directory / "synthetic.png"
                    image.save(path)
                    result = checked_measure(path, source)
                    rows.append({"doc": source.doc, "condition": condition, "defect": "none", "sample": repetition, **result})
                    print(f"{len(rows)} {source.doc} {condition} {result['failed']}", flush=True)
                for defect, damaged in defects(source):
                    path = directory / "synthetic.png"
                    if defect == "unreadable_file":
                        path.write_bytes(b"FICTITIOUS INVALID IMAGE")
                    else:
                        image = render(damaged)[0]
                        if defect == "low_resolution":
                            image = image.resize((400, 566), Image.Resampling.LANCZOS)
                        if defect == "low_image_quality":
                            image = image.resize((200, 280)).filter(ImageFilter.GaussianBlur(3)).resize(image.size)
                        image.save(path)
                    expected_doc = damaged.doc
                    if defect == "wrong_document_type":
                        expected_doc = DOCS[(DOCS.index(source.doc) + 1) % len(DOCS)]
                    # Keep field truth for the actual document; type match in this group is not aggregated.
                    result = checked_measure(path, damaged, expected_doc, damaged.truth if expected_doc == damaged.doc else {})
                    rows.append({"doc": source.doc, "condition": "original", "defect": defect, "sample": repetition, **result})
                    print(f"{len(rows)} {source.doc} {defect} {result['failed']}", flush=True)
    report = {"schema_version": 1, "seed": seed, "samples": samples, "rows": rows, "summary": summarize(rows)}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    return report
