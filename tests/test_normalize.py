"""Tests for odt2sfm.normalize."""

import argparse
import os
import unicodedata

import pytest

from odt2sfm.normalize import normalize_file
from odt2sfm.scripts import normalize_files, normalize_project
from tests.conftest import E_ACUTE_NFC

TEXT = f"\\p caf{E_ACUTE_NFC} crème\n\\p deuxième\n"


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


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_ptx_project_dir_rejects_non_folder(tmp_path, kind):
    path = tmp_path / "LtdLS"
    if kind == "file":
        path.write_text("x", encoding="utf-8")
    with pytest.raises(argparse.ArgumentTypeError, match="Not a valid folder path"):
        normalize_project.ptx_project_dir(str(path))


@pytest.mark.parametrize(
    ("denied", "message"),
    [(os.R_OK, "File not readable"), (os.W_OK, "File not writable")],
)
def test_writable_file_rejects_missing_permission(monkeypatch, tmp_path, denied, message):
    f = tmp_path / "41XXA.SFM"
    f.write_text("\\p text\n", encoding="utf-8")
    monkeypatch.setattr(os, "access", lambda path, mode: mode != denied)
    with pytest.raises(argparse.ArgumentTypeError, match=message):
        normalize_files.writable_file(str(f))