import logging
import re
import unicodedata

from odfdo import Element

from odt2sfm.base import (
    SFM_TEXT_SEP,
    do_paratext_replacements,
    normalize_text,
    verify_paragraph_children_count,
)
from odt2sfm.odt.base import get_node_doc_style

log = logging.getLogger(__name__)

RE_NEWLINES = re.compile(r"\n+")


def strip_newlines(text: str) -> str:
    """Remove literal newlines from ODT character data.

    In ODF, a newline in text content is white space, displayed as a space.
    Drop it when it is next to other white space or at either end of the
    text (where SFM_TEXT_SEP or a marker follows); otherwise replace it with
    a space so that the words on either side are not joined.
    e.g.:
    - Q1_TOC table, row 1, last column, 1st P: "1:5-25\t\n"
    - Q1_L01 verses at top: "Luc 1:5–25\t\n Luc  1:57–64"
    """

    def repl(m: re.Match) -> str:
        before = text[m.start() - 1] if m.start() > 0 else ""
        after = text[m.end()] if m.end() < len(text) else ""
        if not before or not after or before.isspace() or after.isspace():
            return ""
        return " "

    return RE_NEWLINES.sub(repl, text)


def _is_verse_span(element) -> bool:
    if not isinstance(element, OdtSpan):
        return False
    # Use lazy import to avoid circular imports.
    from odt2sfm.sfm.base import get_sfm_type

    marker = element.sfm_marker
    return marker is not None and get_sfm_type(marker) == "v"


class OdtElement:
    def __init__(self, node, chapter=None):
        self.node = node
        self.chapter = None
        if chapter:
            self.chapter = chapter
        self._path = None

    @property
    def intro(self):
        """Returns initial characters of text element. Mostly used for logging."""
        if len(self.text_recursive) > 23:
            s = f"{self.text_recursive[:20]}..."
        else:
            s = self.text_recursive
        return s

    @property
    def parent(self):
        return self.node.parent

    @property
    def path(self):
        if self._path is None:
            node = self.node
            path = [node.tag if isinstance(node, Element) else str(node)]
            while node.parent is not None:
                path.insert(0, node.parent.tag)
                node = node.parent
            self._path = "/".join(path)
        return self._path

    @property
    def tail(self):
        return self.node.tail

    @tail.setter
    def tail(self, value: str):
        self.node.tail = value

    @property
    def text(self):
        return self.node.text

    @text.setter
    def text(self, value):
        self.node.text = value

    @property
    def text_recursive(self):
        return self.node.text_recursive

    def _normalize(self, text, mode):
        """Normalize foreign text according to current document preferences."""
        return unicodedata.normalize(mode, text)

    def sfm_text(self, normalization_mode):
        """Return the element's text as it is written to SFM, but without
        markers or Paratext placeholder replacements. Used both for export
        and for detecting whether imported SFM text differs from the ODT."""
        return normalize_text(normalization_mode, strip_newlines(self.text))

    def to_sfm(self, normalization_mode):
        raise NotImplementedError

    def __str__(self):
        return self.intro


class OdtText(OdtElement):
    """A text-carrying object. Can be node's `text` or `tail` attribute."""

    def __init__(self, text, parent, tail=False, **kwargs):
        # Pass parent as node to OdtElement.
        super().__init__(parent, **kwargs)
        self.is_tail = tail

    @property
    def text(self):
        if self.is_tail:
            return self.node.tail
        else:
            return self.node.text

    @text.setter
    def text(self, value):
        if self.is_tail:
            self.node.tail = value
        else:
            self.node.text = value

    def to_sfm(self, normalization_mode):
        return do_paratext_replacements(self.sfm_text(normalization_mode))


class OdtStyledElement(OdtElement):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sfm_marker = None
        self._style = None

    @property
    def style(self):
        if self._style is None:
            self._style = self.node.style
        return self._style

    @property
    def sfm_marker(self):
        if self.chapter:
            return self.chapter.sfm_ref.get(self.style)


