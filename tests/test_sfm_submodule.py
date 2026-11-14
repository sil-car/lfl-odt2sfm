import unittest
from pathlib import Path

import pytest

from odt2sfm.sfm import SfmBook, SfmChapter
from odt2sfm.sfm.base import get_sfm_type
from odt2sfm.sfm.elements import SfmElement, SfmParagraph, SfmSpan, SfmText

BOOK_PATH = Path(__file__).parent / "data" / "book.sfm"


class TestSfmBase(unittest.TestCase):
    def test_get_sfm_type(self):
        self.assertEqual(get_sfm_type("\\li1"), "li")
        self.assertIsNone(get_sfm_type("\\999"))


class TestSfmElements(unittest.TestCase):
    def setUp(self):
        self.element_input = "\\p \\v 19 Sample \\b text\\b*"
        self.span_input = "\\b bolded text\\b*"
        self.element = SfmElement(self.element_input)
        self.span = SfmSpan(self.span_input)

    def test_end_marker(self):
        self.assertEqual(self.span.end_marker, "\\b*")

    def test_marker(self):
        self.assertEqual(self.span.marker, "\\b")

    def test_sfm_raw(self):
        self.assertEqual(self.element_input, self.element.sfm_raw)

    def test_text(self):
        self.assertEqual("\\v 19 Sample \\b text\\b*", self.element.text)


class TestSfmBook(unittest.TestCase):
    def test_chapters(self):
        self.book = SfmBook(BOOK_PATH)
        self.assertEqual(len(self.book.chapters), 4)

    def test_id_text(self):
        self.book = SfmBook(BOOK_PATH)
        self.assertEqual("XXA Book title information, etc.", self.book.id_text)


class TestSfmChapter(unittest.TestCase):
    def setUp(self):
        self.book = SfmBook(BOOK_PATH)
        self.c1_raw = (
            "\\c 1\n"
            "\\s Section Header\n"
            "\\p\n"
            "\\v 1 1st verse--nothing fancy.\n"
            "\\v 2 2nd verse with some \\b bolded\\b* text.\n"
            "\\p\n"
            "\\v 3 3rd verse, but now 2nd paragraph.\n"
            "\\s A 2nd Section Header\n"
            "\\q\n"
            '\\v 4 Whatever a verse as "q" is (poetry?)\n'
        )

    def test_chapter_number_bad(self):
        c = SfmChapter("\\c  \n\\v 1 Some text.\n")
        with self.assertRaises(ValueError):
            _ = c.number

    # def test_chapter_odt_styles(self):
    #     print(self.book.chapters[1].odt_styles)

    def test_chapter_paragraphs(self):
        p1 = "\\p\n\\v 1 1st verse--nothing fancy.\n\\v 2 2nd verse with some \\b bolded\\b* text."
        self.assertEqual(self.book.chapters[1].paragraphs[1].sfm_raw, p1)

    def test_chapter_sfm_raw(self):
        self.assertEqual(self.book.chapters[1].sfm_raw, self.c1_raw)

    def test_chapter_verses(self):
        self.assertEqual(len(self.book.chapters[1].verses), 4)


class TestSfmParagraph(unittest.TestCase):
    def setUp(self):
        self.book = SfmBook(BOOK_PATH)
        self.chapter1 = self.book.chapters[1]
        self.chapter2 = self.book.chapters[2]
        self.paragraph0 = self.chapter1.paragraphs[0]
        self.paragraph1 = self.chapter1.paragraphs[1]
        self.p_split_texts = self.chapter2.paragraphs[2]

    def test_paragraph_children(self):
        self.assertEqual(len(self.paragraph1.children), 6)
        classes = [SfmSpan, SfmText, SfmSpan, SfmText, SfmSpan, SfmText]
        for i, cls in enumerate(classes):
            self.assertIsInstance(self.paragraph1.children[i], cls)
        texts = [
            "1",
            "1st verse--nothing fancy.",
            "2",
            "2nd verse with some ",
            "bolded",
            " text.",
        ]
        for i, text in enumerate(texts):
            self.assertEqual(self.paragraph1.children[i].text, text)

    def test_paragraph_children_text_split(self):
        # print(f"{self.p_split_texts.sfm_raw}; {self.p_split_texts.children=}")
        self.assertEqual(len(self.p_split_texts.children), 6)

    def test_paragraph_spans(self):
        span_markers = ["\\v", "\\b", "\\it"]
        span_end_markers = [None, "\\b*", "\\it*"]
        span_texts = ["23", "bolded ", "italicized"]
        texts = ["This is a line of ", "and ", " text."]
        sfm_raws = [
            f"{span_markers[0]} {span_texts[0]} ",
            f"{span_markers[1]} {span_texts[1]}{span_end_markers[1]}",
            f"{span_markers[2]} {span_texts[2]}{span_end_markers[2]}",
        ]
        p_sfm = (
            f"\\p {sfm_raws[0]}{texts[0]}{sfm_raws[1]}{texts[1]}{sfm_raws[2]}{texts[2]}"
        )
        p = SfmParagraph(p_sfm)
        self.assertEqual(sfm_raws, [s.sfm_raw for s in p.spans])
        self.assertEqual(span_texts, [s.text for s in p.spans])
        self.assertEqual(span_markers, [s.marker for s in p.spans])
        self.assertEqual(span_end_markers, [s.end_marker for s in p.spans])
        self.assertEqual(texts, [t.text for t in p.texts])

    def test_paragraph_text(self):
        self.assertEqual(
            self.paragraph1.text,
            "1 1st verse--nothing fancy. 2 2nd verse with some  bolded text.",
        )
        self.assertEqual(self.paragraph0.text, "Section Header")


