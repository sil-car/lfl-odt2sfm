import argparse
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
        "PROJECT", nargs=1, type=ptx_project_dir, help="Paratext project folder path"
    )
    return parser.parse_args()


def ptx_project_dir(value):
    p = Path(value)
    if not p.is_dir():
        raise argparse.ArgumentTypeError(f'Not a valid folder path: "{value}"')
    elif not (p / "unique.id").is_file():
        raise argparse.ArgumentTypeError(
            f'Not a valid Paratext project folder: "{value}"'
        )
    return p


def main():
    args = get_args()
    form = args.FORM[0]
    project = args.PROJECT[0]
    files = sorted(f for f in project.iterdir() if f.suffix.lower() == ".sfm")
    for f in files:
        normalize.normalize_file(form, f, backup=args.backup)
