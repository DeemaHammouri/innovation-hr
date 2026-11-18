"""Word (.docx) from a Doc: the same content as the PDF. Arabic is written as real right-to-left text (bidi paragraphs, rtl runs, mirrored
tables), so Word shapes and orders it itself. The font is Arial, which Word has on every machine with Arabic and Latin letters."""
import io
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Mm, Pt, RGBColor

from . import model
from .text import is_rtl_text, pair_text

FONT = "Arial"
NAVY, BLUE, MUTED = RGBColor(0x0B, 0x1F, 0x44), RGBColor(0x00, 0x7A, 0xFF), RGBColor(0x5B, 0x6B, 0x88)
FONTS = Path(__file__).parent / "fonts"


def logo_png():
    """The IA mark as an image (Word has no drawing primitives like the PDF)."""
    from PIL import Image, ImageDraw, ImageFont

    size = 240
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.24), fill=(0, 122, 255, 255))
    font = ImageFont.truetype(str(FONTS / "IBMPlexSansArabic-Bold.ttf"), int(size * 0.46))
    w = d.textlength("IA", font=font)
    d.text(((size - w) / 2, size * 0.24), "IA", font=font, fill=(255, 255, 255, 255))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


TBLPR_ORDER = ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize", "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook"]
SECTPR_ORDER = ["headerReference", "footerReference", "footnotePr", "endnotePr", "type", "pgSz", "pgMar", "paperSrc", "pgBorders", "lnNumType", "pgNumType", "cols", "formProt", "vAlign", "noEndnote", "titlePg", "textDirection", "bidi", "rtlGutter", "docGrid"]


def _insert_ordered(parent, child, order):
    """Word is strict about the order of property elements; put `child` where the schema wants it."""
    name = child.tag.split("}")[1]
    after = set(order[order.index(name) + 1:])
    for existing in parent:
        if existing.tag.split("}")[1] in after:
            existing.addprevious(child)
            return
    parent.append(child)


def _fonts(run, rtl):
    rpr = run._r.get_or_add_rPr()
    f = rpr.find(qn("w:rFonts"))
    if f is None:
        f = OxmlElement("w:rFonts")
        rpr.insert(0, f)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        f.set(qn(attr), FONT)
    if rtl:
        rpr.append(OxmlElement("w:rtl"))


def _para(container, text="", rtl=False, size=10, bold=False, color=None, align="start", space_after=2):
    p = container.add_paragraph()
    ppr = p._p.get_or_add_pPr()
    if rtl:
        ppr.append(OxmlElement("w:bidi"))
    # In a right-to-left paragraph Word reads "left" as the start side, so "left" is the start in both directions.
    p.alignment = {"start": WD_ALIGN_PARAGRAPH.LEFT, "end": WD_ALIGN_PARAGRAPH.RIGHT, "center": WD_ALIGN_PARAGRAPH.CENTER}[align]
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if text != "":
        run = p.add_run(text)
        run.font.size = Pt(size)
        run.bold = bold
        if color is not None:
            run.font.color.rgb = color
        _fonts(run, rtl)
    return p


def _cell_text(cell, text, rtl, size=9, bold=False, color=None, align="start"):
    p = cell.paragraphs[0]
    cell._tc.remove(p._p)
    return _para(cell, text, rtl, size, bold, color, align, space_after=0)


