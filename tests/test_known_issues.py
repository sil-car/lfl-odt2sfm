"""Known bugs and wanted behavior, written as strict xfail tests.

Each test asserts the *desired* behavior. While the bug exists the test
fails and is reported as XFAIL. Once the bug is fixed the test passes, which
``xfail_strict = true`` reports as a failure: remove the xfail mark then.

Where possible, ``raises=`` names the exception the bug produces today, so a
different failure is reported as a real error instead of being hidden.
"""

import logging

import pytest

from odt2sfm.odt import OdtBook, OdtChapter
from odt2sfm.odt.base import node_has_paragraph_descendent_with_text
from odt2sfm.sfm import SfmChapter, SfmParagraph
from tests.conftest import p, span

PKG_LOGGER = "odt2sfm"


def warnings_mentioning(caplog, text):
    return [r for r in caplog.records if r.levelno >= logging.WARNING and text in r.getMessage()]


# --- Unmapped span styles ---
# (Unmapped *paragraph* styles are skipped by design: that is how untranslated
# helper paragraphs are excluded. See test_paragraphs_skipped.)


@pytest.mark.xfail(
    raises=ValueError,
    reason="An unmapped span style aborts the whole export instead of keeping "
    "the span's text without a character marker.",
)
def test_unmapped_span_style_keeps_text(chapter_odt):
    # tests/data/chapter.odt uses span style T2, which is not in its styles-reference.
    sfm = OdtChapter(chapter_odt).to_sfm("NFC")
    assert "5 Yet another verse" in sfm


# --- Book structure ---


@pytest.mark.xfail(raises=KeyError, reason="OdtBook.to_sfm does chs.pop(0), so a TOC file is required.")
def test_export_book_without_toc(make_book):
    sfm = OdtBook(make_book(toc=False), filename="41XXA.SFM", normalization_mode="NFC").to_sfm()
    assert sfm.splitlines()[3] == "\\c 1"


@pytest.mark.xfail(reason="ODT files without 'L##' or 'TOC' all get chapter None and overwrite each other.")
def test_files_without_chapter_number_rejected(make_odt, tmp_path):
    book_dir = tmp_path / "book"
    make_odt([p("Title", "A")], name="first.odt", directory=book_dir)
    make_odt([p("Title", "B")], name="second.odt", directory=book_dir)
    with pytest.raises(ValueError):
        _ = OdtBook(book_dir).chapters


@pytest.mark.xfail(reason="The \\id line hard-codes 'Sango [sag]' and \\rem a personal email address.")
def test_id_line_uses_book_language(make_book):
    sfm = OdtBook(make_book(), lang="Français [fra]", filename="41XXA.SFM", normalization_mode="NFC").to_sfm()
    id_line, rem_line = sfm.splitlines()[:2]
    assert "Français [fra]" in id_line and "Sango" not in id_line
    assert "@" not in rem_line


# --- Export of ODT content ---


@pytest.mark.xfail(raises=ValueError, reason="Hyperlinks (text:a) have no style, so to_sfm aborts.")
def test_hyperlink_exported(make_odt):
    path = make_odt([p("Text_20_body", 'see <text:a xlink:href="https://x.org">x.org</text:a> now')])
    assert "x.org" in OdtChapter(path).to_sfm("NFC")


@pytest.mark.xfail(
    raises=ValueError,
    reason="Span mapping uses automatic style names (T1, T2, ...), which LibreOffice "
    "renumbers per document; identical formatting under another name is unmapped.",
)
def test_span_mapping_independent_of_automatic_style_name(make_odt, tmp_path):
    bold_t3 = (
        '<style:style style:name="T3" style:family="text"><style:text-properties '
        'fo:font-weight="bold" style:font-weight-asian="bold" style:font-weight-complex="bold"/>'
        "</style:style>"
    )
    a = make_odt([p("Text_20_body", f"{span('T1', '1')} Text.")], directory=tmp_path / "a")
    b = make_odt([p("Text_20_body", f"{span('T3', '1')} Text.")], directory=tmp_path / "b", auto_styles=[bold_t3])
    assert OdtChapter(a).to_sfm("NFC") == OdtChapter(b).to_sfm("NFC")


def test_node_has_paragraph_descendent_with_text_after_first_child(make_odt):
    """Control case: nested paragraph is the first child."""
    path = make_odt([p("Text_20_body", "<draw:frame><draw:text-box>" + p("Quotations", "in") + "</draw:text-box></draw:frame>")])
    assert node_has_paragraph_descendent_with_text(OdtChapter(path).all_paragraphs[0])


@pytest.mark.xfail(reason="node_has_paragraph_descendent_with_text only inspects the first child.")
def test_node_has_paragraph_descendent_with_text_not_first_child(make_odt):
    frame = "<draw:frame><draw:text-box>" + p("Quotations", "in") + "</draw:text-box></draw:frame>"
    path = make_odt([p("Text_20_body", span("T2", "x") + frame)])
    assert node_has_paragraph_descendent_with_text(OdtChapter(path).all_paragraphs[0])


# --- SFM parsing ---


@pytest.mark.xfail(raises=IndexError, reason="A \\v line with no preceding paragraph crashes with IndexError.")
def test_verse_before_any_paragraph_gives_clear_error():
    with pytest.raises(ValueError, match="\\\\v"):
        _ = SfmChapter("\\c 1\n\\v 1 Text.\n").paragraphs


@pytest.mark.xfail(raises=ValueError, reason="A verse marker with no text fails to unpack.")
def test_verse_without_text():
    children = SfmParagraph("\\p\n\\v 5").children
    assert [(type(c).__name__, c.text) for c in children] == [("SfmSpan", "5")]


@pytest.mark.xfail(raises=FileNotFoundError, reason="SfmChapter.odt_styles reads a nonexistent ref.txt.")
def test_sfm_chapter_odt_styles():
    _ = SfmChapter("\\c 1\n\\p Text\n").odt_styles


# --- styles-reference parsing ---


@pytest.mark.xfail(reason="Duplicate styles in styles-reference silently override earlier entries.")
def test_conflicting_duplicate_style_warns(make_odt, write_ref, caplog):
    caplog.set_level(logging.WARNING, logger=PKG_LOGGER)
    chapter = OdtChapter(make_odt([p("Title", "T")], ref=None))
    write_ref("Title \\mt\nTitle \\s1\n", directory=chapter.file_path.parent)
    _ = chapter.sfm_ref
    assert warnings_mentioning(caplog, "Title")


@pytest.mark.xfail(reason="Text after the marker (e.g. an inline comment) becomes part of the marker.")
def test_inline_comment_in_styles_reference(make_odt, write_ref):
    chapter = OdtChapter(make_odt([p("Title", "T")], ref=None))
    write_ref("Title \\mt  # main title\n", directory=chapter.file_path.parent)
    assert chapter.sfm_ref == {"Title": "\\mt"}


# --- Import (SFM -> ODT) ---


@pytest.mark.xfail(reason="The lock-file check uses the source filename, not the destination's.")
def test_save_refuses_when_destination_is_open(make_odt, tmp_path):
    chapter = OdtChapter(make_odt([p("Text_20_body", "x")]))
    dest = tmp_path / "renamed.odt"
    (tmp_path / f".~lock.{dest.name}#").write_text("")
    with pytest.raises(OSError):
        chapter.save(dest)
