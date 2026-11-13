"""Tests for odt2sfm.base helpers."""

import re
from types import SimpleNamespace as NS

import pytest

from odt2sfm.base import (
    SFM_ONLY_MARKERS,
    do_paratext_replacements,
    get_timestamp,
    normalize_text,
    undo_paratext_replacements,
    verify_paragraph_children_count,
    verify_paragraph_count,
    verify_sfm_markers,
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


def _para(marker, intro="x"):
    return NS(marker=marker, intro=intro, children=[])


def test_verify_paragraph_count_ignores_sfm_only_markers():
    sfm_ch = NS(
        number=1,
        paragraphs=[_para(m) for m in SFM_ONLY_MARKERS] + [_para("\\p"), _para("\\s1")],
    )
    odt_ch = NS(paragraphs=[_para(None), _para(None)])
    verify_paragraph_count(sfm_ch, odt_ch)  # no exception


def test_verify_paragraph_count_mismatch_raises():
    sfm_ch = NS(number=3, paragraphs=[_para("\\p")])
    odt_ch = NS(paragraphs=[_para(None), _para(None)])
    with pytest.raises(ValueError, match="ch. 3; SFM: 1; ODT: 2"):
        verify_paragraph_count(sfm_ch, odt_ch)


@pytest.mark.parametrize(("n_sfm", "n_odt", "expected"), [(2, 2, 0), (3, 2, 1), (1, 2, -1)])
def test_verify_paragraph_children_count(n_sfm, n_odt, expected):
    child = NS(intro="c")
    sfm_p = NS(children=[child] * n_sfm, intro="s")
    odt_p = NS(children=[child] * n_odt, intro="o")
    assert verify_paragraph_children_count(sfm_p, odt_p) == expected


def test_verify_sfm_markers():
    sfm_ch = NS(paragraphs=[_para("\\id"), NS(marker="\\p", text="t")])
    odt_ch = NS(paragraphs=[NS(style="Body", text="t")], styles={"Body": "\\p"})
    verify_sfm_markers(sfm_ch, odt_ch)  # no exception

    odt_ch.styles = {"Body": "\\m"}
    with pytest.raises(ValueError, match="expected: \\\\m"):
        verify_sfm_markers(sfm_ch, odt_ch)
