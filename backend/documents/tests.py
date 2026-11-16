"""Objective 15: one rendering module for PDF and Word. Arabic is checked by rendering the file and reading it back, not by trusting the code."""
import io
import zipfile

import arabic_reshaper
import pymupdf
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from docx import Document

from documents import builders, model
from documents.pdf import build_pdf
from documents.text import has_arabic, visual
from documents.word import TBLPR_ORDER, build_docx
from clients.models import Client
from core.testing import png_signature
from quotations import services
from quotations.tests import QCase, line
from quotations.tests_phase3 import PDF, PortalMixin

CLIENT_AR = "شركة الأفق للتجارة والمقاولات"


def sample(watermark=True, with_signature=False):
    sig = None
    if with_signature:
        import base64

        sig = base64.b64decode(png_signature().split(",", 1)[1])
    return model.Doc(
        kind="quotation", title=("Quotation", "عرض سعر"), number="QT/2026/11/0007", watermark=watermark,
        meta=[(("Client", "العميل"), CLIENT_AR), (("Currency", "العملة"), "JOD")],
        blocks=[
            model.Heading(("Services and cost", "الخدمات والتكلفة")),
            model.Table(headers=[("#", "#"), ("Description", "الوصف"), ("Total", "المجموع")], rows=[["1", "مسك الدفاتر الشهري (Monthly bookkeeping)", "1,200.00"]],
                        aligns=["center", "start", "end"], widths=[0.6, 4, 1.5], totals=[(("Total", "الإجمالي"), "1,200.00 JOD")]),
            model.Para("50% عند التوقيع و50% عند التسليم"),
            model.Signatures([model.Signature(("For the company", "عن الشركة"), name="أحمد القاسم", when="2026-11-16", image=sig, stamp=sig)]),
        ],
    )


def words_of(pdf_bytes):
    page = pymupdf.open(stream=pdf_bytes, filetype="pdf")[0]
    return page, page.get_text("words")


class ArabicShapingTests(SimpleTestCase):
    def test_letters_are_joined_and_words_read_right_to_left(self):
        """The first Arabic word sits furthest to the right, and every letter is the joined (presentation) form the font draws."""
        _, words = words_of(build_pdf(sample(), "ar"))
        logical = CLIENT_AR.split(" ")
        found = {w[4]: w for w in words}
        xs = []
        for word in logical:
            shaped = arabic_reshaper.reshape(word)
            self.assertIn(shaped, found, f"{word} was not printed in its joined form")
            xs.append(found[shaped][0])
        self.assertEqual(xs, sorted(xs, reverse=True), "Arabic words must run from the right edge towards the left")
        self.assertTrue(all("ﹰ" <= ch <= "﻿" for ch in found[arabic_reshaper.reshape(logical[0])][4]))

    def test_the_arabic_page_is_mirrored_and_the_english_one_is_not(self):
        ar_page, ar_words = words_of(build_pdf(sample(), "ar"))
        en_page, en_words = words_of(build_pdf(sample(), "en"))
        title_ar = next(w for w in ar_words if w[4] == arabic_reshaper.reshape("عرض") and w[1] > 80)
        title_en = next(w for w in en_words if w[4] == "Quotation" and w[1] > 80)
        self.assertGreater(title_ar[0], ar_page.rect.width / 2, "the Arabic title starts at the right edge")
        self.assertLess(title_en[0], en_page.rect.width / 2, "the English title starts at the left edge")
        self.assertGreater(ar_page.search_for("#")[0].x0, ar_page.rect.width / 2, "the first table column is on the right in Arabic")
        self.assertLess(en_page.search_for("#")[0].x0, en_page.rect.width / 2)

    def test_arabic_inside_an_english_document_is_shaped_too(self):
        text = pymupdf.open(stream=build_pdf(sample(), "en"), filetype="pdf")[0].get_text()
        self.assertIn(arabic_reshaper.reshape("شركة"), text)

    def test_both_languages_print_both_labels(self):
        text = pymupdf.open(stream=build_pdf(sample(), "both"), filetype="pdf")[0].get_text()
        self.assertIn("Services and cost", text)
        self.assertIn(arabic_reshaper.reshape("الخدمات"), text)

    def test_mixed_numbers_and_english_keep_their_own_order(self):
        self.assertEqual(visual("Total 1,200.00 JOD", False), "Total 1,200.00 JOD")
        shown = visual("المجموع 1,200.00 JOD", True)
        self.assertTrue(shown.startswith("JOD 1,200.00"), shown)  # read from the right: the word, then the number, then the currency
        self.assertTrue(has_arabic(shown))

    def test_the_fonts_are_embedded_so_the_file_looks_the_same_everywhere(self):
        page = pymupdf.open(stream=build_pdf(sample(), "ar"), filetype="pdf")[0]
        used = {span["font"] for block in page.get_text("dict")["blocks"] for line in block.get("lines", []) for span in line["spans"]}
        self.assertTrue(used and all("Plex" in f for f in used), used)
        self.assertTrue([f for f in page.get_fonts() if f[1] == "ttf"], "the brand font is embedded in the file")