class TestSfmSpan(unittest.TestCase):
    def setUp(self):
        self.span = SfmBook(BOOK_PATH).chapters[1].paragraphs[1].children[4]

    def test_span_children_span(self):
        self.assertEqual(len(self.span.children), 1)
        self.assertEqual(self.span.text, "bolded")


# --- pytest-style tests ---


@pytest.mark.parametrize(
    ("sfm", "expected"),
    [("\\p", "p"), ("\\tc1", "tc"), ("\\li2", "li"), ("\\s1", "s"), ("\\v", "v"), ("\\bd*", "bd")],
)
def test_get_sfm_type_variants(sfm, expected):
    assert get_sfm_type(sfm) == expected


def test_element_without_marker_raises():
    with pytest.raises(ValueError, match="No intial SFM marker"):
        _ = SfmElement("plain text").marker


def test_sfm_raw_setter_requires_backslash():
    e = SfmElement("\\p text")
    with pytest.raises(ValueError, match="does not begin with a backslash"):
        e.sfm_raw = "text"


def test_marker_setter_rewrites_raw():
    e = SfmParagraph("\\p Some text")
    e.marker = "\\m"
    assert e.sfm_raw == "\\m Some text"


def test_span_unmatched_markers_raise():
    with pytest.raises(ValueError, match="Unmatched markers"):
        SfmSpan("\\bd text\\it*")


def test_span_missing_end_marker_raises():
    with pytest.raises(ValueError):
        SfmSpan("\\bd text")


def test_verse_span_has_no_end_marker():
    v = SfmSpan("\\v 12 ")
    assert (v.marker, v.end_marker, v.text) == ("\\v", None, "12")


def test_paragraph_text_undoes_paratext_placeholders():
    assert SfmParagraph("\\p a~b").text == "a\u00a0b"


def test_paragraph_marker_followed_by_newline():
    para = SfmParagraph("\\p\n\\v 1 Text.")
    assert para.marker == "\\p"
    assert [(type(c).__name__, c.text) for c in para.children] == [("SfmSpan", "1"), ("SfmText", "Text.")]


def test_text_separator_splits_children():
    para = SfmParagraph("\\p a _b _c")
    assert [c.text for c in para.children] == ["a", "b", "c"]


@pytest.mark.parametrize(
    ("raw", "texts"),
    [
        ("\\li1 Na ya ti ______ pepe?", ["Na ya ti ______ pepe?"]),
        ("\\li1 Na ndo_________?", ["Na ndo_________?"]),
        ("\\li1 Na ya ti ______ pepe? _( Lamba)", ["Na ya ti ______ pepe?", "( Lamba)"]),
        ("\\li1 Na ya ti ____ _b", ["Na ya ti ____", "b"]),
    ],
)
def test_fill_in_the_blank_is_not_a_text_separator(raw, texts):
    assert [c.text for c in SfmParagraph(raw).children] == texts


def test_chapter_paragraphs_join_verses_to_previous_paragraph():
    ch = SfmChapter("\\c 4\n\\s1 Head\n\\p\n\\v 1 One.\n\\v 2 Two.\n\\q Quote\n")
    assert ch.number == 4
    assert [(para.marker, para.sfm_raw) for para in ch.paragraphs] == [
        ("\\s1", "\\s1 Head"),
        ("\\p", "\\p\n\\v 1 One.\n\\v 2 Two."),
        ("\\q", "\\q Quote"),
    ]


@pytest.mark.parametrize(("raw", "number"), [("\\id XXA\n\\mt T\n", 0), ("\\mt T\n", None)])
def test_chapter_number_without_c_marker(raw, number):
    assert SfmChapter(raw).number == number


def test_book_without_file():
    book = SfmBook()
    assert (book.name, book.sfm_raw, book.chapters, book.id_text) == ("", None, [], None)


def test_book_chapter_numbers(book_sfm):
    assert [c.number for c in SfmBook(book_sfm).chapters] == [0, 1, 2, 3]
    assert [p.marker for p in SfmBook(book_sfm).chapters[0].paragraphs] == ["\\id"]
