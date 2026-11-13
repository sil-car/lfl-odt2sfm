import re
from pathlib import Path

from odt2sfm.sfm.elements import SfmParagraph


class SfmChapter:
    """A complete SFM Chapter, with one or more paragraphs and zero or more verses."""

    def __init__(self, raw_sfm: str, parent=None):
        self._sfm_raw = raw_sfm
        self.parent = parent
        self._number = None
        self._odt_styles = None

    @property
    def intro(self):
        """Returns initial characters of text element; used in logging."""
        if len(self.sfm_raw) > 23:
            s = f"{self.sfm_raw[:20]}..."
        else:
            s = self.sfm_raw
        return s

    @property
    def number(self):
        if self._number is None:
            m = re.match(r"^\\c ([0-9]+)?", self.sfm_raw)
            if m:
                # \\c marker was found; check for chapter number.
                if m[1] is not None:
                    self._number = int(m[1])
                else:
                    raise ValueError(
                        f"No chapter number found after \\c marker: {m[0]}"
                    )
            elif self.sfm_raw.startswith("\\id"):
                self._number = 0
        return self._number

    @property
    def paragraphs(self):
        """A multiline text with a specific, defined style. It may also contain
        "spans" or "verses", which might have their own, character-level styles."""

        paragraphs = []
        for line in self.sfm_raw.splitlines():
            if len(line) == 0:  # noqa: SIM114
                continue
            elif line.startswith("\\c"):
                continue
            elif line.startswith("\\v"):
                # Add to previous line's paragraph.
                p = paragraphs.pop()
                line = f"{p.sfm_raw}\n{line}"
            paragraphs.append(SfmParagraph(line, parent=self))
        return paragraphs

    @property
    def odt_styles(self):
        if self._odt_styles is None:
            styles = {}
            ref_file = Path(__file__).parents[2] / "ref.txt"
            for line in ref_file.read_text(encoding="utf-8").splitlines():
                try:
                    k, v = line.split("\\")
                    k = k.strip()
                    v = f"\\{v.strip()}"
                    if not styles.get(v):
                        styles[v] = []
                    styles[v].append(k)
                except ValueError as e:
                    raise ValueError(f"{e}: {line}")
            self._odt_styles = styles
        return self._odt_styles

    @property
    def sfm_raw(self):
        return self._sfm_raw

    @sfm_raw.setter
    def sfm_raw(self, value):
        self._sfm_raw = value

    @property
    def verses(self):
        verses = []
        init = True
        for v in re.split(r"\\v ", self.sfm_raw):
            if init:  # skip first "split", which is not a verse
                init = False
                continue
            sfm_raw = f"\\v {v.rstrip()}"
            # TODO: Do we need to preserve chapter numbers for some reason?
            verses.append(sfm_raw)
        return verses

    def __str__(self):
        return self.sfm_raw