import argparse
import logging
from pathlib import Path

from odt2sfm.base import LOG_FORMAT, SFM_ONLY_MARKERS
from odt2sfm.sfm import SfmBook

log = logging.getLogger("odt2sfm.sfm")


def sfm_paragraphs():
    parser = argparse.ArgumentParser()
    parser.add_argument("FILE", type=Path)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--chapter", "-c", type=int, default=-1)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    log_level = logging.WARNING
    if args.verbose:
        log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
    )

    book = SfmBook(args.FILE)
    chapters = book.chapters if args.chapter == -1 else [book.chapters[args.chapter]]
    # log.debug(f"{doc.styles=}")
    for c in chapters:
        for p in c.paragraphs:
            if p.marker not in SFM_ONLY_MARKERS:
                print(f"[{p.marker}] {p.text}")
