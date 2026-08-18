import argparse
import os
from pathlib import Path

from odt2sfm import normalize


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-b",
        "--backup",
        action="store_true",
        help="make a backup of the file before normalizing",
    )
    parser.add_argument(
        "FORM", nargs=1, help="desired character form", choices=["NFC", "NFD"]
    )
    parser.add_argument(
        "FILE", nargs="+", type=writable_file, help="Paratext project folder path"
    )
    return parser.parse_args()


def writable_file(value):
    p = Path(value)
    if not p.is_file():
        raise argparse.ArgumentTypeError(f"Not a valid file: {value}")
    elif not os.access(p, os.R_OK):
        raise argparse.ArgumentTypeError(f"File not readable: {value}")
    elif not os.access(p, os.W_OK):
        raise argparse.ArgumentTypeError(f"File not writable: {value}")
    return p


def main():
    args = get_args()
    for f in args.FILE:
        normalize.normalize_file(args.FORM[0], f, backup=args.backup)
