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
from odt2sfm.odt.elements import strip_newlines
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
    assert export(out, SYNTH_SFM_NAME) == sfm2


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


def test_mismatch_in_later_chapter_rejected_before_writing(make_book):
    book = make_book()
    sfm = export(book, SYNTH_SFM_NAME).replace("\\s2 Subsection", "\\s1 Subsection")
    with pytest.raises(ValueError):
        import_sfm(book, sfm, SYNTH_SFM_NAME)
    assert not (book.parent / "import" / "out" / book.name).exists()


# --- Import preserves what SFM cannot represent, unless edited ---


def test_edit_after_verse_keeps_separator_space(make_book):
    book = make_book()
    sfm2 = export(book, SYNTH_SFM_NAME).replace("\\v 1 First verse.", "\\v 1 Premier verset.")
    out = import_sfm(book, sfm2, SYNTH_SFM_NAME)
    l01 = odt_texts(out)["Test_Luke-Q1-L01.odt"]
    assert l01[2] == "1 Premier verset. 2 Second bold verse."
    assert export(out, SYNTH_SFM_NAME) == sfm2


def test_unedited_text_keeps_original_normalization(make_book):
    """Accepted behavior: only edited text takes the import normalization
    mode, so a document can end up with mixed normalization."""
    nfd_title = unicodedata.normalize("NFD", "Leçon originale")
    body = [
        f'<text:p text:style-name="Title">{nfd_title}</text:p>',
        '<text:p text:style-name="Text_20_body">To be edited.</text:p>',
    ]
    book = make_book(chapters={"L01": body})
    sfm2 = export(book, SYNTH_SFM_NAME).replace("To be edited.", unicodedata.normalize("NFD", "Édité."))
    out = import_sfm(book, sfm2, SYNTH_SFM_NAME, form="NFC")
    title, edited = odt_texts(out)["Test_Luke-Q1-L01.odt"]
    assert title == nfd_title
    assert edited == unicodedata.normalize("NFC", "Édité.")


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        pytest.param(None, None, "abc\ndef", id="unedited-keeps-newline"),
        pytest.param("abc def", "uvw xyz", "uvw xyz", id="edited-replaced"),
    ],
)
def test_literal_newline_on_import(make_book, old, new, expected):
    body = ['<text:p text:style-name="Text_20_body">abc\ndef</text:p>']
    book = make_book(chapters={"L01": body})
    sfm = export(book, SYNTH_SFM_NAME)
    assert "\\p abc def" in sfm
    if old:
        sfm = sfm.replace(old, new)
    out = import_sfm(book, sfm, SYNTH_SFM_NAME)
    assert odt_texts(out)["Test_Luke-Q1-L01.odt"] == [expected]


def test_fill_in_the_blank_roundtrip(make_book):
    """A blank ("______") after a space isn't read as a part separator."""
    body = [
        '<text:p text:style-name="Text_20_body">Na ya ti ______ pepe? ( Lamba)</text:p>',
        '<text:p text:style-name="Text_20_body">Na ______<text:s/>( Ta)</text:p>',
    ]
    book = make_book(chapters={"L01": body})
    sfm = export(book, SYNTH_SFM_NAME)
    assert "\\p Na ya ti ______ pepe? ( Lamba)" in sfm
    assert "\\p Na ______ _( Ta)" in sfm
    sfm = sfm.replace("pepe?", "pepe ?").replace("( Ta)", "(Ta)")
    out = import_sfm(book, sfm, SYNTH_SFM_NAME)
    assert odt_texts(out)["Test_Luke-Q1-L01.odt"] == ["Na ya ti ______ pepe ? ( Lamba)", "Na ______ (Ta)"]


def test_part_count_mismatch_rejected_before_writing(make_book):
    """A translator removed a character style: the paragraph can't be
    imported piece by piece, so the whole import is refused."""
    book = make_book()
    sfm = export(book, SYNTH_SFM_NAME).replace("\\bd bold\\bd*", "gras")
    with pytest.raises(ValueError, match=r"ch\. 1, paragraph 3 \(\\p\): SFM has 4 parts, ODT has 6"):
        import_sfm(book, sfm, SYNTH_SFM_NAME)
    assert not (book.parent / "import" / "out" / book.name).exists()


