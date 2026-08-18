import re

RE_SFM_TYPE = re.compile(r"(?<=\\)[a-z]+(?=0-9)*")
SFM_SPAN_TYPES_NO_END_MARKER = (
    # see: https://github.com/ubsicap/usfm/blob/master/sty/usfm.sty
    "v",  # verse
    "th",  # table column heading
    "tc",  # table column text
    "thc",  # table column heading centered
    "tcc",  # table column text centered
    "thr",  # table column heading right
    "tcr",  # table column text right
)


def get_sfm_type(sfm):
    m = RE_SFM_TYPE.search(sfm)
    if m:
        return m[0]