class OdtSpan(OdtStyledElement):
    """A "span" corresponds to the SFM designation of character-level markers;
    e.g. verses, bold, table columns, etc."""

    @property
    def sfm_marker(self):  # re-definition needed so that setter can be defined
        return super().sfm_marker

    @sfm_marker.setter
    def sfm_marker(self, value):
        if not value.startswith("\\"):
            raise ValueError(f"Invalid SFM marker: {value}")
        self._sfm_marker = value

    @property
    def text(self):
        # .inner_text includes child nodes, such as tabs and spacers.
        # FIXME: This seems a bit hacky, but it works well enough for now.
        for tag in ("text:s", "text:span", "text:tab"):
            if tag in [c.tag for c in self.node.children]:
                return self.node.inner_text
        return self.node.text

    @text.setter
    def text(self, value):
        self.node.text = value

    def to_sfm(self, normalization_mode):
        # Use lazy import to avoid circular imports.
        from odt2sfm.sfm.base import SFM_SPAN_TYPES_NO_END_MARKER, get_sfm_type
        # Use span style to get SFM marker.
        sfm_data = ""
        sfm = self.sfm_marker
        if sfm is None:
            raise ValueError(
                f'No SFM span style defined for "{self.style}".'
            )
        if sfm.endswith("v"):
            # Add newline before verse marker.
            sfm_data += "\n"
        text = do_paratext_replacements(self.sfm_text(normalization_mode))
        sfm_data += f"{sfm} {text}"
        sfm_type = get_sfm_type(sfm)
        if sfm_type not in SFM_SPAN_TYPES_NO_END_MARKER:
            # Add ending marker.
            sfm_data += f"{sfm}*"
        return sfm_data


