import unittest
from pathlib import Path

from odt2sfm import OdtChapter, SfmBook, SfmToOdt

DATA = Path(__file__).parent / "data"
ODT_PATH = DATA / "chapter.odt"
SFM_PATH = DATA / "book.sfm"


@unittest.skip("No valid tests defined.")
class TestSfmToOdt(unittest.TestCase):
    def setUp(self):
        self.odt_chapter = OdtChapter(ODT_PATH)
        self.sfm_book = SfmBook(SFM_PATH)
        self.conv = SfmToOdt(source=SFM_PATH, destination=DATA)

    def test_compare_styles(self):
        self.conv.compare_odt_chapter_with_sfm_chapter(self.odt_chapter, self.sfm_book.chapters[3])
