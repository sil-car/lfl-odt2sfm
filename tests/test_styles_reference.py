"""Tests for styles-reference.txt discovery and parsing (OdtChapter)."""

import pytest

from odt2sfm.odt import OdtChapter
from tests.conftest import REFERENCE_DIR, p, span


@pytest.fixture
def chapter(make_odt):
    path = make_odt([p("Text_20_body", "Hello")], ref=None)
    return OdtChapter(path)


def test_comments_blank_lines_tabs_and_spaces(chapter, write_ref):
    write_ref(
        "# a comment\n"
        "\n"
        "Title\t\\mt\n"
        "Text_20_body    \\p\n"
        "   Quotations \\q   \n"
        "#Commented_Style \\rem\n",
        directory=chapter.file_path.parent,
    )
    assert chapter.sfm_ref == {"Title": "\\mt", "Text_20_body": "\\p", "Quotations": "\\q"}


@pytest.mark.parametrize("line", ["NoMarkerHere", "Two \\p \\m"])
def test_malformed_line_raises(chapter, write_ref, line):
    write_ref(f"Title \\mt\n{line}\n", directory=chapter.file_path.parent)
    with pytest.raises(ValueError, match=line.split()[0]):
        _ = chapter.sfm_ref


def test_sfm_ref_setter(chapter):
    chapter.sfm_ref = {"X": "\\p"}
    assert chapter.sfm_ref == {"X": "\\p"}
    with pytest.raises(TypeError):
        chapter.sfm_ref = [("X", "\\p")]


def test_missing_reference_file_raises(chapter):
    with pytest.raises(ValueError, match="No valid styles-reference.txt"):
        _ = chapter.styles_reference_file


def test_lookup_precedence(chapter, write_ref):
    book_dir = chapter.file_path.parent
    parent = write_ref("A \\p\n", directory=book_dir.parent)
    assert chapter.styles_reference_file == parent

    chapter._styles_reference_file = None
    general = write_ref("A \\p\n", directory=book_dir)
    assert chapter.styles_reference_file == general

    chapter._styles_reference_file = None
    specific = write_ref(
        "A \\p\n", directory=book_dir, name=f"{chapter.file_path.stem}.styles-reference.txt"
    )
    assert chapter.styles_reference_file == specific


def test_styles_only_include_used_styles_with_text(make_odt):
    path = make_odt(
        [
            p("Title", "A title"),
            p("Text_20_body", ""),  # mapped, but no text
            p("Heading_20_1", f"{span('T1', '1')} text", tag="h"),
        ],
        ref={"Title": "\\mt", "Text_20_body": "\\p", "Quotations": "\\q", "T1": "\\v", "Heading_20_1": "\\s1"},
    )
    assert OdtChapter(path).styles == {"Title": "\\mt", "Heading_20_1": "\\s1", "T1": "\\v"}


def test_content_style_resolves_to_parent_document_style(make_odt):
    path = make_odt(
        [p("P9", "Body text via automatic style")],
        auto_styles=[
            (
                '<style:style style:name="P9" style:family="paragraph" '
                'style:parent-style-name="Text_20_body"/>'
            )
        ],
    )
    chapter = OdtChapter(path)
    assert "Text_20_body" in chapter.styles
    assert [para.style for para in chapter.paragraphs] == ["Text_20_body"]


@pytest.mark.parametrize("ref", sorted(REFERENCE_DIR.rglob("*styles-reference.txt")), ids=lambda x: x.name)
def test_committed_reference_files_parse(chapter, ref):
    """Every styles-reference file in reference/ parses and maps to SFM markers."""
    chapter._styles_reference_file = ref
    mapping = chapter.sfm_ref
    assert mapping
    for style, marker in mapping.items():
        assert style and " " not in style
        assert marker.startswith("\\") and len(marker) > 1
