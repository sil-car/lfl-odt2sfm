"""Shared pytest fixtures for odt2sfm tests.

The ``make_odt`` factory builds small, targeted ODT documents by taking
``tests/data/chapter.odt`` as a template (so that its named "Document" styles
in styles.xml are available) and replacing its body with the given XML
snippets. Namespace prefixes (``text:``, ``style:``, ``table:``) can be used
freely in snippets; odfdo resolves them.

Paragraph styles available from the template's styles.xml include:
``Title``, ``Heading_20_1``, ``Heading_20_2``, ``Text_20_body``,
``Quotations``, ``Table_20_Contents``, ``Table_20_Heading``.
Automatic (content) styles available: ``P1`` (parent ``Table_20_Contents``),
``P2`` (parent ``Table_20_Heading``), ``T1``, ``T2`` (text, no parent).
"""

import shutil
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest
from odfdo import Document, Element

DATA_DIR = Path(__file__).parent / "data"
CHAPTER_ODT = DATA_DIR / "chapter.odt"
BOOK_SFM = DATA_DIR / "book.sfm"
REAL_DIR = DATA_DIR / "real"
REAL_BOOK_NAME = "Sango_Luke-Q1"
REAL_SFM_NAME = "94XXALtdLS.SFM"
EXPECTED_DIR = DATA_DIR / "expected"
REFERENCE_DIR = Path(__file__).parents[1] / "reference"

# Default mapping used by synthetic books.
DEFAULT_REF = {
    "Title": "\\mt",
    "Heading_20_1": "\\s1",
    "Heading_20_2": "\\s2",
    "Text_20_body": "\\p",
    "Quotations": "\\q",
    "T1": "\\v",
    "T2": "\\bd",
}


def p(style: str, inner: str, tag: str = "p") -> str:
    """Return an XML snippet for a paragraph (or heading with tag="h")."""
    return f'<text:{tag} text:style-name="{style}">{inner}</text:{tag}>'


def span(style: str, inner: str) -> str:
    return f'<text:span text:style-name="{style}">{inner}</text:span>'


def ref_text(mapping: dict[str, str]) -> str:
    return "".join(f"{k}\t{v}\n" for k, v in mapping.items())


def build_odt(
    dest: Path,
    body: Iterable[str],
    auto_styles: Iterable[str] = (),
) -> Path:
    """Write an ODT at ``dest`` whose body consists of the given snippets."""
    doc = Document(CHAPTER_ODT)
    text_body = doc.body
    for child in list(text_body.children):
        if child.tag != "text:sequence-decls":
            text_body.delete(child)
    for snippet in body:
        text_body.append(Element.from_tag(snippet))
    if auto_styles:
        auto = doc.content.get_element("//office:automatic-styles")
        assert auto is not None
        for snippet in auto_styles:
            auto.append(Element.from_tag(snippet))
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dest))
    return dest


@pytest.fixture
def chapter_odt() -> Path:
    return CHAPTER_ODT


@pytest.fixture
def book_sfm() -> Path:
    return BOOK_SFM


@pytest.fixture
def write_ref(tmp_path) -> Callable[..., Path]:
    """Write a styles-reference file. Accepts raw text or a mapping."""

    def _write(
        content: str | dict[str, str] = DEFAULT_REF,
        directory: Path | None = None,
        name: str = "styles-reference.txt",
        encoding: str = "utf-8",
    ) -> Path:
        directory = directory or tmp_path
        directory.mkdir(parents=True, exist_ok=True)
        text = ref_text(content) if isinstance(content, dict) else content
        path = directory / name
        path.write_text(text, encoding=encoding)
        return path

    return _write


@pytest.fixture
def make_odt(tmp_path, write_ref) -> Callable[..., Path]:
    """Build a small ODT (and, by default, a styles-reference next to it)."""

    def _make(
        body: Iterable[str],
        name: str = "Test_Luke-Q1-L01.odt",
        directory: Path | None = None,
        auto_styles: Iterable[str] = (),
        ref: str | dict[str, str] | None = DEFAULT_REF,
    ) -> Path:
        directory = directory or tmp_path / "book"
        path = build_odt(directory / name, body, auto_styles)
        if ref is not None and not (directory / "styles-reference.txt").exists():
            write_ref(ref, directory=directory)
        return path

    return _make


# Body content for a small synthetic book.
TOC_BODY = [
    p("Title", "Table of contents"),
    p("Text_20_body", "Lesson 1 summary."),
]
L01_BODY = [
    p("Title", "Lesson one title"),
    p("Heading_20_1", "First section", tag="h"),
    p("Text_20_body", f"{span('T1', '1')} First verse. {span('T1', '2')} Second {span('T2', 'bold')} verse."),
    p("Quotations", f"{span('T1', '3')} A quote."),
]
L02_BODY = [
    p("Title", "Lesson two title"),
    p("Heading_20_2", "Subsection", tag="h"),
    p("Text_20_body", "Plain paragraph with no break space."),
]


@pytest.fixture
def make_book(tmp_path, make_odt) -> Callable[..., Path]:
    """Lay out a synthetic book folder: TOC + L01 + L02 + styles-reference."""

    def _make(
        name: str = "Test_Luke-Q1",
        toc: bool = True,
        chapters: dict[str, list[str]] | None = None,
        ref: str | dict[str, str] = DEFAULT_REF,
    ) -> Path:
        book_dir = tmp_path / name
        if chapters is None:
            chapters = {"L01": L01_BODY, "L02": L02_BODY}
        if toc:
            make_odt(TOC_BODY, name=f"{name}-TOC.odt", directory=book_dir, ref=ref)
        for suffix, body in chapters.items():
            make_odt(body, name=f"{name}-{suffix}.odt", directory=book_dir, ref=ref)
        return book_dir

    return _make


@pytest.fixture
def real_book(tmp_path) -> Path:
    """Copy of the committed real-data lessons into a writable folder."""
    src = REAL_DIR / REAL_BOOK_NAME
    if not src.is_dir() or not any(src.glob("*.odt")):
        pytest.skip(f"No real-data fixtures in {src}")
    dest = tmp_path / REAL_BOOK_NAME
    shutil.copytree(src, dest)
    return dest

