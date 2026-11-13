"""Tests for odt2sfm.normalize."""

import unicodedata

import pytest

from odt2sfm.normalize import normalize_file

TEXT = "\\p café crème\n\\p deuxième\n"


@pytest.mark.parametrize("form", ["NFC", "NFD"])
def test_normalize_file(tmp_path, form):
    f = tmp_path / "41XXA.SFM"
    f.write_text(TEXT, encoding="utf-8")
    normalize_file(form, f)
    result = f.read_text(encoding="utf-8")
    assert result == unicodedata.normalize(form, TEXT)
    assert unicodedata.is_normalized(form, result)


def test_backup_created_once(tmp_path, capsys):
    f = tmp_path / "41XXA.SFM"
    f.write_text(TEXT, encoding="utf-8")
    backup = tmp_path / "41XXA.SFM.prenormalize.bak"

    normalize_file("NFD", f, backup=True)
    assert backup.read_text(encoding="utf-8") == TEXT

    # A second run must not overwrite the original backup.
    normalize_file("NFC", f, backup=True)
    assert backup.read_text(encoding="utf-8") == TEXT
    assert "skipping backup" in capsys.readouterr().out


def test_no_backup_by_default(tmp_path):
    f = tmp_path / "41XXA.SFM"
    f.write_text(TEXT, encoding="utf-8")
    normalize_file("NFC", f)
    assert list(tmp_path.iterdir()) == [f]
