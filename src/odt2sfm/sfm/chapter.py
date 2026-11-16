import re

from odt2sfm.sfm.elements import SfmParagraph


class SfmChapter:
    """A complete SFM Chapter, with one or more paragraphs and zero or more verses."""

    def __init__(self, raw_sfm: str, parent=None):
        self._sfm_raw = raw_sfm
        self.parent = parent
        self._number = None

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
    def sfm_raw(self):
        return self._sfm_raw

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