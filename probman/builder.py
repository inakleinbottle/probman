import json
import shutil
import os
import base64
import logging
from pathlib import Path
from tempfile import TemporaryDirectory


from .sheets import Sheet
from .sheets import Problem
from .parser import SheetParser

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
        self.sheets = []
        self.parse_sheet_file(Path(sheetfile))
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
 
 
    def parse_sheet_file(self, path):
        logger.debug('Parsing sheet file')
        with SheetParser(path, self.incl) as parser:
            for sh in parser.parse():
                sh.problems = {self.db[i] : mk for i, mk in sh.problems}
                self.sheets.append(sh)
            #self.template = parser.template
            
        
