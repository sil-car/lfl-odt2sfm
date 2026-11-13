"""Tests for OdtBook export (to_sfm) and import (update_text)."""

import pytest

from odt2sfm.base import get_timestamp
from odt2sfm.odt import OdtBook, OdtChapter
from odt2sfm.sfm import SfmBook


@pytest.mark.parametrize(
    ("filename", "book_id"),
    [("42LUKSAG.SFM", "LUK"), ("94XXALtdLS.SFM", "XXA"), (None, None)],
)
def test_book_id(tmp_path, filename, book_id):
    assert OdtBook(tmp_path, filename=filename).book_id == book_id


def test_book_id_invalid_filename(tmp_path):
    with pytest.raises(ValueError, match="##AAA"):
        _ = OdtBook(tmp_path, filename="LUK.SFM").book_id


def test_language_property(tmp_path):
    book = OdtBook(tmp_path)
    assert book.language == ""
    book.language = 123
    assert book.language == "123"


def test_chapters_keyed_by_number(make_book):
    book = OdtBook(make_book())
    # Dict order follows filename sort ("-L01" < "-TOC"); to_sfm pops 0 first.
    assert sorted(book.chapters) == [0, 1, 2]
    assert all(isinstance(c, OdtChapter) for c in book.chapters.values())
    assert str(book) == book.name == "Test_Luke-Q1"


def test_to_sfm_requires_normalization_mode(make_book):
    with pytest.raises(ValueError, match="normalization mode"):
        OdtBook(make_book(), filename="41XXA.SFM").to_sfm()


def test_to_sfm_full_book(make_book):
    sfm = OdtBook(make_book(), filename="41XXA.SFM", normalization_mode="NFC").to_sfm()
    lines = sfm.splitlines()
    assert lines[0].startswith('\\id XXA "Test_Luke-Q1"')
    assert lines[1].startswith("\\rem ") and get_timestamp() in lines[1]
    assert lines[2] == "\\usfm 3.0"
    assert lines[3:] == [
        "\\mt Table of contents",
        "\\p Lesson 1 summary.",
        "\\c 1",
        "\\mt Lesson one title",
        "\\s1 First section",
        "\\p ",
        "\\v 1 First verse. ",
        "\\v 2 Second \\bd bold\\bd* verse.",
        "\\q ",
        "\\v 3 A quote.",
        "\\c 2",
        "\\mt Lesson two title",
        "\\s2 Subsection",
        "\\p Plain paragraph with no~break space.",
    ]
    assert sfm.endswith("\n") and not sfm.endswith("\n\n")


def test_to_sfm_selected_chapters(make_book):
    sfm = OdtBook(make_book(), filename="41XXA.SFM", normalization_mode="NFC").to_sfm(chapters="0,2")
    assert "\\c 2" in sfm and "\\c 1" not in sfm


def test_to_sfm_unknown_chapter_raises(make_book):
    book = OdtBook(make_book(), filename="41XXA.SFM", normalization_mode="NFC")
    with pytest.raises(TypeError, match="Chapter not found"):
        book.to_sfm(chapters="0,9")


def test_update_text_requires_normalization_mode(make_book, tmp_path):
    with pytest.raises(TypeError, match="normalization mode"):
        OdtBook(make_book()).update_text(SfmBook(), tmp_path / "out")


def test_update_text_writes_copies_and_leaves_originals(make_book, tmp_path):
    book_dir = make_book()
    book = OdtBook(book_dir, filename="41XXA.SFM", normalization_mode="NFC")
    sfm_path = tmp_path / "41XXA.SFM"
    sfm_path.write_text(book.to_sfm().replace("Lesson two title", "Leçon deux"), encoding="utf-8")
    originals = {f.name: f.read_bytes() for f in book_dir.glob("*.odt")}

    out_dir = tmp_path / "updated"
    OdtBook(book_dir, normalization_mode="NFC").update_text(SfmBook(sfm_path), out_dir)

    assert {f.name: f.read_bytes() for f in book_dir.glob("*.odt")} == originals
    assert sorted(f.name for f in out_dir.glob("*.odt")) == sorted(originals)
    titles = [p.text_recursive for p in OdtChapter(out_dir / "Test_Luke-Q1-L02.odt").all_paragraphs]
    assert titles[0] == "Leçon deux"


def test_update_text_chapter_missing_from_odt_raises(make_book, tmp_path):
    sfm_path = tmp_path / "41XXA.SFM"
    sfm_path.write_text(
        "\\id XXA\n\\mt Table of contents\n\\p Lesson 1 summary.\n\\c 5\n\\mt Nope\n",
        encoding="utf-8",
    )
    book = OdtBook(make_book(), normalization_mode="NFC")
    with pytest.raises(TypeError, match='"5" not found'):
        book.update_text(SfmBook(sfm_path), tmp_path / "out")
