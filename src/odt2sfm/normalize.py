import shutil
import unicodedata


def normalize_file(form, file_path, backup=False):
    """Rewrite a UTF-8 text file in the given Unicode normalization form.

    Only the normalization changes: line endings (CRLF or LF), a byte-order
    mark and the presence or absence of a final newline are preserved.
    """
    if backup is True:
        backup_file = file_path.with_name(f"{file_path.name}.prenormalize.bak")
        if not backup_file.is_file():
            shutil.copy(file_path, backup_file)
        else:
            print(f"File exists, skipping backup: {backup_file}")
    text = file_path.read_bytes().decode("utf-8")
    file_path.write_bytes(unicodedata.normalize(form, text).encode("utf-8"))