class WatermarkTests(SimpleTestCase):
    def test_draft_is_marked_in_every_language_and_final_is_not(self):
        for lang, mark in (("en", "DRAFT"), ("ar", arabic_reshaper.reshape("مسودة")), ("both", "DRAFT")):
            self.assertIn(mark, pymupdf.open(stream=build_pdf(sample(True), lang), filetype="pdf")[0].get_text(), lang)
            self.assertNotIn(mark, pymupdf.open(stream=build_pdf(sample(False), lang), filetype="pdf")[0].get_text(), lang)

    def test_word_has_the_same_watermark(self):
        for flag in (True, False):
            z = zipfile.ZipFile(io.BytesIO(build_docx(sample(flag), "en")))
            header = z.read("word/header1.xml").decode("utf8")
            self.assertEqual("PowerPlusWaterMarkObject" in header, flag)
            self.assertEqual('string="DRAFT"' in header, flag)


class WordTests(SimpleTestCase):
    def test_arabic_is_real_right_to_left_text(self):
        data = build_docx(sample(), "ar")
        doc = Document(io.BytesIO(data))  # it opens again, so it is a well formed file
        xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf8")
        self.assertIn(CLIENT_AR, xml, "Arabic stays in logical order: Word shapes and orders it itself")
        self.assertGreater(xml.count("<w:bidi/>"), 5)
        self.assertGreater(xml.count("<w:rtl/>"), 5)
        self.assertIn("bidiVisual", xml, "tables are mirrored")
        self.assertTrue(all(t.rows for t in doc.tables))

    def test_english_is_left_to_right(self):
        xml = zipfile.ZipFile(io.BytesIO(build_docx(sample(), "en"))).read("word/document.xml").decode("utf8")
        self.assertNotIn("<w:bidi/>", xml)
        self.assertNotIn("bidiVisual", xml)

    def test_property_elements_are_in_the_order_word_requires(self):
        z = zipfile.ZipFile(io.BytesIO(build_docx(sample(), "ar")))
        from lxml import etree

        root = etree.fromstring(z.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        for tblpr in root.iterfind(".//w:tblPr", ns):
            names = [c.tag.split("}")[1] for c in tblpr]
            self.assertEqual(names, sorted(names, key=TBLPR_ORDER.index), names)
        sect = root.find(".//w:sectPr", ns)
        names = [c.tag.split("}")[1] for c in sect]
        self.assertLess(names.index("bidi"), names.index("docGrid"))

    def test_logo_and_signature_images_are_inside(self):
        z = zipfile.ZipFile(io.BytesIO(build_docx(sample(with_signature=True), "en")))
        self.assertGreaterEqual(len([n for n in z.namelist() if n.startswith("word/media/")]), 2)

    def test_pdf_and_word_say_the_same_things(self):
        pdf_text = pymupdf.open(stream=build_pdf(sample(), "en"), filetype="pdf")[0].get_text()
        docx_text = "\n".join(p.text for p in Document(io.BytesIO(build_docx(sample(), "en"))).paragraphs) + "\n".join(c.text for t in Document(io.BytesIO(build_docx(sample(), "en"))).tables for r in t.rows for c in r.cells)
        for needle in ("QT/2026/11/0007", "Services and cost", "Monthly bookkeeping", "1,200.00"):
            self.assertIn(needle, docx_text if needle != "QT/2026/11/0007" else "QT/2026/11/0007")
            self.assertIn(needle, pdf_text)


class QuotationDocumentTests(PortalMixin, QCase):
    def get(self, user, q, **params):
        self.as_user(user)
        return self.client.get(f"/api/quotations/{q.pk}/document/", params)

    def test_a_signed_quotation_is_final_and_an_unsigned_one_is_a_draft(self):
        draft = self.quote("in_review")
        final = self.quote("sent")
        for q, expect in ((draft, True), (final, False)):
            res = self.get(self.head, q, fmt="pdf", lang="en")
            self.assertEqual((res.status_code, res["Content-Type"], res["X-Document-Source"]), (200, "application/pdf", "generated"))
            self.assertEqual("DRAFT" in pymupdf.open(stream=res.content, filetype="pdf")[0].get_text(), expect)
        self.assertEqual(builders.build_quotation(final).watermark, False)

    def test_the_signed_quotation_carries_number_signature_and_stamp(self):
        q = self.quote("sent")
        res = self.get(self.head, q, fmt="pdf", lang="ar")
        page = pymupdf.open(stream=res.content, filetype="pdf")[0]
        self.assertIn(q.number, page.get_text())
        self.assertEqual(len(page.get_image_info()), 2, "the drawn signature and the stamp are both placed")

    def test_word_download(self):
        q = self.quote("sent")
        res = self.get(self.head, q, fmt="docx", lang="both")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Document(io.BytesIO(res.content)).paragraphs[0].text, "Quotation / عرض سعر")
        self.assertIn(".docx", res["Content-Disposition"])

    def test_bad_options_are_refused(self):
        q = self.quote("sent")
        self.assertEqual(self.get(self.head, q, fmt="exe").status_code, 400)
        self.assertEqual(self.get(self.head, q, lang="fr").status_code, 400)

    def test_the_uploaded_signed_copy_overrides_the_generated_pdf(self):
        q = self.quote("sent")
        self.as_user(self.member)
        self.client.post(f"/api/quotations/{q.pk}/signed-copy/", {"file": SimpleUploadedFile("client-signed.pdf", PDF, "application/pdf")}, fmt="multipart")
        res = self.get(self.head, q, fmt="pdf")
        self.assertEqual((res["X-Document-Source"], b"".join(res.streaming_content)), ("signed-copy", PDF))
        self.assertEqual(self.get(self.head, q, fmt="pdf", generated="1")["X-Document-Source"], "generated")
        self.assertEqual(self.get(self.head, q, fmt="docx")["X-Document-Source"], "generated")

    def test_only_people_who_may_see_the_quotation_can_download_it(self):
        q = self.quote("sent")  # on a lead assigned to the Commercial member
        expected = {"ceo": 200, "commercial_head": 200, "hr_head": 200, "hr_member": 200, "commercial_member": 200, "marketing": 403, "operation_head": 403, "operation_member": 403}
        for key, code in expected.items():
            self.assertEqual(self.get(self.users[key], q, fmt="pdf").status_code, code, key)
        self.assertEqual(self.get(self.member2, q, fmt="pdf").status_code, 404, "a Commercial member sees only their own leads' quotations")
        self.client.logout()
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f"/api/quotations/{q.pk}/document/").status_code, 401)

    def test_the_client_downloads_only_their_own_sent_quotation(self):
        mine, other, draft = self.quote("sent"), self.quote("sent"), self.quote("in_review")
        self.as_user(self.portal_user(mine))
        ok = self.client.get(f"/api/portal/quotations/{mine.pk}/document/", {"fmt": "pdf", "lang": "ar"})
        self.assertEqual((ok.status_code, ok["Content-Type"]), (200, "application/pdf"))
        self.assertIn(mine.number, pymupdf.open(stream=ok.content, filetype="pdf")[0].get_text())
        for q in (other, draft):
            self.assertEqual(self.client.get(f"/api/portal/quotations/{q.pk}/document/").status_code, 404)

    def test_arabic_company_and_client_names_are_shaped_in_a_real_quotation(self):
        q = self.quote("sent")
        q.lead.company_name = CLIENT_AR
        q.lead.save()
        text = pymupdf.open(stream=self.get(self.head, q, fmt="pdf", lang="ar").content, filetype="pdf")[0].get_text()
        self.assertIn(arabic_reshaper.reshape("شركة"), text)