class OdtParagraph(OdtStyledElement):
    """A "paragraph" according to the SFM designation, where all markers are
    either paragraph markers or character markers. This can be a paragraph, a
    heading, a table row, etc."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._children = None
        self._style = None

    @property
    def children(self):
        if self._children is None:
            log.debug(f'Getting children for paragraph "{self}"')
            log.debug(f"{self.node.children=}")
            return self._get_children_from_node(self.node)
        return self._children

    @property
    def spans(self):
        spans = []
        for child in self.children:
            if isinstance(child, OdtSpan):
                spans.append(child)
        return spans

    @property
    def style(self):
        if self._style is None and self.chapter:
            self._style = get_node_doc_style(self.node, self.chapter.odt)
        return self._style

    def _get_children_from_node(self, node, accumulator: list | None = None, depth=0) -> list:
        """Recurively check the node and its child nodes for those that have
        updatable content."""

        if accumulator is None:
            accumulator = []

        # Only allow recursing one level deeper than original paragraph. This
        # avoids "collecting" text from nested paragraphs.
        if depth > 1:
            return accumulator
        depth += 1

        # We re-interpret text as a "child" for easier looping.
        if node.tag in ("text:a", "text:span"):
            # "Flatten" a("address")/span by using "inner_text" to eliminate nested spans.
            if node.inner_text:
                # Skip space-only nodes.
                if node.inner_text.replace(" ", "").replace("\t", "") != "":
                    child = OdtSpan(node, chapter=self.chapter)
                    accumulator.append(child)
                else:
                    log.info(f"Excluding node w/ only space from: {node.tag}")
        else:
            if node.text:
                # Skip space-only nodes.
                if node.text.replace(" ", "").replace("\t", "") != "":
                    child = OdtText(node.text, node, chapter=self.chapter)
                    accumulator.append(child)
                else:
                    log.info(f"Excluding node w/ only space from: {node.tag}")

        # Evaluate node children if not a Span node, b/c "inner_text" is taken
        # from Span node, so child nodes texts' are already incorporated.
        if node.tag != "text:span":
            for child_node in node.children:
                accumulator = self._get_children_from_node(
                    child_node, accumulator, depth=depth
                )

        # As with text, we re-interpret any "tail" as a final child node.
        if node.tail:
            if node.tail.replace(" ", "").replace("\t", "") != "":
                accumulator.append(
                    OdtText(node.tail, node, tail=True, chapter=self.chapter)
                )
            else:
                log.info(f"Excluding tail w/ only space from: {node.tag}")

        return accumulator

    def to_sfm(self, normalization_mode):
        log.debug(f'Generating SFM output for "{self}"')
        out_text = []
        sfm = self.sfm_marker
        line = f"{sfm} "
        prev_child = None
        for child in self.children:
            # log.debug(f"{line=}")
            if isinstance(child, OdtText) and isinstance(prev_child, OdtText):
                # Add space-underscore when following another Text.
                log.debug(
                    f"OdtText following other OdtText: {prev_child.text=}; {child.text=}"
                )
                line += SFM_TEXT_SEP
            line += child.to_sfm(normalization_mode)
            prev_child = child

        # Add SFM line.
        if len(line) > 0:
            # Do Paratext replacements.
            line = do_paratext_replacements(line)
            # Normalize characters.
            line = normalize_text(normalization_mode, line)
            lines = line.split("\n")
            # log.debug(f"{lines=}")
            out_text.extend(lines)

        return "\n".join(out_text)

    def update_text(self, sfm_paragraph, normalization_mode):
        """Starting with the paragraph node, recursively check for Text nodes
        and update their data if needed.

        Text is compared in its exported form (see OdtElement.sfm_text), so
        that details lost in export (literal newlines, the original Unicode
        normalization, the space after a verse number) are only overwritten
        when the SFM text was actually edited. Unedited text is left
        untouched, even if its normalization differs from normalization_mode.
        """
        # Parts are paired by position; if the counts differ, text would be
        # lost (fewer SFM parts) or silently dropped (more SFM parts).
        if verify_paragraph_children_count(sfm_paragraph, self) != 0:
            raise ValueError(
                f"Can't update paragraph: SFM has {len(sfm_paragraph.children)} parts, "
                f'ODT has {len(self.children)}: "{sfm_paragraph.intro}"'
            )

        log.debug(
            f"P children: {[f'{c.__class__.__name__}:{c.text}' for c in self.children]}"
        )
        log.debug(
            f"XML children: {[f'{c.text=}; {c.tail=}' for c in self.node.children]}"
        )
        sfm_children = [c for c in sfm_paragraph.children]
        prev_item = None
        for i, odt_item in enumerate(self.children):
            sfm_item = sfm_children[i]
            new_text = normalize_text(normalization_mode, sfm_item.text)
            current_text = odt_item.sfm_text(normalization_mode)
            # On export, the text after a verse number supplies the space that
            # separates it from the number ("\v 1" + " Text"), and SFM parsing
            # consumes that space, so account for it in both directions.
            prefix = ""
            if _is_verse_span(prev_item) and current_text.startswith(" "):
                current_text = current_text[1:]
                prefix = " "
            prev_item = odt_item
            if current_text == new_text:
                log.debug(f"Skipping unchanged paragraph child: {odt_item.intro}")
                continue
            sfm_item_normalized_text = prefix + new_text
            item = "Unknown"
            tail = ""
            if isinstance(odt_item, OdtText):
                item = "OdtText"
                if odt_item.is_tail:
                    tail = " tail"
            elif isinstance(odt_item, OdtSpan):
                item = "OdtSpan"
            log.info(
                f'Updating {item}{tail} "{odt_item.text}" to "{sfm_item_normalized_text}"'
            )
            odt_item.text = sfm_item_normalized_text


class OdtTableRow(OdtParagraph):
    """A TableRow is special paragraph whose children are set manually rather
    than deduced from the node data. All text and styles are found within the
    children elements."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._children = []
        self._parent_table = None

    # TODO: Set correct SFM marker for paragraph.
    @property
    def children(self):
        return self._children

    @property
    def parent_table(self):
        if self._parent_table is None:
            # Parent of table-row node is table node.
            self._parent_table = self.node.parent._xml_element
        return self._parent_table

    @property
    def sfm_marker(self):
        return "\\tr"

    def add_cell(self, node, column_idx):
        """Add the "paragraph" node's data to the table row. This can include
        plain text and span data."""
        # Hijack OdtParagraph to generate child elements.
        p = OdtParagraph(node, chapter=self.chapter)
        # Create/update column-initial element.
        e = OdtSpan(node, chapter=self.chapter)
        e.sfm_marker = f"\\tc{column_idx}"
        children = p.children
        if len(children) == 0:
            children.append(e)
        elif isinstance(children[0], OdtText):
            e.text = children[0].text
            children[0] = e
        else:
            e.text = ""
            children.insert(0, e)
        self.children.extend(children)
        log.debug(f"{self.children=}")
