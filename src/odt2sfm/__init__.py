import logging

__version__ = "0.1.0"
logging.basicConfig(
    format="%(levelname)s: [%(module)s:%(lineno)d:%(funcName)s]: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger()
