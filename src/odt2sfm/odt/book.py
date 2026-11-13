import logging
import re
from pathlib import Path

from odt2sfm.base import (
    get_timestamp,
    verify_paragraph_count,
    verify_sfm_markers,
)
from odt2sfm.odt.chapter import OdtChapter

log = logging.getLogger(__name__)


class OdtBook:
    """The full content of all of "Lessons from Luke" lessons, which is a
    sequence of ODT files in a single parent folder."""

    RE_BOOK_ID = re.compile(r"(?<=[0-9])[A-Z]{3}")

    def __init__(self, dir: Path, lang: str | None = None, filename: str | None = None, normalization_mode=None):
        self.dir_path = dir
        log.info(f"Book folder path: {self.dir_path}")
        self._language = lang
        self.filename = filename
        self.normalization_mode = normalization_mode

    def __str__(self):
        return self.name

    @property
    def book_id(self) -> str | None:
        if self.filename is None:
            return None
        r = self.RE_BOOK_ID.search(self.filename)
        if r is None:
            raise ValueError("SFM filename must be of this form: ##AAA*.SFM")
        log.debug(f"{r=}")
        return r[0]

    @property
    def language(self) -> str:
        if self._language is None:
            self._language = ""
        return self._language

    @language.setter
    def language(self, value):
        self._language = str(value)

    @property
    def chapters(self) -> dict:
        log.debug(f'Getting chapters for "{self.name}"')
        chapters = {}
        chapter_files = sorted(
            [f for f in self.dir_path.iterdir() if f.suffix == ".odt"]
        )
        for lf in chapter_files:
            chapter = OdtChapter(lf)
            chapters[chapter.number] = chapter
        return chapters

    @property
    def name(self) -> str:
        return self.dir_path.name

    @staticmethod
    def timestamp():
        return get_timestamp()

    def to_sfm(self, chapters="all") -> str:
        if self.normalization_mode is None:
            raise ValueError("Character normalization mode not specified.")
        log.info(f'Generating SFM output for book "{self.name}"')
        # Initialize data.
        out_text = []
        # Add "book" info.
        # r = self.RE_BOOK_ID.search(self.filename)
        # log.debug(f"{r=}")
        # book_id = r[0]

        out_text.append(f'\\id {self.book_id} "{self.name}", Sango [sag] translation')
        out_text.append(
            f'\\rem Initial import to SFM by nate_marti@sil.org using Python module "odt2sfm" (https://github.com/sil-car/lfl-odt2sfm) on {self.timestamp()}'
        )
        out_text.append("\\usfm 3.0")

        # Add lines from given chapter numbers.
        if chapters == "all":
            chs = self.chapters.copy()
        else:
            ch_nums = chapters.split(",")
            ch_nums = [int(n) for n in ch_nums]
            chs = {i: self.chapters.get(i) for i in ch_nums}

        # Handle TOC chapter.
        toc = chs.pop(0)
        if toc:
            out_text.extend(toc.to_sfm(self.normalization_mode).splitlines())
        # Handle remaining chapters.
        for chapter in chs.values():
            if chapter is None:
                raise TypeError("Chapter not found.")
            out_text.extend(chapter.to_sfm(self.normalization_mode).splitlines())

        log.debug(f"Writing out {len(out_text)} lines of SFM text data.")
        sfm_text_data = "\n".join(out_text)
        # Add final newline.
        if sfm_text_data[-1] != "\n":
            sfm_text_data += "\n"
        return sfm_text_data

    def update_text(self, sfm_book, new_dest_path):
        if self.normalization_mode is None:
            raise TypeError("Character normalization mode not specified.")

        for sfm_chapter in sfm_book.chapters:
            log.debug(f"Evaluating SFM chapter: {sfm_chapter.number}")
            odt_chapter = self.chapters.get(sfm_chapter.number)
            if odt_chapter is None:
                raise TypeError(f'Chapter number "{sfm_chapter.number}" not found in ODT book.')
            # Compare paragraph counts in original data and updated data.
            verify_paragraph_count(sfm_chapter, odt_chapter)
            # Ensure that SFM marker is correct for ODT paragraph (or span) style.
            verify_sfm_markers(sfm_chapter, odt_chapter)
            # Ensure updated ODT folder exists.
            new_dest_path.mkdir(exist_ok=True)
            # Make copy of original ODT into updated folder.
            odt_new_file = new_dest_path / odt_chapter.file_path.name

            log.debug("Comparing with destination chapter.")
            odt_chapter.update_text(sfm_chapter, self.normalization_mode)
            # for i, odt_p in enumerate(odt_chapter.paragraphs):
            #     log.debug(f"Checking paragraph: {odt_p.intro}")
            #     odt_p.update_text(sfm_chapter.paragraphs[i], self.normalization_mode)
            odt_chapter.save(odt_new_file)
            print(f'Saved to: "{odt_new_file}"')
