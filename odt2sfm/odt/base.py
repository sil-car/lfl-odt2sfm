import logging


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
        # logging.info(f'Getting parent (document) style of "{node.style}"')
        doc_style = content_style.parent_style
        if doc_style:
            logging.info(
                f'Parent (document) style of content style "{node.style}" is "{doc_style}"'
            )
            style = doc_style
        else:
            logging.warning(f'Content style "{node.style}" has no parent style.')
    return style


def node_has_paragraph_descendent_with_text(node):
    qnames = ("text:h", "text:p")

    def node_contains_paragraph_with_text(n):
        for c in n.children:
            # logging.debug(f"Checking node tag: {c.tag}")
            if c.tag in qnames and (c.text or c.tail):
                return True
            else:
                return node_contains_paragraph_with_text(c)

    return node_contains_paragraph_with_text(node)
