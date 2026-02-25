import logging
import re
from pathlib import Path

from odfdo import Document

from ..base import get_timestamp
from .elements import OdtParagraph


class OdtChapter:
    """One "lesson" ODT file in "Lessons from Luke", which corresponds to a
    "chapter" in Paratext."""

    RE_2_DIGITS = re.compile(r"(?<=L)[0-9]{2}")

    def __init__(self, file_path=None):
        if file_path is None:
            raise ValueError("No file path was given for this lesson.")
        else:
            self.file_path = Path(file_path)
        if not self.file_path.is_file():
            raise ValueError(f"File does not exist: {self.file_path}")

        self._odt = None
        self._styles_reference_file = None
        self._sfm_ref = None
        self._all_styles = None
        self._styles = None

    @property
    def all_paragraphs(self):
        """Return all elements from ODT file defined as either a header or a
        paragraph. Note: Some definied paragraphs have no text, some have no
        defined style, and some are not intended to be user-editable."""

        # NOTE: self.odt.body.headers and .paragraphs exist, but they will not
        # return those elements in the correct, indexable order.
        return [p for p in self._get_elements_by_nstypes(self.odt, ("h", "p"))]

    @property
    def all_spans(self):
        return self.odt.body.spans

    @property
    def all_styles(self):
        if self._all_styles is None:
            styles = []
            for p in self.paragraphs:
                if p.style not in styles:
                    styles.append(p.style)
            self._all_styles = styles
        return self._all_styles

    @property
    def name(self):
        return self.file_path.name

    @property
    def number(self):
        num_match = self.RE_2_DIGITS.search(self.file_path.stem)
        if "TOC" in self.file_path.name:
            return 0
        elif num_match:
            return int(num_match[0])

    @property
    def odt(self):
        if self._odt is None:
            self._odt = Document(self.file_path)
        return self._odt

    @property
    def paragraphs(self):
        """Return list of user-editable paragraphs."""
        paragraphs = []
        for node in self.all_paragraphs:
            if len(node.text_recursive) == 0:
                logging.debug(
                    f"Skipping non-text node: {node.tag}:{node.text_recursive}"
                )
                continue
            # Ignore nodes with attachment-only "text".
            if (
                re.sub(
                    r"\(Pictures/[0-9A-F]+\.[a-zA-Z1-9]{2,}\)",
                    "",
                    node.text_recursive,
                )
                == ""
            ):
                logging.debug(
                    f"Skipping node w/ no valid children: {node.tag}/{node.children}={node.text_recursive}"
                )
                continue
            if node.style not in self.styles:
                logging.debug(
                    f"Skipping node w/ excluded style: {node.tag}:{node.style}"
                )
                continue
            paragraphs.append(OdtParagraph(node, chapter=self))
        return paragraphs

    @property
    def sfm_ref(self):
        if not self._sfm_ref:
            self._sfm_ref = dict()
            for line in self.styles_reference_file.read_text().splitlines():
                if line.lstrip().startswith("#"):  # skip commented lines
                    continue
                try:
                    k, v = line.split("\\")
                    self._sfm_ref[k.strip()] = f"\\{v.strip()}"
                except ValueError as e:
                    raise ValueError(f"{e}: {line}")
        return self._sfm_ref

    @sfm_ref.setter
    def sfm_ref(self, value):
        if not isinstance(value, dict):
            raise ValueError("Must be instance of `dict`.")
        else:
            self._sfm_ref = value

    @property
    def styles_reference_file(self):
        if self._styles_reference_file is None:
            filename = "styles-reference.txt"
            # Check ODT file's parent folder.
            logging.debug(f"{self.file_path=}")
            dir_path = self.file_path.parent
            ref_file = dir_path / filename
            if not ref_file.is_file():
                # Check ODT file's parent's parent folder.
                ref_file = dir_path.parent / filename
                if not ref_file.is_file():
                    raise ValueError("No valid styles-reference.txt found.")
            self._styles_reference_file = ref_file
        return self._styles_reference_file

    @property
    def styles(self):
        """Return list of valid styles for translatable paragraphs and spans."""

        if self._styles is None:
            styles = dict()
            nodes = [n for n in self.all_paragraphs]
            nodes.extend([n for n in self.all_spans])
            for node in nodes:
                # Ignore spans with no style info.
                if node.style is None:
                    continue
                # Ignore spans with no text.
                if len(node.text_recursive) == 0:
                    continue
                if node.style in self.sfm_ref.keys():
                    styles[node.style] = self.sfm_ref.get(node.style)
            self._styles = styles
        return self._styles

    def all_styles_and_paragraphs(self):
        # raise NotImplementedError
        data = []
        for p_node in self.all_paragraphs:
            data.append(f'[{p_node.style}] "{p_node.text_recursive}"')
            for s in p_node.spans:
                data.append(f'> [{s.style}] "{s.inner_text}"|"{s.tail}"')
        print("\n".join(data))

    def _get_elements_by_nstypes(self, node, nstypes, accumulator=None):
        """Return valid "header" and "paragraph" elements in document order to
        preserve indexing."""
        qnames = [f"text:{t}" for t in nstypes]
        if accumulator is None:
            accumulator = list()

        # If "node" is a document, choose its top Node.
        if not hasattr(node, "tag"):
            node = node.body

        if node.tag in qnames:
            accumulator.append(node)

        for c in node.children:
            accumulator = self._get_elements_by_nstypes(c, nstypes, accumulator)

        return accumulator

    def save(self, file_path):
        lock_file = file_path.parent / f".~lock.{self.file_path.name}#"
        if lock_file.is_file():
            raise OSError(f"Can't save; file already open: {self.file_path}")
        self.odt.save(str(file_path))

    def to_sfm(self):
        # Initialize data.
        out_text = list()
        # Add "chapter" info.
        if self.number > 0:
            out_text.append(f"\\c {self.number}")
        # Add lines from ODT document.
        for paragraph in self.paragraphs:
            # logging.debug(f"{paragraph.text_recursive[:30]=}")
            # Ignore paragraphs with no style info.
            if paragraph.style is None:
                continue
            # Ignore paragraphs with no text.
            if len(paragraph.text_recursive) == 0:
                continue

            out_text.extend(paragraph.to_sfm().split("\n"))

        return "\n".join(out_text)

    def __str__(self):
        return self.name