def _shade(cell, hex_fill):
    tcpr = cell._tc.get_or_add_tcPr()
    tcpr.append(parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{hex_fill}"/>'))


def _borders(table, color="D9E0EE"):
    tblpr = table._tbl.tblPr
    _insert_ordered(tblpr, parse_xml(
        f'<w:tblBorders {nsdecls("w")}><w:top w:val="nil"/><w:left w:val="nil"/><w:right w:val="nil"/>'
        f'<w:bottom w:val="single" w:sz="4" w:color="{color}"/><w:insideH w:val="single" w:sz="4" w:color="{color}"/><w:insideV w:val="nil"/></w:tblBorders>'
    ), TBLPR_ORDER)


def _mirror(table, rtl):
    if rtl:
        _insert_ordered(table._tbl.tblPr, OxmlElement("w:bidiVisual"), TBLPR_ORDER)


def _watermark(section, text):
    """The standard Word watermark: a rotated, pale text shape in the header."""
    header = section.header
    p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    xml = (
        f'<w:r {nsdecls("w")} xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"><w:pict>'
        '<v:shapetype id="_x0000_t136" coordsize="21600,21600" o:spt="136" adj="10800" path="m@7,l@8,m@5,21600l@6,21600e">'
        '<v:formulas><v:f eqn="sum #0 0 10800"/><v:f eqn="prod #0 2 1"/><v:f eqn="sum 21600 0 @1"/><v:f eqn="sum 0 0 @2"/><v:f eqn="sum 21600 0 @3"/>'
        '<v:f eqn="if @0 @3 0"/><v:f eqn="if @0 21600 @1"/><v:f eqn="if @0 0 @2"/><v:f eqn="if @0 @4 21600"/><v:f eqn="mid @5 @6"/><v:f eqn="mid @8 @5"/>'
        '<v:f eqn="mid @7 @8"/><v:f eqn="mid @6 @7"/><v:f eqn="sum @6 0 @5"/></v:formulas>'
        '<v:path textpathok="t" o:connecttype="custom" o:connectlocs="@9,0;@10,10800;@11,21600;@12,10800" o:connectangles="270,180,90,0"/>'
        '<v:textpath on="t" fitshape="t"/><v:handles><v:h position="#0,bottomRight" xrange="6629,14971"/></v:handles><o:lock v:ext="edit" text="t" shapetype="t"/></v:shapetype>'
        f'<v:shape id="PowerPlusWaterMarkObject1" o:spid="_x0000_s2049" type="#_x0000_t136" style="position:absolute;margin-left:0;margin-top:0;width:440pt;height:150pt;rotation:315;z-index:-251658752;'
        'mso-position-horizontal:center;mso-position-horizontal-relative:margin;mso-position-vertical:center;mso-position-vertical-relative:margin" '
        f'o:allowincell="f" fillcolor="#c5cde0" stroked="f"><v:fill opacity=".35"/><v:textpath style="font-family:&quot;Arial&quot;;font-size:1pt" string="{text}"/></v:shape>'
        '</w:pict></w:r>'
    )
    p._p.append(parse_xml(xml))


def _page_number(paragraph):
    run = paragraph.add_run()
    for kind, text in (("begin", None), (None, " PAGE "), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    run.font.size = Pt(8)
    _fonts(run, False)


def build_docx(doc, lang="en", draft=None):
    rtl = lang == "ar"
    show_draft = doc.watermark if draft is None else draft
    L = lambda pair: pair_text(pair, lang)  # noqa: E731
    d = Document()
    d.core_properties.title = L(doc.title)
    d.core_properties.author = L(doc.company)
    d.core_properties.subject = doc.number
    sec = d.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.left_margin = sec.right_margin = Mm(18)
    sec.top_margin, sec.bottom_margin = Mm(34), Mm(20)
    if rtl:
        _insert_ordered(sec._sectPr, OxmlElement("w:bidi"), SECTPR_ORDER)
    inner_mm = 210 - 36

    # header: logo, company, number
    header = sec.header
    htable = header.add_table(1, 2, Mm(inner_mm))
    _mirror(htable, rtl)
    left, right = htable.rows[0].cells
    left.width, right.width = Mm(inner_mm * 0.7), Mm(inner_mm * 0.3)
    left.paragraphs[0]._p.getparent().remove(left.paragraphs[0]._p)
    lp = _para(left, "", rtl)
    lp.add_run().add_picture(io.BytesIO(logo_png()), width=Mm(11))
    r = lp.add_run("  " + L(doc.company))
    r.bold, r.font.size, r.font.color.rgb = True, Pt(12), NAVY
    _fonts(r, rtl)
    _cell_text(right, doc.number, False, 10, True, NAVY, "end")
    # python-docx puts an empty paragraph first in a header; drop it
    first = header.paragraphs[0]
    if not first.text and first._p.getnext() is not None:
        first._p.getparent().remove(first._p)
    if show_draft:
        _watermark(sec, L(model.WATERMARK))
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if rtl:
        fp._p.get_or_add_pPr().append(OxmlElement("w:bidi"))
    fr = fp.add_run((doc.footer or L(doc.company)) + "    ")
    fr.font.size, fr.font.color.rgb = Pt(8), MUTED
    _fonts(fr, rtl)
    _page_number(fp)

    _para(d, L(doc.title), rtl, 17, True, NAVY, space_after=4)
    if doc.meta:
        _pairs(d, doc.meta, L, rtl, inner_mm)
        _para(d, "", rtl, space_after=4)
    for b in doc.blocks:
        _block(d, b, L, rtl, inner_mm, mixed=lang == "both")
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()


def _pairs(d, rows, L, rtl, inner_mm):
    t = d.add_table(rows=0, cols=2)
    _mirror(t, rtl)
    _borders(t)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for label, value in rows:
        cells = t.add_row().cells
        cells[0].width, cells[1].width = Mm(inner_mm * 0.36), Mm(inner_mm * 0.64)
        _cell_text(cells[0], L(label), rtl, 8.5, False, MUTED)
        _cell_text(cells[1], str(value), rtl, 9.5)


def _block(d, b, L, rtl, inner_mm, mixed=False):
    if isinstance(b, model.Heading):
        _para(d, "", rtl, space_after=2)
        _para(d, L(b.pair), rtl, 11.5, True, NAVY, space_after=3)
    elif isinstance(b, model.Para):
        _para(d, b.text, rtl or (mixed and is_rtl_text(b.text)), b.size, b.bold, space_after=4)  # lang=both: each paragraph in its own direction
    elif isinstance(b, model.KeyValues):
        _pairs(d, b.rows, L, rtl, inner_mm)
        _para(d, "", rtl, space_after=3)
    elif isinstance(b, model.Table):
        total = sum(b.widths)
        t = d.add_table(rows=1, cols=len(b.headers))
        _mirror(t, rtl)
        _borders(t)
        for i, (h, a) in enumerate(zip(b.headers, b.aligns)):
            c = t.rows[0].cells[i]
            c.width = Mm(inner_mm * b.widths[i] / total)
            _shade(c, "0B1F44")
            _cell_text(c, L(h), rtl, 8, True, RGBColor(255, 255, 255), a)
        for row in b.rows:
            cells = t.add_row().cells
            for i, (v, a) in enumerate(zip(row, b.aligns)):
                cells[i].width = Mm(inner_mm * b.widths[i] / total)
                _cell_text(cells[i], str(v), rtl, 8.8, False, None, a)
        if b.totals:
            _para(d, "", rtl, space_after=2)
            tt = d.add_table(rows=0, cols=2)
            _mirror(tt, rtl)
            _borders(tt)
            tt.alignment = WD_TABLE_ALIGNMENT.RIGHT if not rtl else WD_TABLE_ALIGNMENT.LEFT
            for label, value in b.totals:
                cells = tt.add_row().cells
                cells[0].width, cells[1].width = Mm(inner_mm * 0.26), Mm(inner_mm * 0.2)
                _cell_text(cells[0], L(label) if isinstance(label, tuple) else str(label), rtl, 9.5, False, MUTED)
                _cell_text(cells[1], str(value), rtl, 9.5, True, None, "end")
        _para(d, "", rtl, space_after=4)
    elif isinstance(b, model.Signatures):
        _para(d, "", rtl, space_after=6)
        n = max(1, len(b.items))
        t = d.add_table(rows=1, cols=n)
        _mirror(t, rtl)
        for i, s in enumerate(b.items):
            c = t.rows[0].cells[i]
            c.width = Mm(inner_mm / n)
            c.paragraphs[0]._p.getparent().remove(c.paragraphs[0]._p)
            _para(c, L(s.label), rtl, 8.5, False, MUTED)
            pic = _para(c, "", rtl)
            if s.image:
                pic.add_run().add_picture(io.BytesIO(s.image), width=Mm(34))
            if s.stamp:
                pic.add_run("  ").add_picture(io.BytesIO(s.stamp), width=Mm(22))
            if not (s.image or s.stamp):
                _para(c, "", rtl, space_after=28)
            _para(c, "_" * 28, rtl, 9, space_after=1)
            if s.name:
                _para(c, s.name, rtl, 9.5, True, space_after=0)
            if s.when:
                _para(c, s.when, rtl, 8.5, False, MUTED, space_after=0)
            if s.note:
                _para(c, s.note, rtl, 8.5, False, MUTED, space_after=0)
