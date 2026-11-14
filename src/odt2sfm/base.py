import logging
import re
import unicodedata
from datetime import UTC, datetime

log = logging.getLogger(__name__)

LOG_FORMAT = "%(levelname)s: [%(name)s:%(lineno)d]: %(message)s"
SFM_PLACEHOLDERS = {
    "~": "\u00a0",
}
SFM_ONLY_MARKERS = ("\\id", "\\rem", "\\usfm")
SFM_TEXT_SEP = " _"
# A separator is never followed by another underscore, so that a
# fill-in-the-blank ("na ya ti ______") is read as text, not a separator.
RE_SFM_TEXT_SEP = re.compile(r" _(?!_)")


def get_timestamp():
    return datetime.now(tz=UTC).strftime("%Y-%m-%d")


def normalize_text(normalization_form, text):
    return unicodedata.normalize(normalization_form, text)


def do_paratext_replacements(text):
    for sfm_str, odt_str in SFM_PLACEHOLDERS.items():
        text = text.replace(odt_str, sfm_str)
    return text


def undo_paratext_replacements(text):
    for sfm_str, odt_str in SFM_PLACEHOLDERS.items():
        text = text.replace(sfm_str, odt_str)
    return text


def translatable_sfm_paragraphs(sfm_chapter):
    """Return the chapter's SFM paragraphs that correspond to ODT paragraphs."""
    return [p for p in sfm_chapter.paragraphs if p.marker not in SFM_ONLY_MARKERS]


def find_chapter_mismatches(sfm_chapter, odt_chapter) -> list[str]:
    """Return a description of every structural difference between an SFM
    chapter and the ODT chapter it will be imported into.

    Text is imported piece by piece by position, so the SFM must have the
    same paragraphs, with the same markers, and the same number of parts
    (plain text runs and character-styled spans) in each paragraph.
    """
    ch = sfm_chapter.number
    sfm_ps = translatable_sfm_paragraphs(sfm_chapter)
    odt_ps = odt_chapter.paragraphs
    if len(sfm_ps) != len(odt_ps):
        # Paragraphs can't be paired up, so further checks are meaningless.
        return [f"ch. {ch}: paragraph counts differ; SFM: {len(sfm_ps)}; ODT: {len(odt_ps)}"]

    mismatches = []
    for i, (sfm_p, odt_p) in enumerate(zip(sfm_ps, odt_ps), start=1):
        log.debug(f"ch. {ch}, paragraph {i}: SFM: {sfm_p.intro}; ODT: {odt_p.intro}")
        expected = odt_chapter.styles.get(odt_p.style)
        if sfm_p.marker != expected:
            mismatches.append(
                f'ch. {ch}, paragraph {i}: SFM marker {sfm_p.marker} does not match '
                f'ODT style "{odt_p.style}" (expected {expected}): "{sfm_p.intro}"'
            )
            continue
        n_sfm, n_odt = len(sfm_p.children), len(odt_p.children)
        if n_sfm != n_odt:
            mismatches.append(
                f"ch. {ch}, paragraph {i} ({sfm_p.marker}): SFM has {n_sfm} parts, "
                f'ODT has {n_odt} (text runs and character styles must match): "{sfm_p.intro}"'
            )
    return mismatches


def verify_paragraph_children_count(sfm_paragraph, odt_paragraph):
    sfm_children = sfm_paragraph.children
    odt_children = odt_paragraph.children
    len_sfm = len(sfm_children)
    len_odt = len(odt_children)
    if len_sfm != len_odt:
        log.warning(
            f"Unmatched children for ODT ({len_odt}) & SFM ({len_sfm}): {odt_paragraph.intro}|{sfm_paragraph.intro}"
        )
        for i, (c1, c2) in enumerate(zip(sfm_children, odt_children)):
            log.info(f"{i}: SFM: {c1.intro}; ODT: {c2.intro}")
    return len_sfm - len_odt
