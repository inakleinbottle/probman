import pkgutil
from pathlib import Path
from contextvars import ContextVar
from configparser import ConfigParser

MAIN_CONFIG = Path.home() / '.probman'
parser = ConfigParser()
parser.read_string(pkgutil.get_data('probman', 'data/config').decode())
GLOBALS = ContextVar('GLOBALS')
GLOBALS.set({'config' : parser})
