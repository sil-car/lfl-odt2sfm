"""End-to-end export/import round-trip tests.

Export: ODT book folder -> SFM text (OdtBook.to_sfm)
Import: SFM file + ODT book folder -> updated ODT copies (OdtBook.update_text)

Set UPDATE_GOLDEN=1 to regenerate tests/data/expected/*.SFM after an
intentional output change.
"""

import os
import re
import shutil
import unicodedata
from pathlib import Path

import pytest

from odt2sfm.base import SFM_ONLY_MARKERS, verify_paragraph_children_count
from odt2sfm.odt import OdtBook, OdtChapter
from odt2sfm.sfm import SfmBook
from tests.conftest import EXPECTED_DIR, L02_BODY, REAL_SFM_NAME

SYNTH_SFM_NAME = "41XXA.SFM"
REM_LINE = re.compile(r"^\\rem .*$", re.MULTILINE)


def export(book_dir: Path, filename: str, form: str = "NFC") -> str:
    return OdtBook(book_dir, filename=filename, normalization_mode=form).to_sfm()


def import_sfm(book_dir: Path, sfm_text: str, filename: str, form: str = "NFC") -> Path:
    """Import SFM text into copies of book_dir's ODTs; return the new book dir.

    The new dir has the same name as the original (so re-exports are
    comparable) and gets copies of the styles-reference files.
    """
    work = book_dir.parent / "import"
    work.mkdir(exist_ok=True)
    sfm_path = work / filename
    sfm_path.write_text(sfm_text, encoding="utf-8")
    out_root = work / "out"
    out_root.mkdir(exist_ok=True)
    out = out_root / book_dir.name
    OdtBook(book_dir, normalization_mode=form).update_text(SfmBook(sfm_path), out)
    for ref in book_dir.glob("*.txt"):
        shutil.copy(ref, out)
    return out


def odt_texts(book_dir: Path) -> dict[str, list[str]]:
    return {
        f.name: [para.text_recursive for para in OdtChapter(f).all_paragraphs]
        for f in sorted(book_dir.glob("*.odt"))
    }


def strip_rem(sfm: str) -> str:
    """The \\rem line contains today's date."""
    return REM_LINE.sub("\\\\rem", sfm)


# --- Export golden file ---


