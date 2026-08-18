import shutil
import tempfile
import unicodedata


def normalize_file(form, file_path, backup=False):
    if backup is True:
        backup_file = file_path.with_name(f"{file_path.name}.prenormalize.bak")
        if not backup_file.is_file():
            shutil.copy(file_path, backup_file)
        else:
            print(f"File exists, skipping backup: {backup_file}")
    with tempfile.TemporaryFile() as t:
        f = file_path.read_text()
        for line in f.splitlines():
            t.write(unicodedata.normalize(form, f"{line}\n").encode())
        t.seek(0)
        file_path.write_bytes(t.read())
