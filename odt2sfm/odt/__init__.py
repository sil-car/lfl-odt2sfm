import logging
import re
from pathlib import Path

from odfdo import Document

from ..base import get_timestamp
from ..sfm.elements import SfmParagraph
from .base import get_node_doc_style, node_has_paragraph_descendent_with_text
from .elements import OdtParagraph


class OdtChapter:
    """One "lesson" ODT file in "Lessons from Luke", which corresponds to a
    "chapter" in Paratext."""

    RE_2_DIGITS = re.compile(r"(?<=L)[0-9]{2}")
    RE_PIC = re.compile(r"\(Pictures/[0-9A-F]+\.[a-zA-Z1-9]{2,}\)")

    def __init__(self, file_path=None):
        if file_path is None:
            raise ValueError("No file path was given for this lesson.")
        else:
            self.file_path = Path(file_path)
        if not self.file_path.is_file():
            raise ValueError(f"File does not exist: {self.file_path}")

        self._all_paragraphs = None
        self._odt = None
        self._paragraphs = None
        self._styles_reference_file = None
        self._sfm_ref = None
        self._styles = None

    @property
    def all_paragraphs(self):
        """Return all elements from ODT file defined as either a header or a
        paragraph. Note: Some definied paragraphs have no text, some have no
        defined style, and some are not intended to be user-editable."""

        if self._all_paragraphs is None:
            # NOTE: self.odt.body.headers and .paragraphs exist, but they will not
            # return those elements in the correct, indexable order.
            self._all_paragraphs = [
                p for p in self._get_elements_by_nstypes(self.odt, ("h", "p"))
            ]
        return self._all_paragraphs

    @property
    def all_spans(self):
        return self.odt.body.spans

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

        if self._paragraphs is None:
            paragraphs = []
            for node in self.all_paragraphs:
                node_all_text = node.text_recursive
                node_name = f"{node.tag}:{node.style}"
                node_desc = f"{node_name}={node_all_text[:30]}..."
                if len(node_all_text) == 0:
                    logging.info(f"Skipping non-text node: {node_desc}")
                    continue
                # Ignore nodes with attachment-only "text".
                if self.RE_PIC.sub("", node_all_text) == "":
                    logging.info(
                        f"Skipping node w/ no valid children: {node_name}/{node.children}={node_all_text[:30]}"
                    )
                    continue
                if get_node_doc_style(node, self.odt) not in self.styles:
                    logging.info(f"Skipping node w/ ignored style: {node_desc}")
                    continue
                # Ignore nodes that have no text of their own and have at least
                # one paragraph with text among their descendants.
                if (
                    not node.text
                    and not node.tail
                    and node_has_paragraph_descendent_with_text(node)
                ):
                    logging.info(
                        f"Skipping node whose text comes from a descendent paragraph: {node_name}/{node.children}={node_all_text[:30]}"
                    )
                    continue

                paragraphs.append(OdtParagraph(node, chapter=self))
            self._paragraphs = paragraphs
        return self._paragraphs

    @property
    def sfm_ref(self):
        if not self._sfm_ref:
            self._sfm_ref = dict()
            for line in self.styles_reference_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("#"):  # skip commented lines
                    continue
                elif line == "":  # skip blank lines
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
            dir_path = self.file_path.parent
            paths = (
                # ODT file's parent folder for file with same stem.
                dir_path / f"{self.file_path.stem}.{filename}",
                # ODT file's parent folder for general file.
                dir_path / filename,
                # ODT file's parent's parent folder.
                dir_path.parent / filename,
            )
            for ref_file in paths:
                if ref_file.is_file():
                    self._styles_reference_file = ref_file
                    break
            if not self._styles_reference_file:
                raise ValueError("No valid styles-reference.txt found.")
            logging.debug(f"Using styles reference file: {self._styles_reference_file}")
        return self._styles_reference_file

    @property
    def styles(self):
        """Return list of valid styles for translatable paragraphs and spans."""

        if self._styles is None:
            styles = dict()
            nodes = [n for n in self.all_paragraphs]
            nodes.extend([n for n in self.all_spans])
            for node in nodes:
                # Ignore items with no style info.
                if node.style is None:
                    continue
                # Ignore items with no text.
                if len(node.text_recursive) == 0:
                    continue
                # Get node's Document style (many nodes have a Content style
                # defined instead.)
                style = get_node_doc_style(node, self.odt)
                if style in self.sfm_ref.keys():
                    styles[style] = self.sfm_ref.get(style)
            self._styles = styles
        return self._styles

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
            # if "Limo" in paragraph.text_recursive:
            #     logging.debug(f"{paragraph.text_recursive[:30]=}")
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

    def to_sfm(self):
        # Initialize data.
        out_text = list()
        # Add lines from ODT document.
        for paragraph in self.paragraphs:
            # logging.debug(f"{paragraph.text_recursive[:30]=}")
            # Ignore paragraphs with no style info.
            if paragraph.style is None:
                continue
            # Ignore paragraphs with no text.
            if len(paragraph.text_recursive) == 0:
                continue

            sfm_paragraph = SfmParagraph(paragraph.to_sfm())

            sfm_marker_plain = self.RE_LETTER_BEFORE_DIGITS.sub(
                "", sfm_paragraph.marker
            )
            logging.debug(f"{sfm_marker_plain=}")
            if sfm_marker_plain in self.INTRO_MARKERS:
                # Get trailing digits.
                sfm_digits = sfm_paragraph.marker.split(sfm_marker_plain)[1]
                # Add intro "i" in front of marker.
                updated_marker = f"\\i{sfm_marker_plain[1:]}{sfm_digits}"
                logging.debug(f"{updated_marker=}")
                sfm_paragraph.marker = updated_marker

            out_text.extend(sfm_paragraph.sfm_raw.splitlines())

        return "\n".join(out_text)


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
            # if chapter.number == 0:
            #     chapter = OdtToc(lf)
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
            chs = self.chapters.copy()
        else:
            ch_nums = chapters.split(",")
            ch_nums = [int(n) for n in ch_nums]
            # chs = [self.chapters.get(i) for i in ch_nums]
            chs = {i: self.chapters.get(i) for i in ch_nums}

        # Handle TOC chapter.
        toc = chs.pop(0)
        if toc:
            out_text.extend(toc.to_sfm().splitlines())
        # Handle remaining chapters.
        for n, chapter in chs.items():
            logging.debug(f"{len(self.chapters)=}")
            # logging.debug(f"{self.chapters=}")
            logging.debug(f"{chapter=}")
            out_text.extend(chapter.to_sfm().splitlines())
        # Add final newline.
        out_text.append("")
        return "\n".join(out_text)
