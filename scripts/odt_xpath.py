#!/usr/bin/env python3
"""
odt_xpath.py - Find content at an XPath inside an ODT (OpenDocument) file
and show it with surrounding context.

An .odt file is a ZIP archive; the document body lives in content.xml
(styles in styles.xml, metadata in meta.xml). This script opens the chosen
part, evaluates your XPath with the standard ODF namespace prefixes
pre-registered, and for each match prints:

  * the full path to the node
  * the nearest heading above it (for content.xml)
  * its plain text (with ODF spaces/tabs/line breaks expanded)
  * a window of pretty-printed XML around it, with the match marked

Requires: lxml  (pip install lxml)

Examples
--------
  # Every paragraph
  python odt_xpath.py report.odt "//text:p"

  # Third paragraph in the body, 5 lines of XML context either side
  python odt_xpath.py report.odt "/office:document-content/office:body/office:text/text:p[3]" -C 5

  # All level-2 headings, text only
  python odt_xpath.py report.odt "//text:h[@text:outline-level='2']" --text-only

  # An attribute (shows the attribute value plus its element's context)
  python odt_xpath.py report.odt "//table:table/@table:name"

  # Look in styles.xml instead of content.xml
  python odt_xpath.py report.odt "//style:style[@style:name='Heading_20_1']" --part styles.xml

  # Don't know the path? Find which elements contain some text:
  python odt_xpath.py report.odt --locate "quarterly revenue"

  # Show the parts in the archive and the namespace prefixes you can use
  python odt_xpath.py report.odt --list-parts --list-ns
"""

import argparse
import sys
import zipfile

try:
    from lxml import etree
except ImportError:
    sys.exit("This script needs lxml:  pip install lxml")


# Standard ODF namespace prefixes, so XPaths work even if a document
# declares them differently (or not on the root element).
ODF_NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "dc": "http://purl.org/dc/elements/1.1/",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
    "number": "urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "chart": "urn:oasis:names:tc:opendocument:xmlns:chart:1.0",
    "dr3d": "urn:oasis:names:tc:opendocument:xmlns:dr3d:1.0",
    "math": "http://www.w3.org/1998/Math/MathML",
    "form": "urn:oasis:names:tc:opendocument:xmlns:form:1.0",
    "script": "urn:oasis:names:tc:opendocument:xmlns:script:1.0",
    "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",
    "ooo": "http://openoffice.org/2004/office",
    "loext": "urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}

TEXT_NS = ODF_NS["text"]


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def read_part(odt_path, part):
    try:
        with zipfile.ZipFile(odt_path) as z:
            names = z.namelist()
            if part not in names:
                xml_parts = [n for n in names if n.endswith(".xml")]
                sys.exit(f"'{part}' not found in {odt_path}.\n"
                         f"XML parts available: {', '.join(xml_parts)}")
            return z.read(part)
    except zipfile.BadZipFile:
        sys.exit(f"{odt_path} is not a valid ODT/ZIP file. "
                 f"(Flat .fodt files are plain XML; use any XPath tool on them directly.)")


def parse_trees(raw):
    """Return (original_root, pretty_root, pretty_lines, orig->pretty map).

    XPath runs on the untouched original tree (so whitespace and text are
    exact). A pretty-printed copy is built purely to give each element a
    meaningful line number for the context window; content.xml is usually
    one enormous line otherwise.
    """
    parser = etree.XMLParser(huge_tree=True)
    original = etree.fromstring(raw, parser)

    pretty_src = etree.fromstring(raw, parser)
    etree.indent(pretty_src, space="  ")
    pretty_bytes = etree.tostring(pretty_src, encoding="utf-8")
    pretty = etree.fromstring(pretty_bytes, parser)  # re-parse -> real sourcelines
    lines = pretty_bytes.decode("utf-8").splitlines()

    # indent() adds no nodes, so both trees iterate in the same order.
    mapping = dict(zip(original.iter(), pretty.iter()))
    return original, pretty, lines, mapping


