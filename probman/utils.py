
import base64
import logging
import re
from subprocess import run

logger = logging.getLogger(__name__)

def encode(data):
    return base64.b85encode(data).decode('ascii')

def decode(data):
    return base64.b85decode(data)

def extract_figs(path, attachments):
    for attachment in attachments:
        fname, data = attachment
        with open(path / fname, 'wb') as f:
            f.write(decode(data))

def tex_compile(file, *, engine='pdflatex', runs=2):
    wd = file.parent
    target = file.name
    logger.info(f'Building {target} with {engine}.')

    for _ in range(runs):
        ck = run([engine, target], cwd=wd, capture_output=True)
        logger.debug(f'Build of {target} returned'
                       f'with code {ck.returncode}')
        if ck.returncode:
            break

def parse_for_figures(text):
    pat = r'\\includegraphics(?P<opt>\[.+\])?\{(?P<fig>.+)\}'
    return [m['fig'] for m in re.finditer(pat, text)]
