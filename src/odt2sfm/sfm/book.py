import re
from pathlib import Path

from odt2sfm.sfm.chapter import SfmChapter


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
        if self._id_text is None and self.sfm_raw:
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
        if self._sfm_raw is None and self.file_path:
            # utf-8-sig: ignore a byte-order mark (BOM) added by some Windows editors.
            self._sfm_raw = self.file_path.read_text(encoding="utf-8-sig")
        return self._sfm_raw

    @property
    def chapters(self):
        if self._chapters is None:
            chapters = []
            init = True
            if self.sfm_raw:
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
