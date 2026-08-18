from pathlib import Path

from . import logger
from .base import get_timestamp
from .odt import OdtBook, OdtChapter
from .sfm import SfmBook, SfmChapter


class Conversion:
    """Base class for ODT-to-SFM or SFM-to-ODT conversions."""

    def __init__(self, source=None, destination=None, normalization_mode="NFC"):
        self._destination_path = None
        self.destination_format = None
        self.normalization_mode = normalization_mode
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
        logger.info(f"Evaluating source path: {self.source_path}")
        self.odt_book = OdtBook(
            self.source_path,
            filename=self.destination_path.stem,
            normalization_mode=self.normalization_mode,
        )
        logger.info(f"Evaluating destination path: {self.destination_path}")
        self.sfm_book = SfmBook(self.destination_path)

    def run(self):
        # FIXME: Add any book details here.
        chapters = "all"
        if self.destination_path:
            self.destination_path.write_text(self.odt_book.to_sfm(chapters=chapters))
            print(f"SFM data written to {self._destination_path}")
        else:
            print(self.odt_book.to_sfm(chapters=chapters))


class SfmToOdt(Conversion):
    """Get formatted text from SFM file and create updated ODT files next to the destination dir."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info(f"Evaluating source path: {self.source_path}")
        self.sfm_book = SfmBook(self.source_path)
        logger.info(f"Evaluating destination path: {self.destination_path}")
        self.odt_book = OdtBook(
            self.destination_path, normalization_mode=self.normalization_mode
        )

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
        self.odt_book.update_text(self.sfm_book, new_dest_path)
