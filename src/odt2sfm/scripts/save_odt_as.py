import sys

from odfdo import Document

d = Document(sys.argv[1])
d.save(sys.argv[2])
