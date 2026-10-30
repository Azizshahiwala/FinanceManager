"""
charts.py — server-side inline SVG chart helpers.

Both bar_chart() and donut_chart() return an SVG string that renders
identically in a browser and in WeasyPrint (no JavaScript needed).

Palette matches the dashboard:
  ['#E85D91', '#17161A', '#2E9E6E', '#E2645B', '#F3AFC9', '#837C70', '#D9CFB8']
"""
from __future__ import annotations

from html import escape

PALETTE = ['#E85D91', '#17161A', '#2E9E6E', '#E2645B', '#F3AFC9', '#837C70', '#D9CFB8']
INC_COLOR = '#78c894'
EXP_COLOR = '#f1ad8b'


def _safe(v) -> str:
    return escape(str(v))


def bar_chart(
    labels: list[str],
    income: list[float],
    expense: list[float],
    width: int = 700,
    height: int = 260,
) -> str:
    """
    Grouped bar chart (income green, expense orange) with labels on the x-axis.
    Returns an inline SVG string.
    """
    if not labels:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="700" height="120"><text x="350" y="60" text-anchor="middle" fill="#888" font-size="14">No data for this period.</text></svg>'

    pad_left = 58
    pad_right = 18
    pad_top = 18
    pad_bottom = 52  # room for x-axis labels
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    max_val = max((max(income, default=0), max(expense, default=0)), default=1) or 1
    n = len(labels)
    group_w = chart_w / n
    bar_w = max(4, min(28, group_w * 0.36))
    gap = bar_w * 0.4

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'style="font-family:\'Plus Jakarta Sans\',sans-serif;">'
    )

    # ── Grid lines ────────────────────────────────────────────────────────
    for frac in (0.25, 0.5, 0.75, 1.0):
        y = pad_top + chart_h * (1 - frac)
        val = max_val * frac
        lines.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" '
            f'x2="{width - pad_right}" y2="{y:.1f}" '
            f'stroke="#eef1ec" stroke-width="1"/>'
        )
        label_text = f'₹{val:,.0f}'
        lines.append(
            f'<text x="{pad_left - 6}" y="{y + 4:.1f}" '
            f'text-anchor="end" font-size="9" fill="#879087">'
            f'{_safe(label_text)}</text>'
        )

    # ── Bars ─────────────────────────────────────────────────────────────
    for i, (label, inc_val, exp_val) in enumerate(zip(labels, income, expense)):
        cx = pad_left + (i + 0.5) * group_w
        # income bar (left)
        inc_h = (inc_val / max_val) * chart_h
        x_inc = cx - gap / 2 - bar_w
        y_inc = pad_top + chart_h - inc_h
        if inc_h > 0:
            lines.append(
                f'<rect x="{x_inc:.2f}" y="{y_inc:.2f}" '
                f'width="{bar_w:.2f}" height="{inc_h:.2f}" '
                f'fill="{INC_COLOR}" rx="3"/>'
            )
        # expense bar (right)
        exp_h = (exp_val / max_val) * chart_h
        x_exp = cx + gap / 2
        y_exp = pad_top + chart_h - exp_h
        if exp_h > 0:
            lines.append(
                f'<rect x="{x_exp:.2f}" y="{y_exp:.2f}" '
                f'width="{bar_w:.2f}" height="{exp_h:.2f}" '
                f'fill="{EXP_COLOR}" rx="3"/>'
            )
        # x-axis label
        label_str = label if len(label) <= 7 else label[:6] + '…'
        lines.append(
            f'<text x="{cx:.2f}" y="{pad_top + chart_h + 16:.1f}" '
            f'text-anchor="middle" font-size="9" fill="#879087">'
            f'{_safe(label_str)}</text>'
        )

    # ── Legend ────────────────────────────────────────────────────────────
    ly = height - 12
    lines.append(
        f'<rect x="{pad_left}" y="{ly - 8}" width="10" height="10" fill="{INC_COLOR}" rx="2"/>'
        f'<text x="{pad_left + 14}" y="{ly:.0f}" font-size="10" fill="#667166">Income</text>'
        f'<rect x="{pad_left + 80}" y="{ly - 8}" width="10" height="10" fill="{EXP_COLOR}" rx="2"/>'
        f'<text x="{pad_left + 94}" y="{ly:.0f}" font-size="10" fill="#667166">Expenses</text>'
    )

    lines.append('</svg>')
    return '\n'.join(lines)


def donut_chart(
    categories: list[dict],
    width: int = 260,
    height: int = 260,
) -> str:
    """
    Donut chart for expense-by-category.
    `categories` is a list of dicts with keys: category, total (float), pct, color.
    Returns an inline SVG string.
    """
    totals = [float(c['total']) for c in categories]
    grand = sum(totals) or 1

    cx = width // 2
    cy = height // 2
    r_outer = min(cx, cy) - 10
    r_inner = r_outer * 0.58

    import math

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )

    if not categories:
        lines.append(
            f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" '
            f'font-size="13" fill="#888">No data</text>'
        )
        lines.append('</svg>')
        return '\n'.join(lines)

    angle = -math.pi / 2  # start at top

    for cat, total in zip(categories, totals):
        sweep = (total / grand) * 2 * math.pi
        end_angle = angle + sweep
        large = 1 if sweep > math.pi else 0
        color = cat.get('color', PALETTE[0])

        x1 = cx + r_outer * math.cos(angle)
        y1 = cy + r_outer * math.sin(angle)
        x2 = cx + r_outer * math.cos(end_angle)
        y2 = cy + r_outer * math.sin(end_angle)
        ix1 = cx + r_inner * math.cos(end_angle)
        iy1 = cy + r_inner * math.sin(end_angle)
        ix2 = cx + r_inner * math.cos(angle)
        iy2 = cy + r_inner * math.sin(angle)

        d = (
            f'M {x1:.3f} {y1:.3f} '
            f'A {r_outer} {r_outer} 0 {large} 1 {x2:.3f} {y2:.3f} '
            f'L {ix1:.3f} {iy1:.3f} '
            f'A {r_inner} {r_inner} 0 {large} 0 {ix2:.3f} {iy2:.3f} Z'
        )
        lines.append(f'<path d="{d}" fill="{color}" stroke="#fff" stroke-width="2"/>')
        angle = end_angle

    lines.append('</svg>')
    return '\n'.join(lines)
