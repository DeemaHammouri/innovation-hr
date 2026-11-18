"""P21: in a lang=both document every Arabic paragraph is laid out right to left (right-aligned, bidi in Word); English stays left to right.
Checked on the rendered files, not on the code."""
import io

import pymupdf
from django.test import SimpleTestCase
from docx import Document
from docx.oxml.ns import qn
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4

from documents import model
from documents.pdf import build_pdf
from documents.text import has_arabic, is_rtl_text
from documents.word import build_docx

ENGLISH = "The client agrees to the services listed above."
ARABIC = "يوافق العميل على الخدمات المذكورة أعلاه."
DOC = model.Doc(kind="contract", title=("Contract", "عقد"), blocks=[model.Heading(("Terms", "الشروط")), model.Para(ENGLISH), model.Para(ARABIC)])
MARGIN = 18 * mm


class DirectionRuleTests(SimpleTestCase):
    def test_paragraphs_are_classified_by_their_own_text(self):
        self.assertTrue(is_rtl_text(ARABIC))
        self.assertTrue(is_rtl_text("شركة Acme للتجارة"))  # Arabic sentence with an English name in it
        self.assertFalse(is_rtl_text(ENGLISH))
        self.assertFalse(is_rtl_text("Quotation / عرض سعر"))  # a bilingual label keeps the English reading order
        self.assertFalse(is_rtl_text("1,200.00"))
        self.assertFalse(is_rtl_text(""))


class PdfBothTests(SimpleTestCase):
    def lines(self, lang):
        page = pymupdf.open(stream=build_pdf(DOC, lang), filetype="pdf")[0]
        out = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"])
                out.append((text, line["bbox"]))
        return out

    def test_the_arabic_paragraph_is_right_aligned_and_the_english_one_left_aligned(self):
        lines = self.lines("both")
        right_edge = A4[0] - MARGIN
        arabic = [b for t, b in lines if has_arabic(t) and "/" not in t and b[1] > 150]  # body lines, not the header band or the heading
        english = [b for t, b in lines if "client agrees" in t]
        self.assertTrue(arabic and english, lines)
        for x0, _, x1, _ in arabic:
            self.assertAlmostEqual(x1, right_edge, delta=3, msg="the Arabic paragraph must end at the right margin")
            self.assertGreater(x0, MARGIN + 60, "and must not start at the left margin")
        for x0, _, x1, _ in english:
            self.assertAlmostEqual(x0, MARGIN, delta=3, msg="the English paragraph starts at the left margin")

    def test_arabic_only_and_english_only_documents_are_unchanged(self):
        ar = self.lines("ar")
        self.assertTrue(all(abs(b[2] - (A4[0] - MARGIN)) < 3 for t, b in ar if has_arabic(t) and b[1] > 150))
        en = self.lines("en")
        self.assertTrue(all(abs(b[0] - MARGIN) < 3 for t, b in en if "client agrees" in t))


class WordBothTests(SimpleTestCase):
    def paragraph(self, lang, needle):
        doc = Document(io.BytesIO(build_docx(DOC, lang)))
        return next(p for p in doc.paragraphs if needle in p.text)

    def bidi(self, p):
        return p._p.pPr is not None and p._p.pPr.find(qn("w:bidi")) is not None

    def rtl_runs(self, p):
        return [r._r.rPr is not None and r._r.rPr.find(qn("w:rtl")) is not None for r in p.runs]

    def test_both_marks_the_arabic_paragraph_bidi_and_rtl_and_not_the_english_one(self):
        arabic = self.paragraph("both", "العميل")
        english = self.paragraph("both", "client agrees")
        self.assertTrue(self.bidi(arabic))
        self.assertTrue(arabic.runs and all(self.rtl_runs(arabic)))
        self.assertFalse(self.bidi(english))
        self.assertFalse(any(self.rtl_runs(english)))

    def test_the_xml_of_a_both_document_carries_rtl_markers(self):
        xml = Document(io.BytesIO(build_docx(DOC, "both")))._element.xml
        self.assertGreater(xml.count("<w:bidi/>"), 0)
        self.assertGreater(xml.count("<w:rtl/>"), 0)

    def test_the_english_only_document_has_none(self):
        xml = Document(io.BytesIO(build_docx(DOC, "en")))._element.xml
        self.assertNotIn("<w:bidi/>", xml)
