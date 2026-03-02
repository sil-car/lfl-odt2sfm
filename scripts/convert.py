import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from odt2sfm.conversions import OdtToSfm, SfmToOdt


def main():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
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
        logger_filepath = source_path / "odt2sfm.log"
        conv = OdtToSfm
    else:
        raise ValueError(f"Invalid source: {source_path}")

    if conv is SfmToOdt:
        if dest_path is None or not dest_path.is_dir():
            raise ValueError(
                f"{conv} conversion requires a destination dir containing ODT files."
            )
        logger_filepath = dest_path / "odt2sfm.log"

    # Add file handler to logger and remove console logger.
    logfile_handler = logging.FileHandler(logger_filepath)
    logfile_handler.setFormatter(logger.handlers[0].formatter)  # use console formatter
    logger_filepath.write_text("")  # truncate the file
    logger.addHandler(logfile_handler)
    logger.removeHandler(logger.handlers[0])
    logging.info(f"Script start time: {datetime.now()}")

    # Run converion.
    c = conv(source=source_path, destination=dest_path)
    # c.compare_paragraphs((c.sfm_book.chapters[1], c.odt_book.chapters[1]))
    c.run()


if __name__ == "__main__":
    main()