class OdtToc(OdtChapter):
    RE_LETTER_BEFORE_DIGITS = re.compile(r"(?<=[a-z])[0-9]+")
    INTRO_MARKERS = (
        "\\mt",
        "\\s",
        "\\p",
        "\\pi",
        "\\m",
        "\\mi",
        "\\pq",
        "\\mq",
        "\\q",
        "\\b",
        "\\li",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert "normal" SFMs to Intro-specific SFMs.
        for pstyle, sfm in self.sfm_ref.items():
            sfm_intro = self.to_intro_sfm(sfm)
            self.sfm_ref[pstyle] = sfm_intro

    @classmethod
    def to_intro_sfm(cls, sfm):
        # Strip any #s from SFM tags.
        # sfm_plain = re.sub(cls.RE_LETTER_BEFORE_DIGITS, "", sfm)
        sfm_plain = cls.RE_LETTER_BEFORE_DIGITS.sub("", sfm)
        if sfm_plain in cls.INTRO_MARKERS:
            # Get trailing digits.
            sfm_digits = sfm.split(sfm_plain)[1]
            # Add intro "i" in front of marker.
            return f"\\i{sfm_plain[1:]}{sfm_digits}"
        else:
            return sfm


class OdtBook:
    """The full content of all of "Lessons from Luke" lessons, which is a
    sequence of ODT files in a single parent folder."""

    def __init__(self, dir=None, lang=None):
        self._dir_path = None
        self._language = lang
        if dir is None:
            raise ValueError("No folder was given.")
        else:
            self.dir_path = dir

    def __str__(self):
        return self.name

    @property
    def dir_path(self):
        return self._dir_path

    @dir_path.setter
    def dir_path(self, value):
        dir_path = Path(value)
        if not dir_path.is_dir():
            raise ValueError(f"Not a valid folder: {value}")
        self._dir_path = dir_path

    @property
    def language(self):
        if self._language is None:
            self._language = ""
        return self._language

    @language.setter
    def language(self, value):
        self._language = str(value)

    @property
    def chapters(self):
        chapters = dict()
        chapter_files = sorted(
            [f for f in self.dir_path.iterdir() if f.suffix == ".odt"]
        )
        for lf in chapter_files:
            chapter = OdtChapter(lf)
            if chapter.number == 0:
                chapter = OdtToc(lf)
            chapters[chapter.number] = chapter
        return chapters

    @property
    def name(self):
        return self.dir_path.name

    @staticmethod
    def timestamp():
        return get_timestamp()

    def to_sfm(self, chapters="all"):
        # Initialize data.
        out_text = list()
        # Add "book" info.
        out_text.append(
            f'\\id XXA "{self.name}"; generated by Python module "odt2sfm" on {self.timestamp()}'
        )
        out_text.append("\\usfm 3.0")

        # Add lines from given chapter numbers.
        if chapters == "all":
            chs = self.chapters
        else:
            ch_nums = chapters.split(",")
            ch_nums = [int(n) for n in ch_nums]
            chs = [self.chapters[i] for i in ch_nums]
        for chapter in chs:
            out_text.extend(chapter.to_sfm().split("\n"))
        # Add final newline.
        out_text.append("")
        return "\n".join(out_text)


def print_styles(book):
    all_styles = []
    for chapter in book.chapters:
        print(chapter.name)
        for i, style in enumerate(sorted(chapter.styles)):
            if style not in all_styles:
                all_styles.append(style)
            print(f" {i:2d}: {style}")
        print()

    print("All styles:")
    for i, style in enumerate(all_styles):
        print(f" {i:2d}: {style}")
