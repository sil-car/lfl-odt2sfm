import unittest
from pathlib import Path

from odt2sfm.odt import OdtChapter
from odt2sfm.odt.base import get_node_table, get_node_table_pos
from odt2sfm.odt.elements import OdtParagraph, OdtSpan

CHAPTER_PATH = Path(__file__).parent / "data" / "chapter.odt"


class TestOdtChapter(unittest.TestCase):
    def setUp(self):
        self.chapter = OdtChapter(CHAPTER_PATH)

    def test_chapter_paragraphs(self):
        self.assertEqual(len(self.chapter.all_paragraphs), 21)
        self.assertEqual(
            len(self.chapter.odt.body.paragraphs) + len(self.chapter.odt.body.headers),
            21,
        )


class TestOdtElements(unittest.TestCase):
    def setUp(self):
        self.chapter = OdtChapter(CHAPTER_PATH)
        self.paragraph3 = OdtParagraph(
            self.chapter.all_paragraphs[2], chapter=self.chapter
        )
        self.paragraph4 = OdtParagraph(
            self.chapter.all_paragraphs[3], chapter=self.chapter
        )
        self.span_bold = OdtSpan(self.chapter.all_spans[2])
        self.span_tabs = OdtSpan(self.chapter.all_spans[3])

    def test_paragraph_children(self):
        # for c in self.chapter.paragraphs[2].children:
        #     print(f"{c.text=}")
        self.assertEqual(len(self.chapter.paragraphs[2].children), 7)

    def test_paragraph_spans(self):
        self.assertEqual(len(self.chapter.all_spans), 8)

    def test_paragraph_text(self):
        self.assertEqual(
            "3 3rd verse, but now 2nd paragraph.", self.paragraph4.text_recursive
        )

    def test_path(self):
        self.assertEqual(
            self.paragraph3.path,
            "office:document-content/office:body/office:text/text:p",
        )

    def test_span_text_simple(self):
        self.assertEqual("bolded", self.span_bold.text)

    def test_span_text_withtabs(self):
        # print(f"{self.span_tabs.node.children=}")
        self.assertEqual("bold\twith\ttabs.", self.span_tabs.text)


class TestOdtTable(unittest.TestCase):
    def setUp(self):
        self.chapter = OdtChapter(CHAPTER_PATH)

    def test_table_row_pos(self):
        p = self.chapter.all_paragraphs[8]  # 8th paragraph is 1st table cell
        table = get_node_table(p)
        self.assertIsNotNone(table)
        self.assertEqual(get_node_table_pos(p), (0, 0))
