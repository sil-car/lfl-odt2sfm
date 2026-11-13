"""Tests for odt2sfm.conversions."""

import pytest

from odt2sfm import OdtChapter, OdtToSfm, SfmBook, SfmToOdt
from odt2sfm.base import get_timestamp
from odt2sfm.conversions import Conversion


def test_validate_path(tmp_path):
    odt_dir = tmp_path / "book.odt"
    odt_dir.mkdir()
    sfm_file = tmp_path / "41XXA.sfm"
    sfm_file.write_text("\\id XXA\n")
    Conversion._validate_path(odt_dir)
    Conversion._validate_path(sfm_file)
    with pytest.raises(ValueError, match="root folder"):
        Conversion._validate_path(tmp_path / "file.odt")
    with pytest.raises(ValueError, match="readable file"):
        Conversion._validate_path(tmp_path / "missing.sfm")


def test_path_setters_validate_and_record_format(tmp_path):
    sfm_file = tmp_path / "41XXA.sfm"
    sfm_file.write_text("\\id XXA\n")
    conv = Conversion(source=tmp_path, destination=tmp_path)
    conv.source_path = sfm_file
    conv.destination_path = tmp_path
    assert (conv.source_format, conv.destination_format) == (".sfm", "")
    with pytest.raises(ValueError):
        conv.source_path = tmp_path / "missing.sfm"
    with pytest.raises(NotImplementedError):
        conv.run()


def test_odt_to_sfm(make_book, tmp_path, capsys):
    book = make_book()
    dest = tmp_path / "41XXA.SFM"
    conv = OdtToSfm(source=book, destination=dest, normalization_mode="NFC")
    assert conv.odt_book.book_id == "XXA"
    conv.run()
    assert dest.read_text(encoding="utf-8").startswith('\\id XXA "Test_Luke-Q1"')
    assert "SFM data written" in capsys.readouterr().out


def test_sfm_to_odt_writes_sibling_updated_dir(make_book, tmp_path):
    book = make_book()
    sfm = tmp_path / "41XXA.SFM"
    OdtToSfm(source=book, destination=sfm, normalization_mode="NFC").run()
    SfmToOdt(source=sfm, destination=book, normalization_mode="NFC").run()
    updated = book.with_name(f"{book.name}_updated_{get_timestamp()}")
    assert sorted(f.name for f in updated.iterdir()) == sorted(f.name for f in book.glob("*.odt"))


def test_compare_odt_chapter_with_sfm_chapter(chapter_odt, book_sfm, capsys):
    odt_chapter = OdtChapter(chapter_odt)
    odt_chapter.sfm_ref = {**odt_chapter.sfm_ref, "T2": "\\bd"}
    SfmToOdt.compare_odt_chapter_with_sfm_chapter(odt_chapter, SfmBook(book_sfm).chapters[3])
    out = capsys.readouterr().out
    assert '[Title] "Chapter title information, etc."' in out
    assert '[\\mt] "Chapter title information, etc."' in out
