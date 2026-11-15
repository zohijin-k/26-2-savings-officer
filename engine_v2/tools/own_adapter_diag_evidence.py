"""Transient, conservative evidence for the value-free adapter diagnostic.

This module never serializes its inputs. Counterfactuals are copies used only
to test an observation; they never replace the measured extraction result.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import math
import re
import unicodedata
from unittest.mock import patch

CODES = ('OK', 'ROUTE_MISMATCH', 'LABEL_NOT_FOUND', 'LABEL_SPACED', 'LABEL_SPLIT',
         'VALUE_NOT_FOUND', 'VALUE_OTHER_LINE', 'LINE_MERGED', 'ORDER',
         'NORMALIZE', 'PATTERN_MISMATCH', 'OCR_CHAR', 'OTHER')
_DASHES = str.maketrans({c: '-' for c in '‐‑‒–—―−﹘﹣－'})


def extract_with_form(page, words, engine):
    """Observe actual dispatch, while delegating the complete baseline path."""
    from engine_v2.extractors import nhis_payment, nhis_payment_gov
    from . import ocr_baseline_runtime as runtime

    forms = []
    legacy, government = nhis_payment.extract, nhis_payment_gov.extract

    def observe_legacy(*args, **kwargs):
        result = legacy(*args, **kwargs)
        forms.append('GOVERNMENT' if result.form_kind == 'government_payment' else 'LEGACY')
        return result

    def observe_government(*args, **kwargs):
        forms.append('GOVERNMENT')
        return government(*args, **kwargs)

    with ExitStack() as stack:
        stack.enter_context(patch.object(nhis_payment, 'extract', observe_legacy))
        stack.enter_context(patch.object(nhis_payment_gov, 'extract', observe_government))
        result, fields = runtime.extract(page, words, engine)
    return result, fields, forms[-1] if forms else 'OTHER'


def comparison(kind, key, reference_raw, observed_raw, observed_kind):
    """Return independent raw typed equality and baseline normalized equality."""
    from .batch_assess import _present, _typed_equal
    from .ocr_baseline_fields import _canonical_field

    if key not in reference_raw or not _present(reference_raw[key]):
        return False, False
    if observed_kind != kind or key not in observed_raw or not _present(observed_raw[key]):
        return False, False
    return (_typed_equal(reference_raw[key], observed_raw[key]),
            _typed_equal(_canonical_field(key, reference_raw[key]),
                         _canonical_field(key, observed_raw[key])))


def _flat(text):
    return ''.join(unicodedata.normalize('NFKC', text).split())


def _bounds(words):
    return (min(w.bbox_px[0] for w in words), min(w.bbox_px[1] for w in words),
            max(w.bbox_px[2] for w in words), max(w.bbox_px[3] for w in words))


def _overlap(a, b):
    x = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    y = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return x * y / max(1e-9, min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1])))


def _adjacent(left, right):
    a, b = left.bbox_px, right.bbox_px
    height = max(a[3]-a[1], b[3]-b[1], 1e-9)
    horizontal = max(a[0]-b[2], b[0]-a[2], 0)
    vertical = max(a[1]-b[3], b[1]-a[3], 0)
    same_row = abs((a[1]+a[3]-b[1]-b[3])/2) <= .6 * height
    same_column = min(a[2], b[2]) > max(a[0], b[0])
    return (same_row and horizontal <= 1.5*height) or (same_column and vertical <= height)


def _groups(page, words, *, cross_lines=False):
    """Adjacent groups only; never concatenate an entire page or distant columns."""
    from engine_v2.pipeline.layout import group_lines, normalize

    from collections import defaultdict, deque
    by_box = defaultdict(deque)
    for word in words:
        by_box[(tuple(word.bbox_px),word.text,word.confidence)].append(word)
    lines = group_lines(normalize(words, page.page, page.pixel_size))
    rows = [[by_box[(tuple(w.px), w.text, w.conf)].popleft() for w in row] for row in lines]
    seen = set()
    for row in rows:
        for start in range(len(row)):
            for end in range(start+1, min(len(row), start+8)+1):
                group = row[start:end]
                if len(group)>1 and not all(_adjacent(a,b) for a,b in zip(group,group[1:])):
                    break
                token = tuple(id(w) for w in group)
                if token not in seen:
                    seen.add(token)
                    yield group
    if cross_lines:
        for index,row in enumerate(rows[:-1]):
            for word in row:
                chain=[word]
                for lower in rows[index+1:index+8]:
                    previous=chain[-1]
                    following=[candidate for candidate in lower if _adjacent(previous,candidate)
                               and min(previous.bbox_px[2],candidate.bbox_px[2]) >
                               max(previous.bbox_px[0],candidate.bbox_px[0])]
                    if len(following)!=1:
                        break
                    chain.append(following[0])
                    yield list(chain)


def _minimal(groups):
    unique = []
    for group in sorted(groups, key=len):
        ids = {id(w) for w in group}
        if not any({id(w) for w in previous} <= ids for previous in unique):
            unique.append(group)
    return unique


def _phrase(page, words, anchor):
    return _minimal(group for group in _groups(page, words, cross_lines=True)
                    if anchor in _flat(''.join(w.text for w in group)))


def _date(text):
    from engine_v2.extractors.nhis_common import parse_date
    return parse_date(unicodedata.normalize('NFKC', text).translate(_DASHES))


def _date_digits(text):
    groups = re.findall(r'\d+', unicodedata.normalize('NFKC', text))
    if len(groups) == 1 and len(groups[0]) == 8:
        groups = [groups[0][:4], groups[0][4:6], groups[0][6:]]
    if len(groups) != 3:
        return None
    try:
        return date(*(int(x) for x in groups))
    except ValueError:
        return None


def _month(text):
    from engine_v2.extractors.nhis_payment import MONTH_RE, COMPACT_MONTH_RE
    text = _flat(text).translate(_DASHES)
    match = MONTH_RE.fullmatch(text) or COMPACT_MONTH_RE.fullmatch(text)
    return (int(match[1]), int(match[2])) if match else None


@dataclass
class _Component:
    mode: str
    value: object
    words: list

    def matches(self, text):
        if self.mode == 'DATE':
            return _date(text) == self.value
        if self.mode == 'MONTH':
            return _month(text) == self.value
        if self.mode == 'MONTH_ONLY':
            return bool(re.fullmatch(rf'0?{self.value}월', _flat(text)))
        return self.value in _flat(text)

    def same_parts(self, text):
        if self.mode == 'DATE':
            return _date_digits(text) == self.value
        return self.matches(text)

    def visible(self,text):
        """A correct literal inside a composite box is not a character error."""
        text=_flat(text)
        digits=''.join(re.findall(r'\d',text))
        if self.mode=='DATE':
            return self.value.strftime('%Y%m%d') in digits
        if self.mode=='MONTH':
            return f'{self.value[0]}{self.value[1]:02}' in digits
        if self.mode=='MONTH_ONLY':
            return bool(re.search(rf'(?<!\d)0?{self.value}월',text))
        return self.matches(text)


@dataclass
class _Anchor:
    text: str
    words: list


def _reference(page, words, key, value):
    """Return only a reference-supported anchor and literal components."""
    groups = list(_groups(page, words))
    if key == '가입구분' and value in ('직장','지역'):
        direct = _minimal(g for g in groups if value+'가입' in _flat(''.join(w.text for w in g)))
        if len(direct) == 1:
            return None, [_Component('LITERAL', value+'가입', direct[0])], False
        if value == '직장':
            labels = _phrase(page, words, '사업장명칭')
            if len(labels) == 1:
                # The legacy reader derives this field from the label/value regex.
                return _Anchor('사업장명칭',labels[0]), [_Component('LITERAL','사업장명칭',labels[0])], False
        return None
    if key == '발급일' and isinstance(value,str):
        try:
            target = date.fromisoformat(value)
        except ValueError:
            return None
        hits = _minimal(g for g in groups if _date(''.join(w.text for w in g)) == target)
        if len(hits) != 1:
            return None
        from engine_v2.extractors import nhis_common as common, nhis_payment_gov
        from .ocr_baseline_fields import prepare_pairs
        pairs=prepare_pairs(page,words,'text_layer')
        anchor=None
        header=common.header_for_page(*pairs[0])
        # Government uses its confirmation block, never a random print-date label.
        if not nhis_payment_gov.recognizes(pairs) and header.issue==target:
            for row in common.page_lines(*pairs[0]):
                boxes={tuple(w.px) for w in row}
                if not all(tuple(w.bbox_px) in boxes for w in hits[0]):
                    continue
                row_words=[w for w in words if tuple(w.bbox_px) in boxes]
                for text in ('발급일자','발급일','발행일','출력일'):
                    labels=_phrase(page,row_words,text)
                    if len(labels)==1:
                        anchor=_Anchor(text,labels[0]);break
                if anchor is not None:
                    break
        # The labeled header path requires the date on the same production line.
        return anchor, [_Component('DATE',target,hits[0])], anchor is not None
    if key == '고지월' and isinstance(value,str):
        months = [_month(item) for item in value.split(',')]
        if not months or any(item is None for item in months):
            return None
        components = []
        for target in months:
            full = _minimal(g for g in groups if _month(''.join(w.text for w in g)) == target)
            if len(full) == 1:
                components.append(_Component('MONTH',target,full[0]))
                continue
            year_present = any(str(target[0]) in _flat(w.text) for w in words)
            only = _minimal(g for g in groups if re.fullmatch(rf'0?{target[1]}월',_flat(''.join(w.text for w in g))))
            if not year_present or len(only) != 1:
                return None
            components.append(_Component('MONTH_ONLY',target[1],only[0]))
        from engine_v2.extractors.nhis_payment import MONTH_LABELS
        anchors = [a for a in MONTH_LABELS if _phrase(page,words,a)]
        label_hits=_phrase(page,words,anchors[0]) if anchors else []
        anchor=_Anchor(anchors[0],label_hits[0]) if len(label_hits)==1 else None
        return anchor, components, False
    return None


def _replay(page, words, kind, key, reference_raw, engine):
    result, raw, _ = extract_with_form(page, words, engine)
    observed_kind = result.detected_doc_type.name if result.detected_doc_type else 'X'
    return comparison(kind,key,reference_raw,raw,observed_kind)[1]


def _normalized_copy(words):
    copied = deepcopy(words)
    for word in copied:
        word.text = unicodedata.normalize('NFKC', word.text).translate(_DASHES)
        word.text = re.sub(r'(?<=[가-힣])\s+(?=[가-힣])','',word.text)
        # Explicit whitespace observation only: no digits, delimiters or field
        # grammar are added. Ordinary baseline NFKC success already returned OK.
        word.text = word.text.replace('\u200b','')
    return copied


def diagnose(page, reference_words, observed_words, kind, key, reference_raw,
             observed_raw, observed_kind, engine, reference_form=None, observed_form=None):
    """Return the first supported observation; uncertainty remains explicit."""
    from .batch_assess import _present
    from .ocr_baseline_fields import _canonical_field, normalize_words

    if key not in reference_raw or not _present(reference_raw[key]):
        return 'REFERENCE_MISSING'
    if comparison(kind,key,reference_raw,observed_raw,observed_kind)[1]:
        return 'OK'
    if reference_form is not None and observed_form is not None and reference_form != observed_form:
        return 'ROUTE_MISMATCH'
    if observed_kind != kind:
        return 'CLASSIFICATION_FAILED'
    if kind != 'NHIS_PAYMENT' or key not in ('가입구분','발급일','고지월'):
        return 'REFERENCE_UNATTRIBUTABLE'
    reference = normalize_words(reference_words)
    observed = normalize_words(observed_words)
    if (not page.pixel_size or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in page.pixel_size)
            or any(len(w.bbox_px)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in w.bbox_px)
                   or not all(b>a for a,b in zip(w.bbox_px[:2],w.bbox_px[2:])) for w in reference+observed)):
        return 'OTHER'
    evidence = _reference(page,reference,key,_canonical_field(key,reference_raw[key]))
    if evidence is None:
        return 'REFERENCE_UNATTRIBUTABLE'
    anchor, components, same_line = evidence
    if anchor is not None:
        hits = _phrase(page,observed,anchor.text)
        if not hits:
            return 'LABEL_NOT_FOUND'
        if len(hits)!=1 or _overlap(_bounds(anchor.words),_bounds(hits[0]))<.3:
            return 'OTHER'
        if not any(anchor.text in unicodedata.normalize('NFKC',w.text) for w in hits[0]):
            if any(anchor.text in _flat(w.text) for w in hits[0]):
                return 'LABEL_SPACED'
            return 'LABEL_SPLIT'
    groups = list(_groups(page,observed))
    exact = [_minimal(g for g in groups if c.matches(''.join(w.text for w in g))) for c in components]
    same_parts = [_minimal(g for g in groups if c.same_parts(''.join(w.text for w in g))) for c in components]
    aligned = [[g for g in _minimal([[w] for w in observed])
                if _overlap(_bounds(c.words),_bounds(g)) >= .3] for c in components]
    visible = [[word for word in observed if component.visible(word.text)]
               for component in components]
    # No content, formatting or aligned substitution candidate exists.
    if any(not a and not b and not c and not d
           for a,b,c,d in zip(exact,same_parts,aligned,visible)):
        return 'VALUE_NOT_FOUND'
    if same_line and anchor and all(len(hits)==1 for hits in exact):
        from engine_v2.pipeline.layout import group_lines, normalize
        normalized = normalize(observed,page.page,page.pixel_size)
        rows = group_lines(normalized)
        anchors = _phrase(page,observed,anchor.text)
        if len(anchors)==1:
            a = _bounds(anchors[0]);v = _bounds(exact[0][0])
            label_rows = [i for i,row in enumerate(rows) if any(tuple(w.px)==tuple(x.bbox_px) for w in row for x in anchors[0])]
            value_rows = [i for i,row in enumerate(rows) if any(tuple(w.px)==tuple(x.bbox_px) for w in row for x in exact[0][0])]
            x_overlap = min(a[2],v[2]) > max(a[0],v[0])
            if label_rows and value_rows and set(label_rows).isdisjoint(value_rows) and x_overlap:
                return 'VALUE_OTHER_LINE'
    # A merged token may be split only at literal boundaries already visible in it.
    # Reference boxes corroborate separate cells; no characters are invented.
    for token in observed:
        pieces = re.split(r'\s+',token.text.strip())
        supported_indexes = [index for index, component in enumerate(components)
                             if any(component.matches(piece) for piece in pieces)]
        supported = [components[index] for index in supported_indexes]
        if len(supported)<2:
            continue
        # A successful replay is not permission to move another column's text
        # into the reference cells. The observed box itself must uniquely
        # corroborate every component that the split would place there.
        if any(len(aligned[index]) != 1 or aligned[index][0][0] is not token or
               _overlap(tuple(token.bbox_px), _bounds(components[index].words)) < .3
               for index in supported_indexes):
            continue
        ref_bounds = [_bounds(c.words) for c in supported]
        if not any(_overlap(a,b)==0 for i,a in enumerate(ref_bounds) for b in ref_bounds[i+1:]):
            continue
        if len(pieces)<2:
            continue
        copied = []
        valid = True
        for word in observed:
            if word is not token:
                copied.append(deepcopy(word));continue
            for piece in pieces:
                matching = [c for c in supported if c.matches(piece)]
                boxes=[_bounds(c.words) for c in matching]
                if not boxes:
                    boxes=[tuple(w.bbox_px) for w in reference if _flat(w.text)==_flat(piece)
                           and _overlap(tuple(token.bbox_px),tuple(w.bbox_px))>=.3]
                if len(boxes)!=1:
                    valid=False;break
                item=deepcopy(word);item.text=piece;item.bbox_px=boxes[0];copied.append(item)
        if valid and copied and _replay(page,copied,kind,key,reference_raw,engine):
            return 'LINE_MERGED'
    # ORDER requires the exact same token multiset and geometry, with a replay
    # proving that input order alone matters. Unequal tokens are never replaced.
    from collections import Counter
    if (Counter(w.text for w in reference)==Counter(w.text for w in observed) and
            Counter(tuple(w.bbox_px) for w in reference)==Counter(tuple(w.bbox_px) for w in observed)):
        order = {(_flat(w.text),tuple(w.bbox_px)):i for i,w in enumerate(reference)}
        if len(order)==len(reference):
            copied=sorted(deepcopy(observed),key=lambda w:order.get((_flat(w.text),tuple(w.bbox_px)),len(order)))
            if copied!=observed and _replay(page,copied,kind,key,reference_raw,engine):
                return 'ORDER'
    copied=_normalized_copy(observed_words)
    if copied!=observed and _replay(page,copied,kind,key,reference_raw,engine):
        return 'NORMALIZE'
    if all(len(hits)==1 for hits in same_parts) and not all(exact):
        if all(_overlap(_bounds(c.words),_bounds(hits[0]))>=.3 for c,hits in zip(components,same_parts)):
            return 'PATTERN_MISMATCH'
    # Only one spatially corroborated candidate can support a character error.
    if any(not hits for hits in exact):
        supported=True
        for component, matches, candidates, literals in zip(components,exact,aligned,visible):
            if len(matches)==1 and _overlap(_bounds(component.words),_bounds(matches[0]))>=.3:
                continue
            if (literals or len(candidates)!=1 or component.same_parts(''.join(w.text for w in candidates[0]))
                    or component.visible(''.join(w.text for w in candidates[0]))):
                supported=False;break
        if supported:
            return 'OCR_CHAR'
    return 'OTHER'
