import argparse
import logging
from pathlib import Path

from odt2sfm import OdtChapter
from odt2sfm.base import LOG_FORMAT
from odt2sfm.odt.base import get_node_doc_style

log = logging.getLogger("odt2sfm.odt")


def odt_paragraphs():
    parser = argparse.ArgumentParser()
    parser.add_argument("PATH", type=Path)
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

    if args.PATH.is_dir():
        files = [f for f in args.PATH.iterdir() if f.suffix == ".odt"]
        files.sort()
        for i, f in enumerate(files[:]):
            if "TOC" in f.name:
                files.insert(0, files.pop(i))
                break
        docs = [OdtChapter(f) for f in files]
    else:
        docs = [OdtChapter(args.PATH)]
    for doc in docs:
        log.debug(f"{doc.styles=}")
        if args.all:
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
        else:
            for p in doc.paragraphs:
                print(f"[{get_node_doc_style(p, doc.odt)}] {p.text_recursive}")