import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from odt2sfm.conversions import OdtToSfm, SfmToOdt


def main():
    logging.getLogger().setLevel(logging.DEBUG)
    # logging.getLogger().setLevel(logging.INFO)
    # logging.getLogger().setLevel(logging.WARNING)

    source_path = None
    dest_path = None
    if len(sys.argv) > 1:
        source_path = Path(sys.argv[1])
    else:
        raise ValueError("Need a source file (SFM) or dir (ODTs).")
    if len(sys.argv) > 2:
        dest_path = Path(sys.argv[2])

    if source_path.suffix.lower() == ".sfm":
        conv = SfmToOdt
    elif source_path.is_dir():
        conv = OdtToSfm
    else:
        raise ValueError(f"Invalid source: {source_path}")

    if conv is SfmToOdt:
        if dest_path is None or not dest_path.is_dir():
            raise ValueError(
                f"{conv} conversion requires a destination dir containing ODT files."
            )

    c = conv(source=source_path, destination=dest_path)
    # c.compare_paragraphs((c.sfm_book.chapters[1], c.odt_book.chapters[1]))
    c.run()


if __name__ == "__main__":
    main()
