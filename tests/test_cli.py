"""Tests for the command-line entry points declared in pyproject.toml."""

import logging
import sys
import unicodedata

import pytest

from odt2sfm import __version__
from odt2sfm.__main__ import main
from odt2sfm.base import get_timestamp
from odt2sfm.odt.__main__ import odt_paragraphs
from odt2sfm.scripts import normalize_files, normalize_project
from odt2sfm.sfm.__main__ import sfm_paragraphs

pytestmark = pytest.mark.cli


def run(monkeypatch, func, *args):
    """Call an entry point with the given argv.

    Entry points call logging.basicConfig, which does nothing if the root
    logger already has handlers (pytest's log capture adds some at the start
    of each test), so temporarily remove them, then close any file handler
    the entry point added. The package logger level is also reset so that
    the log file receives INFO messages.
    """
    monkeypatch.setattr(sys, "argv", ["prog", *map(str, args)])
    root = logging.getLogger()
    pkg = logging.getLogger("odt2sfm")  # tests/__init__.py sets it to ERROR
    saved, saved_level = root.handlers[:], pkg.level
    root.handlers = []
    pkg.setLevel(logging.NOTSET)
    try:
        return func()
    finally:
        for h in root.handlers:
            h.close()
        root.handlers = saved
        pkg.setLevel(saved_level)


def test_version(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, main, "--version")
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == __version__


def test_export(monkeypatch, make_book, tmp_path, capsys):
    book = make_book()
    dest = tmp_path / "41XXA.SFM"
    run(monkeypatch, main, book, dest)
    sfm = dest.read_text(encoding="utf-8")
    assert sfm.startswith('\\id XXA "Test_Luke-Q1"')
    assert "\\c 2" in sfm
    assert f"SFM data written to {dest}" in capsys.readouterr().out
    log = (book / "odt2sfm-export.log").read_text(encoding="utf-8")
    assert "Conversion type: OdtToSfm" in log


def test_export_nfd(monkeypatch, make_book, tmp_path):
    book = make_book(chapters={"L01": ['<text:p text:style-name="Title">Leçon</text:p>']})
    dest = tmp_path / "41XXA.SFM"
    run(monkeypatch, main, "-m", "NFD", book, dest)
    assert unicodedata.normalize("NFD", "\\mt Leçon") in dest.read_text(encoding="utf-8")


def test_import(monkeypatch, make_book, tmp_path):
    book = make_book()
    sfm_path = tmp_path / "41XXA.sfm"
    run(monkeypatch, main, book, sfm_path)
    sfm_path.write_text(
        sfm_path.read_text(encoding="utf-8").replace("Lesson two title", "Leçon deux"),
        encoding="utf-8",
    )
    run(monkeypatch, main, sfm_path, book)
    updated = book.with_name(f"{book.name}_updated_{get_timestamp()}")
    assert sorted(f.name for f in updated.glob("*.odt")) == sorted(f.name for f in book.glob("*.odt"))
    assert "Conversion type: SfmToOdt" in (book / "odt2sfm-import.log").read_text(encoding="utf-8")


def test_invalid_source(monkeypatch, tmp_path):
    src = tmp_path / "file.txt"
    src.write_text("x")
    with pytest.raises(ValueError, match="Invalid source"):
        run(monkeypatch, main, src, tmp_path / "out.sfm")


def test_import_requires_destination_dir(monkeypatch, tmp_path):
    src = tmp_path / "41XXA.sfm"
    src.write_text("\\id XXA\n")
    with pytest.raises(ValueError, match="requires a destination dir"):
        run(monkeypatch, main, src, tmp_path / "missing")


def test_bad_normalization_mode(monkeypatch, make_book, tmp_path):
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, main, "-m", "NFKC", make_book(), tmp_path / "x.sfm")
    assert exc.value.code == 2


def test_odt_paragraphs(monkeypatch, capsys, make_odt):
    path = make_odt(
        [
            '<text:p text:style-name="Title">A title</text:p>',
            '<text:p text:style-name="Table_20_Contents">Unmapped</text:p>',
        ]
    )
    run(monkeypatch, odt_paragraphs, path)
    assert capsys.readouterr().out.splitlines() == ["[Title] A title"]

    run(monkeypatch, odt_paragraphs, "--all", path)
    assert capsys.readouterr().out.splitlines() == [
        "[Title] A title",
        "[Table_20_Contents] (skipped) Unmapped",
    ]


def test_sfm_paragraphs(monkeypatch, capsys, book_sfm):
    run(monkeypatch, sfm_paragraphs, "-c", "2", book_sfm)
    assert capsys.readouterr().out.splitlines()[0] == '[\\s2] "H2" Section Header'

    run(monkeypatch, sfm_paragraphs, book_sfm)
    out = capsys.readouterr().out
    assert "[\\id]" not in out and "[\\mt] Chapter title information, etc." in out


def test_normalize_files(monkeypatch, tmp_path):
    f = tmp_path / "41XXA.SFM"
    f.write_text("\\p café\n", encoding="utf-8")
    run(monkeypatch, normalize_files.main, "-b", "NFD", f)
    assert f.read_text(encoding="utf-8") == "\\p café\n"
    assert (tmp_path / "41XXA.SFM.prenormalize.bak").is_file()


def test_normalize_files_rejects_missing_file(monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        run(monkeypatch, normalize_files.main, "NFC", tmp_path / "missing.SFM")


def test_normalize_project(monkeypatch, tmp_path):
    (tmp_path / "unique.id").write_text("x")
    sfm_files = [tmp_path / "41XXA.SFM", tmp_path / "42XXB.sfm"]
    for f in sfm_files:
        f.write_text("\\p café\n", encoding="utf-8")
    other = tmp_path / "notes.txt"
    other.write_text("café", encoding="utf-8")
    run(monkeypatch, normalize_project.main, "NFC", tmp_path)
    assert all(f.read_text(encoding="utf-8") == "\\p café\n" for f in sfm_files)
    assert other.read_text(encoding="utf-8") == "café"


def test_normalize_project_rejects_non_paratext_dir(monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        run(monkeypatch, normalize_project.main, "NFC", tmp_path)
