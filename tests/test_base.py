"""Tests for odt2sfm.base helpers."""

import re
from types import SimpleNamespace as NS

import pytest

from odt2sfm.base import (
    SFM_ONLY_MARKERS,
    do_paratext_replacements,
    find_chapter_mismatches,
    get_timestamp,
    normalize_text,
    translatable_sfm_paragraphs,
    undo_paratext_replacements,
    verify_paragraph_children_count,
)

NBSP = " "
E_ACUTE_NFC = "é"
E_ACUTE_NFD = "é"


def test_timestamp_format():
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", get_timestamp())


@pytest.mark.parametrize(
    ("form", "text", "expected"),
    [
        ("NFC", E_ACUTE_NFD, E_ACUTE_NFC),
        ("NFD", E_ACUTE_NFC, E_ACUTE_NFD),
        ("NFC", E_ACUTE_NFC, E_ACUTE_NFC),
    ],
)
def test_normalize_text(form, text, expected):
    assert normalize_text(form, text) == expected


def test_paratext_replacements_roundtrip():
    odt = f"a{NBSP}b{NBSP}:"
    sfm = do_paratext_replacements(odt)
    assert sfm == "a~b~:"
    assert undo_paratext_replacements(sfm) == odt


def _sfm_p(marker, n_children=1, intro="x"):
    return NS(marker=marker, intro=intro, children=[NS(intro="c")] * n_children)


def _odt_p(style, n_children=1, intro="x"):
    return NS(style=style, intro=intro, children=[NS(intro="c")] * n_children)


def _chapters(sfm_ps, odt_ps, number=1):
    sfm_ch = NS(number=number, paragraphs=[_sfm_p(m) for m in SFM_ONLY_MARKERS] + sfm_ps)
    odt_ch = NS(paragraphs=odt_ps, styles={"Body": "\\p", "Head": "\\s1"})
    return sfm_ch, odt_ch


def test_translatable_sfm_paragraphs_excludes_sfm_only_markers():
    sfm_ch, _ = _chapters([_sfm_p("\\p")], [])
    assert [p.marker for p in translatable_sfm_paragraphs(sfm_ch)] == ["\\p"]


def test_find_chapter_mismatches_none():
    sfm_ch, odt_ch = _chapters(
        [_sfm_p("\\s1"), _sfm_p("\\p", 3)], [_odt_p("Head"), _odt_p("Body", 3)]
    )
    assert find_chapter_mismatches(sfm_ch, odt_ch) == []


def test_find_chapter_mismatches_paragraph_count_stops_further_checks():
    sfm_ch, odt_ch = _chapters([_sfm_p("\\q")], [_odt_p("Body"), _odt_p("Body")], number=3)
    assert find_chapter_mismatches(sfm_ch, odt_ch) == [
        "ch. 3: paragraph counts differ; SFM: 1; ODT: 2"
    ]


def test_find_chapter_mismatches_reports_every_problem():
    sfm_ch, odt_ch = _chapters(
        [
            _sfm_p("\\p", intro="wrong marker"),
            _sfm_p("\\p", 2, intro="fewer parts"),
            _sfm_p("\\p", 4, intro="more parts"),
            _sfm_p("\\p", 3, intro="fine"),
        ],
        [_odt_p("Head"), _odt_p("Body", 3), _odt_p("Body", 3), _odt_p("Body", 3)],
    )
    problems = find_chapter_mismatches(sfm_ch, odt_ch)
    assert len(problems) == 3
    assert problems[0].startswith("ch. 1, paragraph 1: SFM marker \\p does not match")
    assert "(expected \\s1)" in problems[0] and "wrong marker" in problems[0]
    assert problems[1].startswith("ch. 1, paragraph 2 (\\p): SFM has 2 parts, ODT has 3")
    assert problems[2].startswith("ch. 1, paragraph 3 (\\p): SFM has 4 parts, ODT has 3")


@pytest.mark.parametrize(("n_sfm", "n_odt", "expected"), [(2, 2, 0), (3, 2, 1), (1, 2, -1)])
def test_verify_paragraph_children_count(n_sfm, n_odt, expected):
    child = NS(intro="c")
    sfm_p = NS(children=[child] * n_sfm, intro="s")
    odt_p = NS(children=[child] * n_odt, intro="o")
    assert verify_paragraph_children_count(sfm_p, odt_p) == expected
