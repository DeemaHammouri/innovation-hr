"""PDF from a Doc. Branded (navy and blue, the IA mark), English, Arabic (right to left, shaped) or both, with a DRAFT watermark."""
import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, PageTemplate, Spacer, Table, TableStyle

from . import model
from .text import pair_text, visual

FONTS = Path(__file__).parent / "fonts"
NAVY, BLUE, INK, MUTED, LINE, TINT = colors.HexColor("#0b1f44"), colors.HexColor("#007aff"), colors.HexColor("#14213d"), colors.HexColor("#5b6b88"), colors.HexColor("#d9e0ee"), colors.HexColor("#e8f1ff")
REGULAR, BOLD = "Plex", "Plex-Bold"
_registered = False


def register_fonts():
    global _registered
    if not _registered:
        pdfmetrics.registerFont(TTFont(REGULAR, str(FONTS / "IBMPlexSansArabic-Regular.ttf")))
        pdfmetrics.registerFont(TTFont(BOLD, str(FONTS / "IBMPlexSansArabic-Bold.ttf")))
        pdfmetrics.registerFontFamily(REGULAR, normal=REGULAR, bold=BOLD, italic=REGULAR, boldItalic=BOLD)
        _registered = True


def width_of(text, font, size, rtl):
    return pdfmetrics.stringWidth(visual(text, rtl), font, size)


def wrap(text, font, size, max_width, rtl):
    """Greedy word wrap on the logical text; each finished line is shaped and ordered on its own, so Arabic breaks where it should."""
    lines = []
    for raw in str(text or "").split("\n"):
        words, line = raw.split(" "), ""
        for word in words:
            trial = f"{line} {word}".strip() if line else word
            if line and width_of(trial, font, size, rtl) > max_width:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
    return lines


class Txt(Flowable):
    """Text that wraps to the space it is given. align: start (right in Arabic), end, center."""

    def __init__(self, text, rtl, size=9.5, bold=False, color=INK, align="start", leading=None):
        super().__init__()
        self.text, self.rtl, self.size, self.bold, self.color, self.align = text, rtl, size, bold, color, align
        self.font = BOLD if bold else REGULAR
        self.leading = leading or size * 1.45
        self.lines = []

    def wrap(self, aw, ah):
        self.lines = wrap(self.text, self.font, self.size, aw, self.rtl)
        self.width, self.height = aw, max(1, len(self.lines)) * self.leading
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFont(self.font, self.size)
        c.setFillColor(self.color)
        for i, line in enumerate(self.lines):
            shown = visual(line, self.rtl)
            w = pdfmetrics.stringWidth(shown, self.font, self.size)
            side = self.align
            if side == "start":
                side = "right" if self.rtl else "left"
            elif side == "end":
                side = "left" if self.rtl else "right"
            x = {"left": 0, "right": self.width - w, "center": (self.width - w) / 2}[side]
            c.drawString(x, self.height - (i + 1) * self.leading + self.size * 0.28, shown)


class Img(Flowable):
    def __init__(self, data, w, h):
        super().__init__()
        self.data, self.width, self.height = data, w, h

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        self.canv.drawImage(ImageReader(io.BytesIO(self.data)), 0, 0, self.width, self.height, mask="auto", preserveAspectRatio=True, anchor="c")


def draw_logo(c, x, y, size):
    """The IA mark: a blue rounded square with the two letters."""
    c.setFillColor(BLUE)
    c.roundRect(x, y, size, size, size * 0.24, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(BOLD, size * 0.44)
    c.drawCentredString(x + size / 2, y + size * 0.3, "IA")


def build_pdf(doc, lang="en", draft=None):
    """Returns the PDF bytes. `draft` overrides doc.watermark when given."""
    register_fonts()
    rtl = lang == "ar"
    show_draft = doc.watermark if draft is None else draft
    L = lambda pair: pair_text(pair, lang)  # noqa: E731
    out = io.BytesIO()
    page_w, page_h = A4
    margin = 18 * mm
    inner = page_w - 2 * margin
    footer_text = doc.footer or L(doc.company)

    def on_page(c, d):
        c.saveState()
        # brand band
        c.setFillColor(NAVY)
        c.rect(0, page_h - 24 * mm, page_w, 24 * mm, stroke=0, fill=1)
        logo_x = page_w - margin - 13 * mm if rtl else margin
        draw_logo(c, logo_x, page_h - 19 * mm, 13 * mm)
        c.setFillColor(colors.white)
        c.setFont(BOLD, 12)
        name = visual(L(doc.company), rtl)
        if rtl:
            c.drawRightString(logo_x - 4 * mm, page_h - 13.5 * mm, name)
        else:
            c.drawString(logo_x + 17 * mm, page_h - 13.5 * mm, name)
        c.setFont(REGULAR, 8.5)
        c.setFillColor(colors.HexColor("#9fb0cc"))
        sub = visual(L(doc.title), rtl)
        if rtl:
            c.drawRightString(logo_x - 4 * mm, page_h - 19 * mm, sub)
        else:
            c.drawString(logo_x + 17 * mm, page_h - 19 * mm, sub)
        if doc.number:
            c.setFont(BOLD, 10)
            c.setFillColor(colors.white)
            if rtl:
                c.drawString(margin, page_h - 14 * mm, doc.number)
            else:
                c.drawRightString(page_w - margin, page_h - 14 * mm, doc.number)
        # footer
        c.setStrokeColor(LINE)
        c.line(margin, 14 * mm, page_w - margin, 14 * mm)
        c.setFillColor(MUTED)
        c.setFont(REGULAR, 8)
        if rtl:
            c.drawRightString(page_w - margin, 9.5 * mm, visual(footer_text, rtl))
            c.drawString(margin, 9.5 * mm, str(d.page))
        else:
            c.drawString(margin, 9.5 * mm, visual(footer_text, rtl))
            c.drawRightString(page_w - margin, 9.5 * mm, str(d.page))
        c.restoreState()

    def on_page_end(c, d):
        if not show_draft:
            return
        c.saveState()
        c.translate(page_w / 2, page_h / 2)
        c.rotate(40)
        c.setFillColor(colors.Color(0.45, 0.52, 0.68, alpha=0.16))
        c.setFont(BOLD, 96)
        if lang == "both":  # the two words stacked, so neither runs off the page
            c.drawCentredString(0, 28, model.WATERMARK[0])
            c.drawCentredString(0, -80, visual(model.WATERMARK[1], False))
        else:
            c.drawCentredString(0, 0, visual(L(model.WATERMARK), rtl))
        c.restoreState()

    frame = Frame(margin, 18 * mm, inner, page_h - 24 * mm - 18 * mm - 8 * mm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    pdf = BaseDocTemplate(out, pagesize=A4, title=L(doc.title), author=L(doc.company), subject=doc.number)
    pdf.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=on_page, onPageEnd=on_page_end)])

    flow = []
    flow.append(Txt(L(doc.title), rtl, size=17, bold=True, color=NAVY))
    flow.append(Spacer(1, 2 * mm))
    if doc.meta:
        flow.append(_pairs(doc.meta, L, rtl, inner))
        flow.append(Spacer(1, 5 * mm))
    for block in doc.blocks:
        flow.extend(_block(block, L, rtl, inner))
    pdf.build(flow)
    return out.getvalue()


