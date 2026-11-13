# Real-data fixtures

Lessons 0 (TOC), 1 and 2 of the Sango "Lessons from Luke" Quarter 1 book, used for
end-to-end export/import tests (`@pytest.mark.realdata`).

- To keep the files small, every embedded image (`Pictures/*`, `Thumbnails/*`) was
  replaced with a 1×1 PNG. The text, styles and document structure are unchanged.
- The styles-reference files are copies of the ones in `reference/LfL-Sango/`.
- `../expected/94XXALtdLS.SFM` is the golden export of this folder. To regenerate it
  after an intentional change in output, run: `UPDATE_GOLDEN=1 pytest tests/test_roundtrip.py`
