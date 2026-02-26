import re

from ..base import normalize_text, undo_paratext_replacements


class SfmElement:
    """Text that begins with an SFM."""

    NODE_TYPE = "element"
    RE_SFM_INIT = re.compile(r"^\\[a-z]+[0-9]*[ \n]")
    RE_SFM = re.compile(r"(\\[a-z]+[0-9]*[ *])")

    def __init__(self, raw_text, odt_style=None, parent=None):
        self._marker = None
        self._marker_separator = None
        self._odt_style = odt_style
        self.parent = parent
        self._sfm_raw = raw_text
        self._text = None
        # FIXME: Normalization from should come from Paratext project settings.
        self.normalization_form = "NFD"

    @property
    def children(self):
        """Mimic ODT doc behavior by dividing paragraph into SfmText and SfmSpan
        Elements."""
        children = []
        # Divide SFM on SFM markers.
        parts = re.split(
            self.RE_SFM,
            self.sfm_raw.removeprefix(f"{self.marker}{self._marker_separator}"),
        )
        span_marker = None
        verse_marker = None
        prev_part = None
        for part in parts:
            part = part.rstrip("\n")  # remove newlines from all splits
            child = None
            if len(part) == 0:  # ignore parts with no content
                child = None
            elif part.startswith("\\"):  # paragraph/span/chapter marker
                part = part.rstrip(" ")  # remove spaces from SFM markers
                if part == "\\v" and not verse_marker:
                    verse_marker = True
                elif not span_marker:  # capture opening span SFM marker
                    span_marker = part
                    # print(f"{span_marker=}")
                elif part == f"{span_marker}*":  # define span end
                    span_text = prev_part
                    child = SfmSpan(
                        f"{span_marker} {span_text}{span_marker}*", parent=self
                    )
                    span_marker = None
            elif verse_marker:  # handle verse number
                v_num, part = part.split(" ", maxsplit=1)
                children.append(SfmSpan(f"\\v {v_num} ", parent=self))
                child = SfmText(part, parent=self)
                verse_marker = None
            elif span_marker:
                child = None
            elif part != "":  # ignore empty part
                child = SfmText(part, parent=self)
            prev_part = part
            if child:
                children.append(child)

        ct = len(children)
        for i, child in enumerate(children.copy()[::-1]):
            idx = ct - 1 - i
            if isinstance(child, SfmText):
                texts = re.split(r" {2}", child.text)
                if len(texts) > 1:
                    children.pop(idx)
                    for text in texts[::-1]:
                        children.insert(idx, SfmText(text))

        return children

    @property
    def intro(self):
        """Returns initial characters of text element. Mostly used for logging."""
        if len(self.text) > 23:
            s = f"{self.text[:20]}..."
        else:
            s = self.text
        return s

    @property
    def marker(self):
        if self._marker is None:
            match = self.RE_SFM_INIT.search(self.sfm_raw)
            if match is None:
                raise ValueError(f"No intial SFM marker: {self.sfm_raw}")
            self._marker = match[0].rstrip()
            self._marker_separator = match[0][-1]
        return self._marker

    @marker.setter
    def marker(self, value):
        old_marker = self.marker
        self._marker = value
        self.sfm_raw = (
            f"{self.marker} {self.sfm_raw.removeprefix(old_marker).lstrip(' ')}"
        )

    @property
    def odt_style(self):
        return self._odt_style

    @odt_style.setter
    def odt_style(self, value):
        self._odt_style = value

    @property
    def sfm_raw(self):
        return self._sfm_raw

    @sfm_raw.setter
    def sfm_raw(self, value):
        if not value.startswith("\\"):
            raise ValueError(f'SFM text does not begin with a backslash: "{value}"')
        self._sfm_raw = value

    @property
    def spans(self):
        return [c for c in self.children if isinstance(c, SfmSpan)]

    @property
    def text(self):
        if self._text is None:
            text = self.sfm_raw
            # Remove leading SFM marker.
            if self.marker:
                text = text.removeprefix(f"{self.marker}{self._marker_separator}")
            # Replace Paratext placeholder characters.
            text = self._sanitize(text)
            self._text = text
        return self._text

    @property
    def texts(self):
        return [c for c in self.children if isinstance(c, SfmText)]

    def _normalize(self, text):
        return normalize_text(self.normalization_form, text)

    def _sanitize(self, text):
        return undo_paratext_replacements(text)

    def __str__(self):
        return self.sfm_raw


class SfmText(SfmElement):
    NODE_TYPE = "text"

    @property
    def children(self):
        return list()

    @property
    def marker(self):
        return None

    @property
    def data(self):
        return self.text


class SfmSpan(SfmElement):
    """Text that has additional, character-level formatting added.
    It must close with another SFM marker that matches the first one, unless
    it's a verse number reference."""

    NODE_TYPE = "span"
    RE_SFM_END = re.compile(r"\\[a-z]+\*$")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._end_marker = None
        if self.end_marker and self.marker != self.end_marker.rstrip("*"):
            raise ValueError(f"Unmatched markers: {self.marker} & {self.end_marker}")

    @property
    def end_marker(self):
        if self._end_marker is None:
            if self.marker == "\\v":  # verses are spans with no end markers
                return self._end_marker
            match = self.RE_SFM_END.search(self.sfm_raw)
            if match is None:
                raise ValueError(f"No intial SFM marker: {self.sfm_raw}")
            self._end_marker = match[0].rstrip()
        return self._end_marker

    @property
    def text(self):
        if self._text is None:
            # Initialize and remove leading SFM marker.
            text = super().text
            # Check for trailing SFM marker.
            if self.end_marker and self.end_marker.rstrip("*") == self.marker:
                # Remove "closing" marker.
                text = text.removesuffix(self.end_marker)
            else:  # verse span
                # Remove end space.
                text = text.rstrip(" ")
            self._text = text
        return self._text


class SfmParagraph(SfmElement):
    """Paragraphs can be composed of multiple text lines if containing one or
    more verses. They can contain zero or more spans."""

    NODE_TYPE = "paragraph"

    @property
    def text(self):
        if self._text is None:
            text = ""
            for i, c in enumerate(self.children):
                if hasattr(c, "end_marker") and c.end_marker is not None:
                    text += f"{c.text}"
                elif i == len(self.children) - 1:  # no space after last child
                    text += f"{c.text}"
                else:
                    text += f"{c.text} "
            self._text = text
        return self._text
