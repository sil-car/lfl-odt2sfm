import logging

__version__ = "0.2.0-dev"
logging.basicConfig(
    format="%(levelname)s: [%(module)s:%(lineno)d:%(funcName)s]: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger()
