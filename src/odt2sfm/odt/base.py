from .. import logger


def get_node_doc_style(node, document):
    """Many nodes have a "Content" style defined in content.xml, but we're
    interested in "Document" styles defined in styles.xml. Content styles
    will have a parent style from Document styles."""
    style = node.style
    # Check if node's style is a Content style.
    content_style = None
    for family in ("paragraph", "text"):
        # Get style object, prioritizing paragraph style over text style.
        content_style = document.content.get_style(family, style)
        if content_style:
            break
    if content_style:
        # logger.info(f'Getting parent (document) style of "{node.style}"')
        doc_style = content_style.parent_style
        if doc_style:
            logger.info(
                f'Parent (document) style of content style "{node.style}" is "{doc_style}"'
            )
            style = doc_style
        else:
            logger.warning(f'Content style "{node.style}" has no parent style.')
    return style


def get_node_row(node):
    if node.parent.tag.startswith("table"):
        # Parent of node is Cell, whose parent is Row.
        return node.parent.parent


def get_node_table(node):
    if node.parent.tag.startswith("table"):
        # Parent of node is Cell, whose parent is Row, whose parent is Table.
        return get_node_row(node).parent


def get_node_table_pos(node):
    """Return (row, col) indexes for node's cell in given table."""

    table = get_node_table(node)
    row = get_node_row(node)
    col_ct = len([c for c in table.children if c.tag == "table:table-column"])
    table_children_elems = [c._xml_element for c in table.children]
    row_idx = table_children_elems.index(row._xml_element) - col_ct
    row_children_elems = [c._xml_element for c in row.children]
    col_idx = row_children_elems.index(node.parent._xml_element)
    return (row_idx, col_idx)


def node_has_paragraph_descendent_with_text(node):
    qnames = ("text:h", "text:p")

    def node_contains_paragraph_with_text(n):
        for c in n.children:
            # logger.debug(f"Checking node tag: {c.tag}")
            if c.tag in qnames and (c.text or c.tail):
                return True
            else:
                return node_contains_paragraph_with_text(c)

    return node_contains_paragraph_with_text(node)


def node_in_table(node):
    return node.parent.tag.startswith("table")
