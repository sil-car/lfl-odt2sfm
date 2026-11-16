"""Known bugs and wanted behavior, written as strict xfail tests.

Each test asserts the *desired* behavior. While the bug exists the test
fails and is reported as XFAIL. Once the bug is fixed the test passes, which
``xfail_strict = true`` reports as a failure: remove the xfail mark then.

Where possible, ``raises=`` names the exception the bug produces today, so a
different failure is reported as a real error instead of being hidden.
"""

import pytest

from odt2sfm.odt import OdtChapter
from odt2sfm.odt.base import node_has_paragraph_descendent_with_text
from tests.conftest import p, span

# --- Export of ODT content ---


def test_node_has_paragraph_descendent_with_text_first_child(make_odt):
    """Control case: nested paragraph is the first child."""
    path = make_odt([p("Text_20_body", "<draw:frame><draw:text-box>" + p("Quotations", "in") + "</draw:text-box></draw:frame>")])
    assert node_has_paragraph_descendent_with_text(OdtChapter(path).all_paragraphs[0])


@pytest.mark.xfail(reason="node_has_paragraph_descendent_with_text only inspects the first child.")
def test_node_has_paragraph_descendent_with_text_not_first_child(make_odt):
    frame = "<draw:frame><draw:text-box>" + p("Quotations", "in") + "</draw:text-box></draw:frame>"
    path = make_odt([p("Text_20_body", span("T2", "x") + frame)])
    assert node_has_paragraph_descendent_with_text(OdtChapter(path).all_paragraphs[0])
