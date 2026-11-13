import logging
import re
from pathlib import Path

from odfdo import Document

from odt2sfm.base import SFM_ONLY_MARKERS
from odt2sfm.odt.base import (
    get_node_doc_style,
    node_has_paragraph_descendent_with_text,
)
from odt2sfm.odt.elements import OdtParagraph

log = logging.getLogger(__name__)


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
        log.info(f"Chapter file path: {self.file_path}")

        self._all_paragraphs = None
        self._odt = None
        self._paragraphs = None
        self._styles_reference_file = None
        self._sfm_ref = None
        self._styles = None

    @property
    def all_paragraphs(self):
        """Return all elements from ODT file defined as either a header or a
        paragraph. Note: Some defined paragraphs have no text, some have no
        defined style, and some are not intended to be user-editable."""

        if self._all_paragraphs is None:
            # NOTE: self.odt.body.headers and .paragraphs exist, but they will not
            # return those elements in the correct, indexable order.
            log.debug(
                f'Getting all "paragraphs" ("text:h", "text:p") in "{self.name}".'
            )
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
    def number(self) -> int | None:
        num_match = self.RE_2_DIGITS.search(self.file_path.stem)
        if "TOC" in self.file_path.name:
            return 0
        elif num_match:
            return int(num_match[0])

    @property
    def odt(self):
        if self._odt is None:
            log.info(f"Reading file: {self.file_path}")
            self._odt = Document(self.file_path)
        return self._odt

    @property
    def paragraphs(self):
        """Return list of user-editable paragraphs."""

        if self._paragraphs is None:
            log.debug(f'Getting translatable paragraphs in "{self.name}"')
            paragraphs = []
            # active_table = None
            for node in self.all_paragraphs:
                for s in ("1:5–25", "1:57–64"):
                    if s in str(node):
                        log.debug(
                            f"FIXME: {node.text=}; {node.tail}; {node.children=}; {node.text_recursive=}"
                        )
                        for c in node.children:
                            log.debug(f"FIXME: {c.text=}; {c.tail=}; {c.children=}")
                node_all_text = node.text_recursive
                node_name = f"{node.tag}:{node.style}"
                node_desc = f"{node_name}={node_all_text[:30]}..."
                if len(node_all_text) == 0:
                    log.info(f" Skipping non-text node: {node_desc}")
                    continue
                # Ignore nodes with attachment-only "text".
                if self.RE_PIC.sub("", node_all_text) == "":
                    log.info(
                        f" Skipping node w/ no valid children: {node_name}/{node.children}={node_all_text[:30]}"
                    )
                    continue
                if get_node_doc_style(node, self.odt) not in self.styles:
                    log.info(f" Skipping node w/ ignored style: {node_desc}")
                    continue
                # Ignore nodes that have no text of their own and have at least
                # one paragraph with text among their descendants.
                if (
                    not node.text
                    and not any(c.tail for c in node.children)
                    and node_has_paragraph_descendent_with_text(node)
                ):
                    log.info(
                        f" Skipping node whose text comes from a descendent paragraph: {node_name}/{node.children}={node_all_text[:30]}"
                    )
                    continue
                """
                if node_in_table(node):
                    log.info(
                        f" Handling table node: {active_table=}/{get_node_table_pos(node)}:{node_desc}"
                    )
                    if active_table is None:
                        active_table = get_node_table(node)._xml_element
                    elif active_table is not get_node_table(node)._xml_element:
                        raise ValueError(
                            "New table found before previous table finished."
                        )
                    row, col = get_node_table_pos(node)
                    log.debug(f"cell pos: ({row}, {col})")
                    # Ensure TableRow paragraph.
                    if not isinstance(paragraphs[-1], OdtTableRow):
                        paragraphs.append(OdtTableRow(get_node_row(node), chapter=self))
                    # Update previous Table paragraph with new cell data.
                    p = paragraphs[-1]
                    log.debug(f"{type(p)}:{p.children=}; {p.text_recursive=}")
                    p.add_cell(node, col)
                    log.debug(f"{type(p)}:{p.children=}; {p.text_recursive=}")
                    continue
                else:
                    active_table = None
                """

                paragraphs.append(OdtParagraph(node, chapter=self))
            self._paragraphs = paragraphs
        return self._paragraphs

    @property
    def sfm_ref(self):
        if not self._sfm_ref:
            log.debug(
                f"Building SFM reference dict from {self.styles_reference_file}"
            )
            self._sfm_ref = {}
            text = self.styles_reference_file.read_text(encoding="utf-8-sig")  # ignore BOM
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("#"):  # skip commented lines  # noqa: SIM114
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
            raise TypeError("Must be instance of `dict`.")
        else:
            self._sfm_ref = value

    @property
    def styles_reference_file(self):
        if self._styles_reference_file is None:
            log.debug(f'Searching for styles-reference file for "{self.name}"')
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
            log.debug(
                f" Using styles reference file: {self._styles_reference_file}"
            )
        return self._styles_reference_file

    @property
    def styles(self):
        """Return list of valid styles for translatable paragraphs and spans."""

        if self._styles is None:
            log.debug(f'Getting valid styles from "{self.name}"')
            styles = {}
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
                if style in self.sfm_ref:
                    styles[style] = self.sfm_ref.get(style)
            self._styles = styles
        return self._styles

    def _get_elements_by_nstypes(self, node, nstypes, accumulator=None):
        """Return valid "header" and "paragraph" elements in document order to
        preserve indexing."""

        qnames = [f"text:{t}" for t in nstypes]
        if accumulator is None:
            accumulator = []

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
        log.info(f"Saving ODT to: {file_path}")
        self.odt.save(str(file_path))

    def to_sfm(self, normalization_mode):
        log.info(f'Generating SFM output for "{self.name}"')
        # Initialize data.
        out_text = []
        # Add "chapter" info.
        if self.number and self.number > 0:
            out_text.append(f"\\c {self.number}")
        # Add lines from ODT document.
        for paragraph in self.paragraphs:
            # Ignore paragraphs with no style info.
            if paragraph.style is None:
                continue
            # Ignore paragraphs with no text.
            if len(paragraph.text_recursive) == 0:
                continue

            out_text.extend(paragraph.to_sfm(normalization_mode).splitlines())

        return "\n".join(out_text)

    def update_text(self, sfm_chapter, normalization_mode):
        sfm_paragraphs = [
            p for p in sfm_chapter.paragraphs if p.marker not in SFM_ONLY_MARKERS
        ]
        for i, odt_p in enumerate(self.paragraphs):
            log.debug(f"Checking paragraph: {odt_p.intro}")
            odt_p.update_text(sfm_paragraphs[i], normalization_mode)

    def __str__(self):
        return self.name
