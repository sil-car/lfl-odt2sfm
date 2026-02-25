import logging
import unicodedata

from odfdo import Element, Span


class OdtElement:
    def __init__(self, node, chapter=None):
        self.node = node
        self.chapter = None
        # FIXME: Normalization form should come from ODT file somehow.
        self.normalization_form = "NFC"
        if chapter:
            self.chapter = chapter

    @property
    def all_children(self):
        return self.node.children

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
        node = self.node
        path = [node.tag if isinstance(node, Element) else str(node)]
        while node.parent is not None:
            path.insert(0, node.parent.tag)
            node = node.parent
        return "/".join(path)

    @property
    def tail(self):
        return self.node.tail

    @tail.setter
    def tail(self, value):
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

    def _normalize(self, text):
        """Normalize foreign text according to current document preferences."""
        return unicodedata.normalize(self.normalization_form, text)

    def to_sfm(self):
        pass

    def __str__(self):
        return self.text_recursive


class OdtText(OdtElement):
    """A text-carrying object. Can be node's `text` or `tail` attribute."""

    def __init__(self, text, parent, tail=False, **kwargs):
        # Pass parent as node to OdtElement.
        super().__init__(parent, **kwargs)
        self.is_tail = tail

    @property
    def tail(self):
        if self.is_tail:
            return self.text

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


class OdtSpan(OdtElement):
    @property
    def style(self):
        return self.node.style

    @property
    def text(self):
        # .inner_text includes child nodes, such as tabs and spacers.
        # FIXME: This seems a bit hacky, but it works well enough for now.
        if "text:s" or "text:tab" in [c.tag for c in self.node.children]:
            return self.node.inner_text
        else:
            return self.node.text

    @text.setter
    def text(self, value):
        self.node.text = value


class OdtParagraph(OdtElement):
    @property
    def children(self):
        return self._get_children_from_node(self.node)

    @property
    def spans(self):
        spans = []
        for child in self.children:
            if isinstance(child, OdtSpan):
                spans.append(child)
        return spans

    @property
    def style(self):
        return self.node.style

    def _get_children_from_node(self, node, accumulator=None):
        """Recurively check the node and its child nodes for those that have
        updatable content."""

        if accumulator is None:
            accumulator = list()

        # We re-interpret text as a "child" for easier looping.
        if node.text:
            # logging.debug(f"children: {node.__class__.__name__}|{node.text}|")
            if node.text.replace(" ", "").replace("\t", "") != "":
                if isinstance(node, Span):
                    if "Quel" in node.text:
                        logging.debug(
                            f"quel: {node.tag}|{node.text}|{node.text_recursive}|"
                        )
                    child = OdtSpan(node, chapter=self.chapter)
                else:
                    child = OdtText(node.text, node, chapter=self.chapter)
                accumulator.append(child)
            else:
                # logging.debug(f"{node.__dir__()}")
                logging.debug(f"Excluding node w/ only space from: {node.tag}")

        # Evaluate node children.
        for child_node in node.children:
            accumulator = self._get_children_from_node(child_node, accumulator)

        # As with text, we re-interpret any "tail" as a final child node.
        if node.tail:
            if node.tail.replace(" ", "").replace("\t", "") != "":
                accumulator.append(
                    OdtText(node.tail, node, tail=True, chapter=self.chapter)
                )
            else:
                logging.debug(f"Excluding tail w/ only space from: {node.tag}")

        return accumulator

    def to_sfm(self):
        out_text = list()
        sfm = self.chapter.sfm_ref.get(self.style)
        line = f"{sfm} "
        logging.debug(f"{[f'{c.__class__.__name__}|{c.text}|' for c in self.children]}")
        prev_child = None
        for child in self.children:
            logging.debug(f"{line=}")
            if isinstance(child, OdtText):
                # Add double-space when following another Text.
                if isinstance(prev_child, OdtText):
                    line += "  "
                line += child.text
            elif isinstance(child, OdtSpan):
                # Use span style
                sfm = self.chapter.sfm_ref.get(child.style)
                if sfm is None:
                    raise ValueError(f'No SFM span style defined for "{child.style}"')
                if sfm.endswith("v"):
                    # Add newline before verse marker.
                    line += "\n"
                logging.debug(f"|{child.text=}|{child.text_recursive=}|")
                line += f"{sfm} {child.text}"
                if not sfm.endswith("v"):
                    # Add ending marker.
                    line += f"{sfm}*"
            prev_child = child

        # Add SFM line.
        if len(line) > 0:
            lines = line.split("\n")
            # logging.debug(f"{lines=}")
            out_text.extend(lines)

        return "\n".join(out_text)

    def update_text(self, sfm_paragraph):
        """Starting with the paragraph node, recursively check for Text nodes
        and update their data if needed."""
        # Only proceed if overall paragraph text is different.
        if self.text == self._normalize(sfm_paragraph.text):
            logging.debug(f"Skipping unchanged paragraph: {sfm_paragraph.intro}")
            return

        odt_ct = len(self.children)
        sfm_ct = len(sfm_paragraph.children)
        if odt_ct != sfm_ct:
            logging.warning(
                f"Warning: Unmatched children for ODT ({odt_ct}) & SFM ({sfm_ct}): {self.intro}|{sfm_paragraph.intro}"
            )
            logging.debug(
                [f'{c.__class__.__name__}:"{c.text}":"{c.tail}"' for c in self.children]
            )
            logging.debug(
                [f'{c.__class__.__name__}:"{c.text}"' for c in sfm_paragraph.children]
            )
            logging.debug(f"{self.all_children=}")
            return

        logging.debug(
            f"P children: {[f'{c.__class__.__name__}:{c.text}' for c in self.children]}"
        )
        logging.debug(
            f"XML children: {[f'{c.text=}; {c.tail=}' for c in self.node.children]}"
        )
        for i, odt_item in enumerate(self.children):
            sfm_item = sfm_paragraph.children[i]
            if isinstance(odt_item, OdtText):
                # Set odt_paragraph.text or odt_text.tail value.
                if not odt_item.is_tail:
                    logging.info(
                        f'Updating OdtText "{odt_item.intro}" to "{sfm_item.intro}"'
                    )
                else:
                    logging.info(
                        f'Updating OdtText tail "{odt_item.tail}" to "{sfm_item.intro}"'
                    )
                odt_item.text = sfm_item.text
            elif isinstance(odt_item, OdtSpan):
                logging.info(
                    f'Updating OdtSpan "{odt_item.intro}" to "{sfm_item.intro}"'
                )
                odt_item.text = sfm_item.text
