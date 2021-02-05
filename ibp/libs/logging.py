import logging
import locale
import os

locale.setlocale(locale.LC_ALL, '')  # Use locale defined in user's environment

logging.basicConfig(level=logging.DEBUG, filename='/tmp/ibparser.log')
log = logging.getLogger(__name__)

if os.environ.get('DEBUG'):
    log.addHandler(logging.StreamHandler())
