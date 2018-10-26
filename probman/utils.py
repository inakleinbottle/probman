
import base64
import logging
import re
import os
import shutil
from pathlib import Path
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from subprocess import run, PIPE

logger = logging.getLogger(__name__)

def compress(tree, outfile, algorithm):
    return shutil.make_archive(outfile,
                               algorithm,
                               root_dir=tree,
                               base_dir=tree,
                               logger=logger)

@contextmanager
def decompress(path, algorithm=None):
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        try:
            shutil.unpack_archive(path, extract_dir=tmp, format=algorithm)
            yield tmp
        except ValueError as e:
            yield None
            raise e

@contextmanager
def change_cwd(self, path):
    current = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(current)

def check_is_archive(path):
    rv = False
    ext = ['.zip', '.tar.gz', '.tar.xz', '.bz2']
    if any(path.endswith(e) for e in ext):
        rv = True
    return rv

def tex_compile(file, *, engine='pdflatex', runs=2):
    wd = file.parent
    target = file.name
    logger.info(f'Building {target} with {engine} in {wd}.')
    for _ in range(runs):
        ck = run([engine, '--interaction=nonstopmode', target], cwd=wd,
                 stdout=PIPE, stderr=PIPE)
        logger.debug(f'Build of {target} returned '
                       f'with code {ck.returncode}')
        if ck.returncode:
            outcome=False
            break
    else:
        outcome=True
    return outcome

def parse_for_figures(text):
    pat = r'\\includegraphics(?P<opt>\[.+\])?\{(?P<fig>.+)\}'
    return [m['fig'] for m in re.finditer(pat, text)]

def make_launcher(executable):
    from subprocess import Popen, PIPE
    def wrapper(*args):
        proc = Popen([executable, *args], stdout=PIPE, stderr=PIPE)
        proc.wait()
    return wrapper
        