def _pairs(rows, L, rtl, inner):
    data = []
    for label, value in rows:
        cells = [Txt(L(label), rtl, size=8.5, color=MUTED), Txt(str(value), rtl, size=9.5)]
        data.append(cells[::-1] if rtl else cells)
    widths = [inner * 0.64, inner * 0.36] if rtl else [inner * 0.36, inner * 0.64]
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    return t


def _block(b, L, rtl, inner):
    if isinstance(b, model.Heading):
        return [Spacer(1, 3 * mm), Txt(L(b.pair), rtl, size=11.5, bold=True, color=NAVY), Spacer(1, 1.5 * mm)]
    if isinstance(b, model.Para):
        return [Txt(b.text, rtl, size=b.size, bold=b.bold), Spacer(1, 2 * mm)]
    if isinstance(b, model.KeyValues):
        return [_pairs(b.rows, L, rtl, inner), Spacer(1, 3 * mm)]
    if isinstance(b, model.Table):
        return _table(b, L, rtl, inner)
    if isinstance(b, model.Signatures):
        return [Spacer(1, 6 * mm), _signatures(b, L, rtl, inner)]
    return []


def _table(b, L, rtl, inner):
    total_w = sum(b.widths)
    widths = [inner * w / total_w for w in b.widths]
    heads = [Txt(L(h), rtl, size=8, bold=True, color=colors.white, align=a) for h, a in zip(b.headers, b.aligns)]
    rows = [[Txt(str(c), rtl, size=8.8, align=a) for c, a in zip(row, b.aligns)] for row in b.rows]
    data = [heads] + rows
    if rtl:
        data = [r[::-1] for r in data]
        widths = widths[::-1]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fd")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    out = [t]
    if b.totals:
        rows = []
        for label, value in b.totals:
            pair = [Txt(L(label) if isinstance(label, tuple) else str(label), rtl, size=9.5, color=MUTED, align="start"), Txt(str(value), rtl, size=9.5, bold=True, align="end")]
            rows.append(pair[::-1] if rtl else pair)
        tw = inner * 0.46
        tt = Table(rows, colWidths=[tw * 0.55, tw * 0.45] if not rtl else [tw * 0.45, tw * 0.55], hAlign="LEFT" if rtl else "RIGHT")
        tt.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LINEABOVE", (0, -1), (-1, -1), 1, NAVY)]))
        out += [Spacer(1, 3 * mm), tt]
    return out + [Spacer(1, 4 * mm)]


def _signatures(b, L, rtl, inner):
    n = max(1, len(b.items))
    cell_w = inner / n
    cells = []
    for s in b.items:
        parts = [Txt(L(s.label), rtl, size=8.5, color=MUTED), Spacer(1, 1.5 * mm)]
        if s.image or s.stamp:
            inner_row = []
            if s.image:
                inner_row.append(Img(s.image, 34 * mm, 15 * mm))
            if s.stamp:
                inner_row.append(Img(s.stamp, 22 * mm, 22 * mm))
            tbl = Table([inner_row[::-1] if rtl else inner_row], hAlign="RIGHT" if rtl else "LEFT")
            tbl.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
            parts.append(tbl)
        else:
            parts.append(Spacer(1, 14 * mm))
        parts.append(Table([[""]], colWidths=[cell_w - 10 * mm], rowHeights=[0.4], style=[("LINEABOVE", (0, 0), (-1, 0), 0.6, INK)], hAlign="RIGHT" if rtl else "LEFT"))
        if s.name:
            parts.append(Txt(s.name, rtl, size=9.5, bold=True))
        if s.when:
            parts.append(Txt(s.when, rtl, size=8.5, color=MUTED))
        if s.note:
            parts.append(Txt(s.note, rtl, size=8.5, color=MUTED))
        cells.append(parts)
    t = Table([cells[::-1] if rtl else cells], colWidths=[cell_w] * n)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    return t
