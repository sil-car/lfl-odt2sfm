import re
from pathlib import Path

from .elements import SfmParagraph


class SfmChapter:
    """A complete SFM Chapter, with one or more paragraphs and zero or more verses."""

    def __init__(self, raw_sfm=None, parent=None):
        self._number = None
        self._odt_styles = None
        self.parent = parent
        self._sfm_raw = None
        if raw_sfm is not None:
            self.sfm_raw = raw_sfm

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
            for line in ref_file.read_text().splitlines():
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


class SfmBook:
    """A complete SFM file with one or more Chapters.
    The data is read from the source file. Any changes are written to a new
    destination file."""

    def __init__(self, file_path=None, odt_dir_path=None, normalization_mode=None):
        self._chapters = None
        self.file_path = None
        if file_path is not None:
            self.file_path = Path(file_path)
        self._id_text = None
        self._name = None
        self.normalization_mode = normalization_mode
        self.odt_dir_path = None
        if odt_dir_path is not None:
            self.odt_dir_path = Path(odt_dir_path)
        self.parent = None
        self._sfm_raw = None

    def __str__(self):
        return self.name

    @property
    def id_text(self):
        if self._id_text is None:
            m = re.search(r"\\id (.*)\n", self.sfm_raw)
            if m:
                self._id_text = m[1]
        return self._id_text

    @property
    def name(self):
        if self._name is None:
            if self.file_path is not None:
                self._name = self.file_path.name
            else:
                self._name = ""
        return self._name

    @property
    def sfm_raw(self):
        if self._sfm_raw is None:
            self._sfm_raw = self.file_path.read_text()
        return self._sfm_raw

    @property
    def chapters(self):
        if self._chapters is None:
            chapters = []
            init = True
            for c in re.split(r"\\c ", self.sfm_raw):
                if init:
                    sfm_raw = c.rstrip(" ")
                    init = False
                else:
                    sfm_raw = f"\\c {c.rstrip(' ')}"
                # TODO: Do we need to preserve chapter numbers for some reason?
                chapters.append(SfmChapter(sfm_raw, parent=self))
            self._chapters = chapters.copy()
        return self._chapters
