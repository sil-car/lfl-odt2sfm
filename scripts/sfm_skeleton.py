"""Print the structure of an SFM file with the text hidden.

Each paragraph goes on one line. Markers, chapter and verse numbers and
" _" separators are kept. Each stretch of ordinary words becomes "x", and
every space that isn't a single space between two words is shown as "·",
so differences in spacing around "_" stand out.

Each line starts with [chapter:paragraph], counting the paragraphs after
the \\c line, so you can find it in Paratext.

Usage: python3 sfm_skeleton.py FILE.SFM > FILE.skel
"""
import re
import sys
from pathlib import Path

MARKER = re.compile(r"(\\[a-z]+[0-9]*\*?)")
WORDS = re.compile(r"[^\s_]+(?: [^\s_]+)*")  # words joined by single spaces
NUMBERED = ("\\c", "\\v")                       # keep the number after these
SKIP_TEXT = ("\\id", "\\rem", "\\usfm")          # header lines: marker only


def skeleton_text(text):
    return WORDS.sub("x", text).replace(" ", "·").replace("\t", "→")


def skeleton_paragraph(para):
    out = []
    parts = MARKER.split(para)
    prev_marker = None
    for part in parts:
        if not part:
            continue
        if MARKER.fullmatch(part):
            out.append(part)
            prev_marker = part
            continue
        if prev_marker in SKIP_TEXT:
            continue
        if prev_marker and not prev_marker.endswith("*"):
            # One space always follows a marker; it isn't part of the text.
            part = part.removeprefix(" ")
            if not part:
                prev_marker = None
                continue
            if prev_marker in NUMBERED:
                num, _, part = part.partition(" ")
                out[-1] += f" {num}"
                if part:
                    out.append(skeleton_text(part))
                prev_marker = None
                continue
        out.append(skeleton_text(part))
        prev_marker = None
    return " ".join(out)


def main(path):
    text = Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    paras = []
    for line in text.split("\n"):
        # A line starting with a marker other than \v starts a new paragraph.
        if not line:
            continue
        if line.startswith("\\") and not line.startswith("\\v "):
            paras.append(line)
        elif not paras:
            paras.append(line)
        elif line.startswith("\\v "):
            # The newline before a verse is only layout.
            paras[-1] += line
        else:
            # A line wrapped by an editor: the newline stands for a space.
            paras[-1] += " " + line
    chapter, n = 0, 0
    for para in paras:
        if para.startswith("\\c "):
            chapter, n = para.split()[1], 0
            print(para.split()[0], chapter)
            continue
        if not para.startswith(SKIP_TEXT):
            n += 1
        # Label: chapter and paragraph number within it, to find it in Paratext.
        print(f"[{chapter}:{n}] {skeleton_paragraph(para)}")


if __name__ == "__main__":
    main(sys.argv[1])
