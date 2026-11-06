import argparse
import logging
from pathlib import Path

from odt2sfm.base import LOG_FORMAT
from odt2sfm.odt import OdtChapter

log = logging.getLogger("odt2sfm.odt")


def odt_styles():
    parser = argparse.ArgumentParser()
    parser.add_argument("FILE", type=Path)
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

    doc = OdtChapter(args.FILE)
    for p in doc.paragraphs:
        print(f"{p.style}: {p.text_recursive}")