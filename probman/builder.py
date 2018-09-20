import json
import shutil
import os
import base64
import logging
from pathlib import Path
from tempfile import TemporaryDirectory


from .sheets import Sheet
from .sheets import Problem

logger = logging.getLogger(__name__)

def decode(data):
    return base64.b85decode(data.encode('ascii'))
 
def extract_figs(path, attachments):
    for attachment in attachments:
        fname, data = attachment
        with open(path / fname, 'wb') as f:
            f.write(decode(data))

def mark_sep(text):
    spl = text.split()
    if len(spl) == 1:
        return spl[0], None
    else:
        return spl[0], int(spl[1])

class Builder:
 
    def __init__(self, db, sheetfile, incl, template):
        logger.debug(f'Initialising builder\ndatabase={db!s}')
        self.incl = list(incl)
        self.db = {item[0] : Problem(*item) for item in json.load(db)}
        self.sheets = list(self.parse_sheet_file(sheetfile))
        logger.debug(f'Including files: {", ".join(self.incl)}')
        self.template = template
 
 
    def compile_all(self, dst='.'):
        cur = Path.cwd()
        with TemporaryDirectory() as tmpdir:
            dirpath = Path(tmpdir)
            logger.debug(f'Creating build directory {dirpath!s}')
            #os.mkdir(dirpath / 'figs')
            for i in self.incl:
                logger.debug(f'Copying {i} to {dirpath!s}')
                shutil.copy(str(cur / i), str(dirpath / i))
            for sheet in self.sheets:
                logger.debug(f'Compiling sheet {sheet.file_name}')
                sheet.create_question_file(dirpath, self.template)
                sheet.compile_only(dirpath, dst)
 
 
    def parse_sheet_file(self, fd):
        logger.debug('Parsing sheet file')
        is_toplevel = True
         
        glb_metadata = {}
 
        fname = None
        metadata = None
        problems = None
        mark_formatter=None
        formatters={}
         
        for line in fd:
            if line.startswith('#'):
                # skip comment lines
                continue
            elif not line.strip():
                # blank lines delimit the sheets
                if not is_toplevel:
                    if fname:
                        yield Sheet(fname, ftype, metadata,
                                    {self.db[i] : mk for i, mk in problems},
                                    formatters)
                    is_toplevel = True
                    fname = None
                    metadata = None
                    problems = None
                # is_toplevel reset on blank line
                continue
 
            if is_toplevel:
                if '=' in line:
                    key, value = line.split('=')
                    key = key.strip()
                    value = value.strip()
                    if key == 'include':
                        self.incl.append(value)
                    elif key == 'template':
                        with open(value, 'r') as f:
                            self.template = f.read()
                    elif key == 'mark':
                        macro = value
                        def mark_formatter(mk):
                            if mk is not None:
                                return f'\n{macro}{{{mk}}}'
                            else:
                                return ''
                        formatters['mark'] = mark_formatter
                    else:
                        glb_metadata[key] = value
                else:
                    fname, ftype = line.strip().split()
                    ftype = ftype if ftype else 'normal'
                    is_toplevel = False
                    metadata = {}
                    metadata.update(glb_metadata)
                    problems=[]
            else:
                k, v = line.strip().split('=')
                if k.strip() == 'problems':
                    problems.extend(map(mark_sep, v.strip().split(';')))
                else:
                    metadata[k.strip()] = v.strip()


        else:
            if fname:
                yield Sheet(fname, ftype, metadata,
                            {self.db[i] : mk for i, mk in problems},
                            formatters)
