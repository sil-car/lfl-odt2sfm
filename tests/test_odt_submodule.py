import shutil
import unittest
from pathlib import Path

import pytest

from odt2sfm.odt import OdtChapter
from odt2sfm.odt.base import (
    get_node_doc_style,
    get_node_table,
    get_node_table_pos,
    node_has_paragraph_descendent_with_text,
    node_in_table,
)
from odt2sfm.odt.elements import OdtParagraph, OdtSpan, OdtText, strip_newlines
from tests.conftest import p, span

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


# --- pytest-style tests built on synthetic documents (see conftest.make_odt) ---


def frame(inner: str) -> str:
    return f"<draw:frame><draw:text-box>{inner}</draw:text-box></draw:frame>"


@pytest.mark.parametrize(
    ("name", "number"),
    [
        ("Sango_Luke-Q1-TOC.odt", 0),
        ("Sango_Luke-Q1-L07.odt", 7),
        ("Sango_Luke-Q1-L13.odt", 13),
        ("chapter.odt", None),
    ],
)
def test_chapter_number_from_filename(tmp_path, chapter_odt, name, number):
    path = tmp_path / name
    shutil.copy(chapter_odt, path)
    assert OdtChapter(path).number == number


def test_chapter_requires_existing_file(tmp_path):
    with pytest.raises(ValueError, match="No file path"):
        OdtChapter()
    with pytest.raises(ValueError, match="does not exist"):
        OdtChapter(tmp_path / "missing.odt")


@pytest.mark.parametrize(
    "body",
    [
        pytest.param([p("Text_20_body", "")], id="empty"),
        pytest.param([p("Text_20_body", "(Pictures/10000000ABC123.png)")], id="image-only"),
        pytest.param([p("Table_20_Contents", "unmapped style")], id="unmapped-style"),
    ],
)
def test_paragraphs_skipped(make_odt, body):
    """Paragraphs with no translatable text are not exported. Skipping
    paragraphs whose style isn't in styles-reference.txt is intentional: it is
    how the untranslated "helper" paragraphs in the source ODTs (often the
    text in another language) are excluded."""
    assert OdtChapter(make_odt(body)).paragraphs == []


def test_paragraph_whose_text_is_in_nested_paragraph_is_skipped(make_odt):
    chapter = OdtChapter(make_odt([p("Text_20_body", frame(p("Quotations", "inner")))]))
    assert [(para.style, para.text_recursive) for para in chapter.paragraphs] == [
        ("Quotations", "inner")
    ]


def test_paragraph_with_own_text_and_nested_paragraph_is_kept(make_odt):
    chapter = OdtChapter(make_odt([p("Text_20_body", "Outer " + frame(p("Quotations", "inner")))]))
    assert [para.style for para in chapter.paragraphs] == ["Text_20_body", "Quotations"]
    assert chapter.to_sfm("NFC") == "\\c 1\n\\p Outer \n\\q inner"


def test_node_has_paragraph_descendent_with_text(make_odt):
    chapter = OdtChapter(
        make_odt([p("Text_20_body", frame(p("Quotations", "inner"))), p("Text_20_body", "plain")])
    )
    outer, inner, plain = chapter.all_paragraphs
    assert node_has_paragraph_descendent_with_text(outer)
    assert not node_has_paragraph_descendent_with_text(plain)
    assert not node_in_table(plain)
    assert get_node_doc_style(inner, chapter.odt) == "Quotations"


def test_children_text_tail_span(make_odt):
    chapter = OdtChapter(
        make_odt([p("Text_20_body", f"Lead {span('T1', '1')} middle {span('T2', 'bold')} tail.")])
    )
    (para,) = chapter.paragraphs
    kinds = [(type(c).__name__, c.text) for c in para.children]
    assert kinds == [
        ("OdtText", "Lead "),
        ("OdtSpan", "1"),
        ("OdtText", " middle "),
        ("OdtSpan", "bold"),
        ("OdtText", " tail."),
    ]
    assert [c.is_tail for c in para.children if isinstance(c, OdtText)] == [False, True, True]
    assert [s.sfm_marker for s in para.spans] == ["\\v", "\\bd"]


def test_space_only_children_excluded(make_odt):
    chapter = OdtChapter(
        make_odt([p("Text_20_body", f"{span('T1', '1')} <text:s/>{span('T2', ' ')} tail")])
    )
    (para,) = chapter.paragraphs
    assert [(type(c).__name__, c.text) for c in para.children] == [
        ("OdtSpan", "1"),
        ("OdtText", " tail"),
    ]


def test_nested_spans_are_flattened(make_odt):
    chapter = OdtChapter(
        make_odt([p("Text_20_body", f"{span('T2', 'out ' + span('T1', 'in') + ' more')} end")])
    )
    assert chapter.to_sfm("NFC") == "\\c 1\n\\p \\bd out in more\\bd* end"