def build_namespaces(root, extra):
    ns = dict(ODF_NS)
    for prefix, uri in (root.nsmap or {}).items():
        if prefix:  # XPath 1.0 can't use a default (None) namespace
            ns.setdefault(prefix, uri)
    for item in extra or []:
        if "=" not in item:
            sys.exit(f"--ns expects prefix=uri, got: {item}")
        prefix, uri = item.split("=", 1)
        ns[prefix] = uri
    return ns


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def odf_text(el):
    """Plain text of an element, expanding ODF's text:s / text:tab / text:line-break."""
    out = []

    def walk(node):
        if not isinstance(node.tag, str):  # comments / PIs
            return
        if node.tag == f"{{{TEXT_NS}}}s":
            out.append(" " * int(node.get(f"{{{TEXT_NS}}}c", "1")))
        elif node.tag == f"{{{TEXT_NS}}}tab":
            out.append("\t")
        elif node.tag == f"{{{TEXT_NS}}}line-break":
            out.append("\n")
        else:
            if node.text:
                out.append(node.text)
            for child in node:
                walk(child)
                if child.tail:
                    out.append(child.tail)
    walk(el)
    return "".join(out)


def qname(el, ns):
    """Prefixed name like text:p for display."""
    q = etree.QName(el)
    for prefix, uri in ns.items():
        if uri == q.namespace:
            return f"{prefix}:{q.localname}"
    return q.localname if not q.namespace else f"{{{q.namespace}}}{q.localname}"


def nearest_heading(el, ns):
    try:
        hits = el.xpath("(preceding::text:h | ancestor-or-self::text:h)[last()]",
                        namespaces=ns)
    except etree.XPathError:
        return None
    if hits:
        h = hits[0]
        level = h.get(f"{{{TEXT_NS}}}outline-level", "?")
        return f"[H{level}] {odf_text(h).strip()}"
    return None


def short(s, width):
    s = s.replace("\n", "\\n")
    return s if len(s) <= width else s[: width - 1] + "…"


def xml_window(pretty_el, lines, context, width):
    start = pretty_el.sourceline  # 1-based
    n_lines = etree.tostring(pretty_el, encoding="unicode", with_tail=False).count("\n") + 1
    end = start + n_lines - 1
    lo, hi = max(1, start - context), min(len(lines), end + context)
    num_w = len(str(hi))
    out = []
    for i in range(lo, hi + 1):
        mark = ">" if start <= i <= end else " "
        out.append(f"  {mark} {i:>{num_w}} | {short(lines[i - 1], width)}")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def report_element(idx, total, el, focus, tree, ns, lines, mapping, args):
    print(f"── Match {idx}/{total} " + "─" * 50)
    print(f"Path:    {tree.getpath(el)}")
    if focus:
        print(focus)
    if args.part == "content.xml":
        h = nearest_heading(el, ns)
        if h:
            print(f"Section: {short(h, args.width)}")

    text = odf_text(el)
    if text.strip():
        print(f"Text:    {short(text, args.width) if not args.full_text else text}")
    else:
        attrs = ", ".join(f'{qname_attr(k, ns)}="{v}"' for k, v in el.attrib.items())
        print(f"Element: <{qname(el, ns)}{' ' + attrs if attrs else ''}> (no text)")

    if args.siblings:
        parent = el.getparent()
        if parent is not None:
            sibs = [c for c in parent if isinstance(c.tag, str)]
            pos = sibs.index(el)
            lo, hi = max(0, pos - args.siblings), min(len(sibs), pos + args.siblings + 1)
            print("Siblings:")
            for s in sibs[lo:hi]:
                mark = "→" if s is el else " "
                print(f"  {mark} <{qname(s, ns)}> {short(odf_text(s).strip(), args.width - 20)}")

    if not args.text_only:
        print("XML:")
        print(xml_window(mapping[el], lines, args.context, args.width))
    print()


def qname_attr(key, ns):
    if key.startswith("{"):
        uri, local = key[1:].split("}", 1)
        for prefix, u in ns.items():
            if u == uri:
                return f"{prefix}:{local}"
    return key


