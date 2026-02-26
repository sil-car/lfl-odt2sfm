import logging
from pathlib import Path

from .base import get_timestamp
from .odt import OdtBook, OdtChapter
from .sfm import SfmBook, SfmChapter


class Conversion:
    """Base class for ODT-to-SFM or SFM-to-ODT conversions."""

    def __init__(self, source=None, destination=None):
        self._destination_path = None
        self.destination_format = None
        self._source_path = None
        self.source_format = None
        if destination is not None:
            self.destination_path = destination
        if source is not None:
            self.source_path = source

    @property
    def destination_path(self):
        return self._destination_path

    @destination_path.setter
    def destination_path(self, value):
        destination = Path(value)
        self._validate_path(destination)
        self.destination_format = destination.suffix
        self._destination_path = destination

    @property
    def source_path(self):
        return self._source_path

    @source_path.setter
    def source_path(self, value):
        source = Path(value)
        self._validate_path(source)
        self.source_format = source.suffix
        self._source_path = source

    def run(self):
        raise NotImplementedError

    @staticmethod
    def _validate_path(path):
        if path.suffix == ".odt" and not path.is_dir():
            raise ValueError("ODT book must be defined as its root folder.")
        elif path.suffix == ".sfm" and not path.is_file():
            raise ValueError("SFM book must be a readable file.")


class OdtToSfm(Conversion):
    """Get formatted text from the files in the source dir and generate the destination SFM file."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logging.info(f"Evaluating source path: {self.source_path}")
        self.odt_book = OdtBook(self.source_path)
        if self.destination_path is not None:
            logging.info(f"Evaluating destination path: {self.destination_path}")
            self.sfm_book = SfmBook(self.destination_path)

    def run(self):
        # FIXME: Add any book details here.
        chapters = "all"
        if self.destination_path:
            # FIXME: For testing, skip all chapters but Chapter 1.
            self.destination_path.write_text(self.odt_book.to_sfm(chapters=chapters))
            print(f"SFM data written to {self._destination_path}")
        else:
            print(self.odt_book.to_sfm(chapters=chapters))


class SfmToOdt(Conversion):
    """Get formatted text from SFM file and create updated ODT files next to the destination dir."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logging.info(f"Evaluating source path: {self.source_path}")
        self.sfm_book = SfmBook(self.source_path)
        logging.info(f"Evaluating destination path: {self.destination_path}")
        self.odt_book = OdtBook(self.destination_path)

    @staticmethod
    def compare_paragraphs(chapters):
        odt_chapter = None
        sfm_chapter = None
        for chapter in chapters:
            if isinstance(chapter, SfmChapter):
                sfm_chapter = chapter
            elif isinstance(chapter, OdtChapter):
                odt_chapter = chapter
        for c in (odt_chapter, sfm_chapter):
            if c is None:
                raise ValueError(f"Invalid chapter type: {type(c)}")

        for i, odt_p in enumerate(odt_chapter.paragraphs):
            print(f'[{odt_p.style}] "{odt_p.text_recursive}"')
            try:
                sfm_p = sfm_chapter.paragraphs[i]
            except IndexError:
                sfm_p = None
            if sfm_p:
                style = sfm_p.marker
                text = sfm_p.text
            else:
                style = text = None
            print(f'[{style}] "{text}"\n')

    def run(self):
        """Create updated ODT file(s) based on the data found in the given SFM file."""

        new_dest_path = self.destination_path.with_name(
            f"{self.destination_path.name}_updated_{get_timestamp()}"
        )
        for sfm_chapter in self.sfm_book.chapters:
            logging.info(f"Evaluating SFM chapter: {sfm_chapter.number}")
            # FIXME: For testing, skip all chapters but Chapter 1.
            if sfm_chapter.number != 1:
                continue
            odt_chapter = self.odt_book.chapters.get(sfm_chapter.number)
            # Compare paragraph counts in original data and updated data.
            self._verify_paragraph_count(sfm_chapter, odt_chapter)
            # Ensure that SFM marker is correct for ODT paragraph (or span) style.
            self._verify_sfm_markers(sfm_chapter, odt_chapter)
            # Ensure updated ODT folder exists.
            new_dest_path.mkdir(exist_ok=True)
            # Make copy of original ODT into updated folder.
            odt_new_file = new_dest_path / odt_chapter.file_path.name

            logging.info("Comparing with destination chapter.")
            for i, odt_p in enumerate(odt_chapter.paragraphs):
                logging.debug(f"Checking paragraph: {odt_p.intro}")
                odt_p.update_text(sfm_chapter.paragraphs[i])
            odt_chapter.save(odt_new_file)
            print(f'Saved to: "{odt_new_file}"')

    @staticmethod
    def _verify_paragraph_count(sfm_chapter, odt_chapter):
        # Compare paragraph counts in original data and updated data.
        len_sfm = len(sfm_chapter.paragraphs)
        len_odt = len(odt_chapter.paragraphs)
        if len_sfm != len_odt:
            raise ValueError(f"Paragraph counts differ; SFM: {len_sfm}; ODT: {len_odt}")

    @staticmethod
    def _verify_sfm_markers(sfm_chapter, odt_chapter):
        for i, p in enumerate(odt_chapter.paragraphs):
            sfm = sfm_chapter.paragraphs[i].marker
            marker = odt_chapter.styles.get(p.style)
            if marker != sfm:
                raise ValueError(
                    f'SFM marker ({sfm}) does not correspond to ODT style ({p.style}) for text "{p.text}"; expected: {marker}'
                )
