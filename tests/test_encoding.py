"""Files are read and written as UTF-8 regardless of the system locale.

On Windows, Python's default text encoding is the ANSI code page (e.g.
cp1252) rather than UTF-8. These tests simulate a non-UTF-8 system by running
odt2sfm in a subprocess with an ASCII-only locale (C locale, with Python's
UTF-8 mode and locale coercion disabled).
"""

import os
import subprocess
import sys
import unicodedata

import pytest

from odt2sfm.base import get_timestamp
from odt2sfm.normalize import normalize_file
from odt2sfm.odt import OdtChapter
from odt2sfm.sfm import SfmBook
from tests.conftest import DEFAULT_REF, p, ref_text

ASCII_LOCALE_ENV = {**os.environ, "LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX locale variables")


def run_ascii_locale(code: str, *args) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-c", code, *map(str, args)],
        env=ASCII_LOCALE_ENV,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert b"Logging error" not in result.stderr, result.stderr.decode(errors="replace")
    return result


def test_ascii_locale_is_really_ascii():
    """Guard: the simulated locale must make Python's default encoding ASCII."""
    result = run_ascii_locale("import locale; print(locale.getencoding())")
    assert result.stdout.decode().strip() in {"ANSI_X3.4-1968", "ascii", "US-ASCII"}


@posix_only
def test_sfm_read_as_utf8_regardless_of_locale(tmp_path):
    sfm = tmp_path / "41XXA.SFM"
    sfm.write_text("\\id XXA\n\\c 1\n\\p café\n", encoding="utf-8")
    code = (
        "import sys; from odt2sfm import SfmBook; "
        "t = SfmBook(sys.argv[1]).chapters[1].paragraphs[0].text; "
        "sys.stdout.buffer.write(t.encode('utf-8'))"
    )
    assert run_ascii_locale(code, sfm).stdout.decode("utf-8") == "café"


@pytest.mark.cli
@posix_only
def test_cli_export_and_import_regardless_of_locale(make_book, tmp_path):
    """Export, edit and import non-ASCII text, including the log files and a
    styles-reference containing non-ASCII characters."""
    ref = "# Styles des leçons — référence\n" + ref_text(DEFAULT_REF)
    book = make_book(
        chapters={"L01": [p("Title", "Leçon ê ë"), p("Text_20_body", "Kôlï na mbï.")]},
        ref=ref,
    )
    sfm = tmp_path / "41XXA.SFM"
    cli = "from odt2sfm.__main__ import main; main()"

    run_ascii_locale(cli, book, sfm)
    exported = sfm.read_text(encoding="utf-8")
    assert "\\mt Leçon ê ë" in exported

    sfm.write_text(exported.replace("mbï", "âla"), encoding="utf-8")
    run_ascii_locale(cli, sfm, book)
    updated = book.with_name(f"{book.name}_updated_{get_timestamp()}")
    texts = [para.text_recursive for para in OdtChapter(updated / "Test_Luke-Q1-L01.odt").all_paragraphs]
    assert texts == ["Leçon ê ë", "Kôlï na âla."]
    assert "âla" in (book / "odt2sfm-import.log").read_text(encoding="utf-8")


@posix_only
def test_normalize_file_regardless_of_locale(tmp_path):
    f = tmp_path / "41XXA.SFM"
    f.write_text("\\p café\n", encoding="utf-8")
    run_ascii_locale(
        "import sys; from pathlib import Path; from odt2sfm.normalize import normalize_file; "
        "normalize_file('NFD', Path(sys.argv[1]))",
        f,
    )
    assert f.read_text(encoding="utf-8") == "\\p café\n"


# --- Byte-order mark (BOM) ---


def test_styles_reference_with_bom(make_odt, write_ref):
    chapter = OdtChapter(make_odt([p("Title", "T")], ref=None))
    write_ref(DEFAULT_REF, directory=chapter.file_path.parent, encoding="utf-8-sig")
    assert chapter.sfm_ref == DEFAULT_REF


def test_sfm_with_bom(tmp_path):
    sfm = tmp_path / "41XXA.SFM"
    sfm.write_text("\\id XXA Title\n\\mt T\n\\c 1\n\\p Text\n", encoding="utf-8-sig")
    book = SfmBook(sfm)
    assert book.id_text == "XXA Title"
    assert [c.number for c in book.chapters] == [0, 1]
    assert book.chapters[0].paragraphs[0].marker == "\\id"


# --- normalize_file changes nothing but the normalization ---


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("\\p café\r\n\\p deux\r\n", id="crlf"),
        pytest.param("﻿\\p café\n", id="bom"),
        pytest.param("\\p café", id="no-final-newline"),
    ],
)
def test_normalize_file_preserves_file_format(tmp_path, raw):
    f = tmp_path / "41XXA.SFM"
    f.write_bytes(raw.encode("utf-8"))
    normalize_file("NFC", f)
    assert f.read_bytes() == unicodedata.normalize("NFC", raw).encode("utf-8")
