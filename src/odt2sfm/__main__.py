import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path

from odt2sfm import __version__
from odt2sfm.base import LOG_FORMAT
from odt2sfm.conversions import OdtToSfm, SfmToOdt

log = logging.getLogger("odt2sfm")


def parse_args():
    prog = "odt2sfm"
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="use debug output in log file",
    )
    parser.add_argument(
        "-m",
        "--normalization-mode",
        choices=["NFC", "NFD"],
        default="NFC",
        help="set character normalization mode for destination file(s)",
    )
    parser.add_argument("source_path", type=Path, help="source file|dir")
    parser.add_argument("destination_path", type=Path, help="destination file|dir")
    return parser.parse_args()


def main():
    # Get args.
    args = parse_args()


    # Evaluate path args.
    if args.source_path.suffix.lower() == ".sfm":
        conv = SfmToOdt
    elif args.source_path.is_dir():
        conv = OdtToSfm
    else:
        raise ValueError(f"Invalid source: {args.source_path}")

    if conv is SfmToOdt:
        if not args.destination_path.is_dir():
            raise ValueError(
                f"{conv} conversion requires a destination dir containing ODT files."
            )
        logger_filepath = str(args.destination_path / "odt2sfm-import.log")
    else:
        logger_filepath = str(args.source_path / "odt2sfm-export.log")

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format=LOG_FORMAT,
        filename=logger_filepath,
        filemode="w",
    )

    log.info(f"Script start time: {datetime.now(tz=UTC)}")
    log.info(f"Conversion type: {conv.__name__}")

    # Run converion.
    c = conv(
        source=args.source_path,
        destination=args.destination_path,
        normalization_mode=args.normalization_mode,
    )
    c.run()
