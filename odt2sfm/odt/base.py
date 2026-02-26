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
        logging.info(f'Getting parent (document) style of "{node.style}"')
        doc_style = content_style.parent_style
        if doc_style:
            logging.debug(f'Parent style of "{node.style}" is "{doc_style}"')
            style = doc_style
    return style