@pytest.mark.realdata
def test_export_matches_golden(real_book):
    sfm = strip_rem(export(real_book, REAL_SFM_NAME))
    golden = EXPECTED_DIR / REAL_SFM_NAME
    if os.environ.get("UPDATE_GOLDEN"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(sfm, encoding="utf-8", newline="\n")
    assert sfm == golden.read_text(encoding="utf-8")


# --- Parity between ODT paragraphs and exported SFM paragraphs ---


@pytest.mark.realdata
def test_paragraph_and_children_parity(real_book, tmp_path):
    sfm_path = tmp_path / REAL_SFM_NAME
    sfm_path.write_text(export(real_book, REAL_SFM_NAME), encoding="utf-8")
    odt_chapters = OdtBook(real_book).chapters
    sfm_chapters = SfmBook(sfm_path).chapters
    assert sorted(odt_chapters) == [c.number for c in sfm_chapters]
    for sfm_ch in sfm_chapters:
        odt_ch = odt_chapters[sfm_ch.number]
        sfm_ps = [p for p in sfm_ch.paragraphs if p.marker not in SFM_ONLY_MARKERS]
        assert len(sfm_ps) == len(odt_ch.paragraphs), f"chapter {sfm_ch.number}"
        for i, (sp, op) in enumerate(zip(sfm_ps, odt_ch.paragraphs)):
            assert verify_paragraph_children_count(sp, op) == 0, f"ch {sfm_ch.number} p {i}"
            assert sp.marker == odt_ch.styles[op.style]


# --- Identity round trip: import unchanged SFM ---


@pytest.mark.realdata
def test_identity_roundtrip_sfm_unchanged_real(real_book):
    sfm1 = export(real_book, REAL_SFM_NAME)
    out = import_sfm(real_book, sfm1, REAL_SFM_NAME)
    assert export(out, REAL_SFM_NAME) == sfm1


@pytest.mark.realdata
@pytest.mark.xfail(
    reason="Importing unchanged SFM alters ODT text: line breaks (text:line-break) are "
    "deleted and trailing whitespace of some text runs changes."
)
def test_identity_roundtrip_odt_text_unchanged_real(real_book):
    before = odt_texts(real_book)
    out = import_sfm(real_book, export(real_book, REAL_SFM_NAME), REAL_SFM_NAME)
    assert odt_texts(out) == before


def test_identity_roundtrip_without_verses(make_book):
    book = make_book(chapters={"L02": L02_BODY})
    sfm1 = export(book, SYNTH_SFM_NAME)
    out = import_sfm(book, sfm1, SYNTH_SFM_NAME)
    assert export(out, SYNTH_SFM_NAME) == sfm1
    assert odt_texts(out) == odt_texts(book)


@pytest.mark.xfail(
    reason="Text following a verse span loses its leading space on import "
    "('1 First verse.' becomes '1First verse.')."
)
def test_identity_roundtrip_with_verses(make_book):
    book = make_book()
    sfm1 = export(book, SYNTH_SFM_NAME)
    out = import_sfm(book, sfm1, SYNTH_SFM_NAME)
    assert odt_texts(out) == odt_texts(book)
    assert export(out, SYNTH_SFM_NAME) == sfm1


# --- Edit round trip: import modified SFM ---


def test_edit_roundtrip_plain_text(make_book):
    book = make_book()
    sfm1 = export(book, SYNTH_SFM_NAME)
    sfm2 = (
        sfm1.replace("\\mt Lesson two title", "\\mt Leçon deux")
        .replace("\\s2 Subsection", "\\s2 Sous-section")
        .replace("no~break space.", "espace~insécable.")
    )
    out = import_sfm(book, sfm2, SYNTH_SFM_NAME)
    l02 = odt_texts(out)["Test_Luke-Q1-L02.odt"]
    assert l02 == [
        "Leçon deux",
        "Sous-section",
        "Plain paragraph with espace insécable.",
    ]
    # Compare only the edited chapter; L01 is affected by the verse-space bug
    # (see test_identity_roundtrip_with_verses).
    assert export(out, SYNTH_SFM_NAME).split("\\c 2")[1] == sfm2.split("\\c 2")[1]


def test_edit_roundtrip_span_text(make_book):
    book = make_book()
    sfm2 = export(book, SYNTH_SFM_NAME).replace("\\bd bold\\bd*", "\\bd gras\\bd*")
    out = import_sfm(book, sfm2, SYNTH_SFM_NAME)
    chapter = OdtChapter(out / "Test_Luke-Q1-L01.odt")
    spans = [s.text for para in chapter.paragraphs for s in para.spans]
    assert spans == ["1", "2", "gras", "3"]
    assert "\\bd gras\\bd*" in export(out, SYNTH_SFM_NAME)


@pytest.mark.parametrize("form", ["NFC", "NFD"])
def test_edit_roundtrip_normalizes_input(make_book, form):
    book = make_book()
    other = "NFD" if form == "NFC" else "NFC"
    title = unicodedata.normalize(other, "Leçon été")
    sfm2 = export(book, SYNTH_SFM_NAME).replace("Lesson two title", title)
    out = import_sfm(book, sfm2, SYNTH_SFM_NAME, form=form)
    assert odt_texts(out)["Test_Luke-Q1-L02.odt"][0] == unicodedata.normalize(form, title)


@pytest.mark.realdata
def test_edit_roundtrip_real(real_book):
    sfm1 = export(real_book, REAL_SFM_NAME)
    assert "\\iq Bangui\n" in sfm1
    sfm2 = sfm1.replace("\\iq Bangui\n", "\\iq Bangî\n")
    out = import_sfm(real_book, sfm2, REAL_SFM_NAME)
    assert "Bangî" in odt_texts(out)["Sango_Luke-Q1-TOC.odt"]
    assert export(out, REAL_SFM_NAME) == sfm2


# --- Mismatch rejection ---


@pytest.mark.parametrize(
    ("old", "new"),
    [
        pytest.param("\\mt Table of contents\n", "\\mt Table of contents\n\\p Extra\n", id="extra-paragraph"),
        pytest.param("\\p Lesson 1 summary.\n", "", id="missing-paragraph"),
        pytest.param("\\mt Table of contents", "\\s1 Table of contents", id="wrong-marker"),
    ],
)
def test_mismatch_in_first_chapter_rejected_before_writing(make_book, old, new):
    book = make_book()
    sfm = export(book, SYNTH_SFM_NAME).replace(old, new, 1)
    with pytest.raises(ValueError):
        import_sfm(book, sfm, SYNTH_SFM_NAME)
    assert not (book.parent / "import" / "out" / book.name).exists()


@pytest.mark.xfail(
    reason="Chapters are verified one at a time, so earlier chapters are already "
    "written when a later chapter fails verification."
)
def test_mismatch_in_later_chapter_rejected_before_writing(make_book):
    book = make_book()
    sfm = export(book, SYNTH_SFM_NAME).replace("\\s2 Subsection", "\\s1 Subsection")
    with pytest.raises(ValueError):
        import_sfm(book, sfm, SYNTH_SFM_NAME)
    assert not (book.parent / "import" / "out" / book.name).exists()
