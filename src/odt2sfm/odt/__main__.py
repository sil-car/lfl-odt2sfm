import argparse
import logging
from pathlib import Path

from odt2sfm import OdtChapter
from odt2sfm.base import LOG_FORMAT
from odt2sfm.odt.base import get_node_doc_style

log = logging.getLogger("odt2sfm.odt")


def odt_paragraphs():
    parser = argparse.ArgumentParser()
    parser.add_argument("FILE", type=Path)
    parser.add_argument("--all", action="store_true")
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
    log.debug(f"{doc.styles=}")
    for p in doc.all_paragraphs:
        doc_style = get_node_doc_style(p, doc.odt)
        skipped = "(skipped) " if doc_style not in doc.styles else ""
        if not args.all:
            if skipped:
                continue
            else:
                print(f"[{doc_style}] {p.text_recursive}")
        else:
            print(f"[{doc_style}] {skipped}{p.text_recursive}")
