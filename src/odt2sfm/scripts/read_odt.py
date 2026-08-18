import sys
from pathlib import Path

from odfdo import Document


def show_content(content, all=False):
    t_last = ""
    for k, v in content.items():
        s, t = v
        # Skip duplicated "English translation" paragraphs.
        if "english_20_translation" in s.lower():
            continue
        if not all:  # noqa: SIM102
            # Skip paragraphs whose text is identical to the previous paragraph.
            if str(t) == str(t_last):
                continue
        t_last = t
        print(f"{k:2d}: [{s}] {t}")


def main():
    infile = Path(sys.argv[1])
    doc = Document(infile)
    footer = None
    for page in doc.styles.master_pages:
        footer = page.get_page_footer()
        if not footer:
            continue
        for paragraph in footer.paragraphs:
            print(
                f"{page.name}/{footer.tag}/{paragraph.tag}:{paragraph.text_recursive}"
            )