def run_xpath(root, xpath, ns, args, lines, mapping):
    tree = root.getroottree()
    try:
        result = root.xpath(xpath, namespaces=ns)
    except etree.XPathEvalError as e:
        msg = str(e)
        if "Undefined namespace prefix" in msg:
            msg += " (add it with --ns prefix=uri, or check --list-ns)"
        sys.exit(f"XPath error: {msg}")

    # Scalar results: count(), string(), boolean expressions…
    if not isinstance(result, list):
        print(f"Result: {result!r}")
        return

    if not result:
        print("No matches.")
        return

    total = len(result)
    shown = result[: args.max] if args.max else result
    for i, r in enumerate(shown, 1):
        if isinstance(r, etree._Element) and isinstance(r.tag, str):
            report_element(i, total, r, None, tree, ns, lines, mapping, args)
        elif isinstance(r, etree._ElementUnicodeResult) or isinstance(r, str):
            parent = r.getparent() if hasattr(r, "getparent") else None
            if getattr(r, "is_attribute", False):
                focus = f"Attr:    {qname_attr(r.attrname, ns)} = {r!s}"
            elif getattr(r, "is_tail", False):
                focus = f"Tail text: {short(str(r), args.width)}"
            else:
                focus = f"Text node: {short(str(r), args.width)}"
            if parent is not None:
                report_element(i, total, parent, focus, tree, ns, lines, mapping, args)
            else:
                print(f"── Match {i}/{total}: {r!s}\n")
        else:  # comments, PIs, namespaces
            print(f"── Match {i}/{total}: {r!r}\n")

    if args.max and total > args.max:
        print(f"... {total - args.max} more match(es) not shown (raise --max).")


def locate(root, needle, ns, args):
    """Print paths of the innermost elements whose text contains `needle`."""
    tree = root.getroottree()
    needle_cmp = needle if args.case_sensitive else needle.lower()
    hits = []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        t = odf_text(el)
        if not args.case_sensitive:
            t = t.lower()
        if needle_cmp in t:
            # keep only innermost: drop any ancestor already recorded
            hits = [h for h in hits if el not in h.iterdescendants()]
            hits.append(el)
    # Prefer paragraph/heading level: walk up from spans to text:p / text:h
    para_tags = {f"{{{TEXT_NS}}}p", f"{{{TEXT_NS}}}h"}
    seen, results = set(), []
    for el in hits:
        p = el
        while p is not None and p.tag not in para_tags:
            p = p.getparent()
        target = p if p is not None else el
        if id(target) not in seen:
            seen.add(id(target))
            results.append(target)
    if not results:
        print("Text not found.")
        return
    for el in results:
        print(tree.getpath(el))
        print(f"    {short(odf_text(el).strip(), args.width)}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Find content at an XPath in an ODT file and show its context.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples", 1)[1] if "Examples" in __doc__ else None,
    )
    ap.add_argument("odt", help="path to the .odt (or .ods/.odp) file")
    ap.add_argument("xpath", nargs="?", help="XPath 1.0 expression, e.g. //text:p[3]")
    ap.add_argument("--part", default="content.xml",
                    help="XML part inside the archive (default: content.xml)")
    ap.add_argument("-C", "--context", type=int, default=3,
                    help="lines of XML to show before/after each match (default: 3)")
    ap.add_argument("-s", "--siblings", type=int, default=0,
                    help="also list N sibling elements either side, with their text")
    ap.add_argument("--text-only", action="store_true", help="skip the XML window")
    ap.add_argument("--full-text", action="store_true", help="don't truncate text")
    ap.add_argument("--max", type=int, default=50, help="max matches to show (0 = all)")
    ap.add_argument("--width", type=int, default=140, help="truncate long lines to this width")
    ap.add_argument("--ns", action="append", metavar="PREFIX=URI",
                    help="register an extra namespace prefix (repeatable)")
    ap.add_argument("--locate", metavar="TEXT",
                    help="print XPaths of paragraphs/headings containing TEXT")
    ap.add_argument("--case-sensitive", action="store_true", help="for --locate")
    ap.add_argument("--list-parts", action="store_true", help="list files in the archive")
    ap.add_argument("--list-ns", action="store_true", help="list usable namespace prefixes")
    args = ap.parse_args()

    if args.list_parts:
        with zipfile.ZipFile(args.odt) as z:
            for info in z.infolist():
                print(f"{info.file_size:>10}  {info.filename}")
        print()

    raw = read_part(args.odt, args.part)
    original, _pretty, lines, mapping = parse_trees(raw)
    ns = build_namespaces(original, args.ns)

    if args.list_ns:
        w = max(len(p) for p in ns)
        for p, u in sorted(ns.items()):
            print(f"{p:<{w}}  {u}")
        print()

    if args.locate:
        locate(original, args.locate, ns, args)
    elif args.xpath:
        run_xpath(original, args.xpath, ns, args, lines, mapping)
    elif not (args.list_parts or args.list_ns):
        ap.error("give an XPath, or use --locate / --list-parts / --list-ns")


if __name__ == "__main__":
    main()