def test_to_sfm_verse_spans_start_new_line_without_end_marker(make_odt):
    chapter = OdtChapter(
        make_odt(
            [
                p("Title", "Title"),
                p("Text_20_body", f"{span('T1', '1')} One. {span('T1', '2')} Two {span('T2', 'bold')}."),
            ]
        )
    )
    assert chapter.to_sfm("NFC").splitlines() == [
        "\\c 1",
        "\\mt Title",
        "\\p ",
        "\\v 1 One. ",
        "\\v 2 Two \\bd bold\\bd*.",
    ]


def test_to_sfm_inserts_separator_between_adjacent_texts(make_odt):
    chapter = OdtChapter(make_odt([p("Text_20_body", "a<text:tab/>b")]))
    assert chapter.to_sfm("NFC") == "\\c 1\n\\p a _b"


def test_to_sfm_toc_has_no_chapter_marker(make_odt):
    chapter = OdtChapter(make_odt([p("Title", "Contents")], name="Test_Luke-Q1-TOC.odt"))
    assert chapter.to_sfm("NFC") == "\\mt Contents"


@pytest.mark.parametrize(("form", "expected"), [("NFC", "café~!"), ("NFD", "café~!")])
def test_to_sfm_normalizes_and_replaces_nbsp(make_odt, form, expected):
    chapter = OdtChapter(make_odt([p("Text_20_body", "café !")]))
    assert chapter.to_sfm(form) == f"\\c 1\n\\p {expected}"


def test_span_text_with_spacer(make_odt):
    chapter = OdtChapter(make_odt([p("Text_20_body", span("T2", 'a<text:s text:c="2"/>b'))]))
    (para,) = chapter.paragraphs
    assert para.spans[0].text == "a  b"


def test_span_sfm_marker_setter_validates(chapter_odt):
    chapter = OdtChapter(chapter_odt)
    s = OdtSpan(chapter.all_spans[0], chapter=chapter)
    s.sfm_marker = "\\tc1"
    with pytest.raises(ValueError):
        s.sfm_marker = "tc1"


def test_save_refuses_when_lock_file_present(make_odt, tmp_path):
    chapter = OdtChapter(make_odt([p("Text_20_body", "x")]))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    dest = out_dir / chapter.file_path.name
    (out_dir / f".~lock.{chapter.file_path.name}#").write_text("")
    with pytest.raises(OSError, match="already open"):
        chapter.save(dest)
    assert not dest.exists()


def test_save_writes_file(make_odt, tmp_path):
    chapter = OdtChapter(make_odt([p("Text_20_body", "x")]))
    dest = tmp_path / "copy.odt"
    chapter.save(dest)
    assert OdtChapter(dest).all_paragraphs[0].text == "x"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("abc\ndef", "abc def"),  # only separator: becomes a space
        ("a\n\nb", "a b"),
        ("so \nawa", "so awa"),  # next to white space: dropped
        ("25\t\n  Luc", "25\t  Luc"),
        ("1:5-25\t\n", "1:5-25\t"),
        ("\n", ""),  # text:line-break element
        ("a\n", "a"),
        ("\na", "a"),
        ("no newline", "no newline"),
    ],
)
def test_strip_newlines(text, expected):
    assert strip_newlines(text) == expected


def test_to_sfm_literal_newline_does_not_join_words(make_odt):
    chapter = OdtChapter(make_odt([p("Text_20_body", "abc\ndef")]))
    assert chapter.to_sfm("NFC") == "\\c 1\n\\p abc def"


def test_to_sfm_line_break_element(make_odt):
    chapter = OdtChapter(make_odt([p("Text_20_body", "a<text:line-break/>b")]))
    assert chapter.to_sfm("NFC") == "\\c 1\n\\p a _ _b"


@pytest.mark.parametrize(
    "sfm",
    [
        pytest.param("\\p Nouveau texte sans gras.", id="fewer-parts"),
        pytest.param("\\p Lead \\bd gras\\bd* tail \\it plus\\it*.", id="more-parts"),
    ],
)
def test_update_text_part_count_mismatch_raises(make_odt, sfm):
    from odt2sfm.sfm import SfmParagraph

    chapter = OdtChapter(make_odt([p("Text_20_body", f"Lead {span('T2', 'bold')} tail.")]))
    (para,) = chapter.paragraphs
    with pytest.raises(ValueError, match="Can't update paragraph"):
        para.update_text(SfmParagraph(sfm), "NFC")
    assert para.node.text_recursive == "Lead bold tail."


# --- Unmapped span styles and hyperlinks ---

