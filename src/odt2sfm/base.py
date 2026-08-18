import unicodedata
from datetime import UTC, datetime

from . import logger

SFM_PLACEHOLDERS = {
    "~": "\u00a0",
}
SFM_ONLY_MARKERS = ("\\id", "\\rem", "\\usfm")
SFM_TEXT_SEP = " _"


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


def verify_paragraph_count(sfm_chapter, odt_chapter):
    # Compare paragraph counts in original data and updated data.
    sfm_ps = [p for p in sfm_chapter.paragraphs if p.marker not in SFM_ONLY_MARKERS]
    odt_ps = odt_chapter.paragraphs
    len_sfm = len(sfm_ps)
    len_odt = len(odt_ps)
    if len_sfm != len_odt:
        for i, (p1, p2) in enumerate(zip(sfm_ps, odt_ps)):
            logger.error(f"{i}:SFM: {p1}")
            logger.error(f"{i}:ODT: {p2}")
        raise ValueError(
            f"Paragraph counts differ for ch. {sfm_chapter.number}; SFM: {len_sfm}; ODT: {len_odt}"
        )


def verify_paragraph_children_count(sfm_paragraph, odt_paragraph):
    sfm_children = sfm_paragraph.children
    odt_children = odt_paragraph.children
    len_sfm = len(sfm_children)
    len_odt = len(odt_children)
    if len_sfm != len_odt:
        logger.warning(
            f"Unmatched children for ODT ({len_odt}) & SFM ({len_sfm}): {odt_paragraph.intro}|{sfm_paragraph.intro}"
        )
        for i, (c1, c2) in enumerate(zip(sfm_children, odt_children)):
            logger.info(f"{i}:SFM: {c1.text}")
            logger.info(f"{i}:ODT: {c2.text}")
    return len_sfm - len_odt


def verify_sfm_markers(sfm_chapter, odt_chapter):
    sfm_paragraphs = [
        p for p in sfm_chapter.paragraphs if p.marker not in SFM_ONLY_MARKERS
    ]
    for i, p in enumerate(odt_chapter.paragraphs):
        sfm = sfm_paragraphs[i].marker
        marker = odt_chapter.styles.get(p.style)
        if marker != sfm:
            raise ValueError(
                f'SFM marker ({sfm}) does not correspond to ODT style ({p.style}) for text "{p.text}"; expected: {marker}'
            )