def test_all_mismatches_reported_together(make_book):
    book = make_book()
    sfm = (
        export(book, SYNTH_SFM_NAME)
        .replace("\\bd bold\\bd*", "gras")  # ch. 1: missing part
        .replace("\\s2 Subsection", "\\s1 Subsection")  # ch. 2: wrong marker
    )
    with pytest.raises(ValueError, match="2 problem") as exc:
        import_sfm(book, sfm, SYNTH_SFM_NAME)
    message = str(exc.value)
    assert "nothing was written" in message
    assert "- ch. 1, paragraph 3" in message and "- ch. 2, paragraph 2" in message


# --- Character spans: \no fallback and hyperlinks ---


def test_edit_roundtrip_automatic_style_fallback(make_book):
    body = [
        '<text:p text:style-name="Text_20_body">Lead <text:span text:style-name="T5">odd</text:span> tail</text:p>'
    ]
    book = make_book(chapters={"L01": body})
    sfm = export(book, SYNTH_SFM_NAME)
    assert "\\p Lead \\zodt odd\\zodt* tail" in sfm
    out = import_sfm(book, sfm.replace("\\zodt odd\\zodt*", "\\zodt étrange\\zodt*"), SYNTH_SFM_NAME)
    assert odt_texts(out)["Test_Luke-Q1-L01.odt"] == ["Lead étrange tail"]


@pytest.mark.realdata
def test_edit_roundtrip_real_hyperlink(real_book):
    """The TOC's email link is a text:a wrapping a text:span (T8)."""
    sfm1 = export(real_book, REAL_SFM_NAME)
    old = "\\png chris_jackson@sil.org\\png*"
    assert old in sfm1
    sfm2 = sfm1.replace(old, "\\png contact@example.org\\png*")
    out = import_sfm(real_book, sfm2, REAL_SFM_NAME)
    # The link text is replaced; its address isn't in the SFM, so it's kept.
    toc = odt_texts(out)["Sango_Luke-Q1-TOC.odt"]
    assert "[contact@example.org](mailto:chris_jackson@sil.org)" in toc
    assert export(out, REAL_SFM_NAME) == sfm2


# --- text:s spacers (other tools split ODT text at these) ---

RE_MARKER = re.compile(r"(\\[a-z]+[0-9]*\*?)")
EDIT_CHAR = "ā"  # ā: not in the real data, so the edit can be undone


def edit_every_text(sfm: str) -> str:
    """Change every piece of text (a -> ā), keeping markers and separators."""
    lines = []
    for line in sfm.splitlines(keepends=True):
        if line.startswith(("\\id", "\\rem", "\\usfm", "\\c ")):
            lines.append(line)
            continue
        parts = RE_MARKER.split(line)
        lines.append("".join(p if RE_MARKER.fullmatch(p) else p.replace("a", EDIT_CHAR) for p in parts))
    return "".join(lines)


def spacer_layout(paragraph_node) -> list[tuple]:
    """Each text:s in the paragraph: its parent tag, count, and the text before it."""
    layout = []
    for s in paragraph_node.get_elements("descendant::text:s"):
        parent = s.parent
        siblings = [c._xml_element for c in parent.children]
        i = siblings.index(s._xml_element)
        before = parent.text if i == 0 else parent.children[i - 1].tail
        layout.append((parent.tag, s.get_attribute("text:c"), (before or "").replace(EDIT_CHAR, "a")))
    return layout


@pytest.mark.realdata
def test_full_edit_keeps_spacers_real(real_book):
    """Translating every text keeps each text:s spacer in place and encoded
    as LibreOffice wrote it, both directly in paragraphs (exported as ' _')
    and inside character spans (exported as plain spaces)."""
    sfm = export(real_book, REAL_SFM_NAME)
    assert EDIT_CHAR not in sfm
    out = import_sfm(real_book, edit_every_text(sfm), REAL_SFM_NAME)
    n_spacers = 0
    for f in sorted(real_book.glob("*.odt")):
        before = OdtChapter(f).paragraphs
        after = OdtChapter(out / f.name).paragraphs
        assert len(before) == len(after)
        for a, b in zip(before, after):
            assert [c.tag for c in a.node.children] == [c.tag for c in b.node.children]
            layout_a = spacer_layout(a.node)
            layout_b = spacer_layout(b.node)
            # Edited text takes the import normalization and loses literal
            # newlines (see strip_newlines), so compare in that form.
            def comparable(layout):
                return [(t, c, unicodedata.normalize("NFC", strip_newlines(s))) for t, c, s in layout]

            assert comparable(layout_a) == comparable(layout_b)
            n_spacers += len(layout_a)
    assert n_spacers > 100  # guard: the fixture really contains spacers