LINK = '<text:a xlink:href="mailto:a@b.org"{style}>{inner}</text:a>'


def test_unmapped_automatic_span_style_falls_back_to_no(chapter_odt, caplog):
    # tests/data/chapter.odt uses automatic style T2, not in its styles-reference.
    caplog.set_level("INFO", logger="odt2sfm")
    sfm = OdtChapter(chapter_odt).to_sfm("NFC")
    assert sfm.splitlines()[-1] == "\\p \\zodt 5\\zodt* Yet another verse, but the first one of a new section."
    assert any('unmapped automatic character style "T2"' in r.getMessage() for r in caplog.records)


def test_mapped_automatic_span_style_uses_mapping(make_odt):
    chapter = OdtChapter(make_odt([p("Text_20_body", f"a {span('T2', 'b')} c")]))
    assert chapter.to_sfm("NFC") == "\\c 1\n\\p a \\bd b\\bd* c"  # T2 -> \bd in DEFAULT_REF


def test_unmapped_named_span_style_raises(make_odt):
    chapter = OdtChapter(make_odt([p("Text_20_body", f"a {span('Emphasis', 'b')} c")]))
    with pytest.raises(ValueError, match='"Emphasis"; add it to styles-reference.txt: "b"'):
        chapter.to_sfm("NFC")


def test_unstyled_hyperlink_raises(make_odt):
    link = LINK.format(style="", inner="a@b.org")
    chapter = OdtChapter(make_odt([p("Text_20_body", f"Mail {link} now")]))
    with pytest.raises(ValueError, match='has no style .*hyperlink.*: "a@b.org"'):
        chapter.to_sfm("NFC")


def test_styled_hyperlink_exported(make_odt, write_ref):
    link = LINK.format(style=' text:style-name="Internet_20_link"', inner=span("T2", "a@b.org"))
    path = make_odt([p("Text_20_body", f"Mail {link} now")], ref={"Text_20_body": "\\p", "Internet_20_link": "\\png"})
    assert OdtChapter(path).to_sfm("NFC") == "\\c 1\n\\p Mail \\png a@b.org\\png* now"


def test_explicit_sfm_marker_takes_precedence(chapter_odt):
    chapter = OdtChapter(chapter_odt)
    s = OdtSpan(chapter.all_spans[0], chapter=chapter)
    s.sfm_marker = "\\tc1"
    assert s.sfm_marker == "\\tc1"


# --- Writing new text into a span ---


def _only_span(make_odt, inner):
    chapter = OdtChapter(make_odt([p("Text_20_body", f"Lead {inner} tail")]))
    (para,) = chapter.paragraphs
    (s,) = para.spans
    return para, s


def test_span_text_setter_simple(make_odt):
    para, s = _only_span(make_odt, span("T2", "old"))
    s.text = "new"
    assert para.node.text_recursive == "Lead new tail"


def test_span_text_setter_keeps_nested_span_formatting(make_odt):
    link = LINK.format(style=' text:style-name="Internet_20_link"', inner=span("T2", "a@b.org"))
    para, s = _only_span(make_odt, link)
    s.text = "x@y.org"
    assert para.node.text_recursive == "Lead [x@y.org](mailto:a@b.org) tail"
    inner = para.node.children[0].children[0]
    assert (inner.tag, inner.style, inner.text) == ("text:span", "T2", "x@y.org")


def test_span_text_setter_replaces_mixed_content(make_odt):
    para, s = _only_span(make_odt, span("T2", "old<text:tab/>x <text:span text:style-name=\"T1\">y</text:span>z"))
    s.text = "n  e\tw"
    assert para.node.text_recursive == "Lead n  e\tw tail"
    assert [c.tag for c in para.node.children[0].children] == ["text:s", "text:tab"]
    assert s.text == "n  e\tw"


@pytest.mark.parametrize(
    ("original", "new_text", "expected"),
    [
        pytest.param("Hinga: <text:s/>", "Hingā:  ", "Hingā: <text:s/>", id="trailing-run"),
        pytest.param("a <text:s/>b<text:tab/>", "c   d\t", 'c <text:s text:c="2"/>d<text:tab/>', id="mid-run"),
        pytest.param("x<text:tab/>y", "z ", "z ", id="single-trailing-space"),
    ],
)
def test_span_text_setter_writes_spacers_like_libreoffice(make_odt, original, new_text, expected):
    """LibreOffice writes a run of spaces as one literal space followed by a
    text:s for the rest. Other tools split text at text:s, so keep that form."""
    para, s = _only_span(make_odt, span("T2", original))
    s.text = new_text
    inner = para.node.children[0].serialize()
    assert inner == f'<text:span text:style-name="T2">{expected}</text:span>'
