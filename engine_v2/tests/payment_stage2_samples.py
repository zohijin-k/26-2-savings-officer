"""Authored payment variants; no private dumps or source coordinates are read."""
from . import p2_payment_samples as base


def adjustment(*, optional=False, corrected=False, amounts=None, label="연말정산"):
    cells, size = base.payment(optional=optional, corrected=corrected)
    months = sorted((c for c in cells if c[4].endswith("월") and c[4][:-1].isdigit()), key=lambda c: c[1])
    pitch = months[1][1] - months[0][1]
    y = months[-1][1] + pitch
    sum_y = next(c[1] for c in cells if c[4] == "합계")
    centers = (407, 606, 809, 1010, 1212, 1414, 1616, 1817)
    if amounts is None:
        amounts = [700, 70, 30 if optional else None, 3 if optional else None,
                   300, 30, 20 if optional else None, 2 if optional else None]
    authored = []
    for x0, y0, x1, y1, text, confidence in cells:
        if y0 == sum_y and text != "합계":
            column = min(range(8), key=lambda i: abs(centers[i] - (x0 + x1) / 2))
            text = f"{int(text.replace(',', '')) + (amounts[column] or 0):,}"
        if text != "합계" and x0 == 738:
            text = f"{int(text.replace(',', '')) + sum(v or 0 for v in amounts[4:]):,}"
        dy = pitch if y0 >= sum_y else 0
        authored.append((x0, y0 + dy, x1, y1 + dy, text, confidence))
    authored.append(base.cell(180, y, 276, y + 48, label, 1))
    for center, value in zip(centers, amounts):
        if value is not None:
            authored.append(base.cell(center - 30, y, center + 30, y + 48, str(value), 1))
    return authored, size, y


def clipped_headers():
    cells, size = base.payment()
    group_bottom = max(c[3] for c in cells if c[4] in {"고지금액", "납부금액"})
    upper = [c for c in cells if c[4] == "보수외"]
    selected = {upper[1], upper[3]}
    return [(x0, group_bottom - 1 if c in selected else y0, x1, y1, text, conf)
            for c in cells for x0, y0, x1, y1, text, conf in [c]], size


def fused_headers(*, optional=True):
    # The demonstrated fused shape has printed evidence in all eight columns.
    cells, size = base.payment(optional=optional)
    care = next(c for c in cells if c[4] == "장기요양")
    following_left = min(c[0] for c in cells if c[4] in {"보수외", "소득월액"})
    return [(x0, y0, following_left - 2 if c == care else x1, y1, text, conf)
            for c in cells for x0, y0, x1, y1, text, conf in [c]], size
