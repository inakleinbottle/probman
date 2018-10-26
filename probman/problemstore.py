
import shutil
import logging
import re
from fnmatch import fnmatch
from pathlib import Path
from functools import wraps
from string import Template
from tempfile import TemporaryDirectory
from configparser import ConfigParser
from contextlib import contextmanager

from .utils import tex_compile
from .sheets import Problem
from probman import MAIN_CONFIG, GLOBALS

logger = logging.getLogger(__name__)

def _ensure_exists(path):
    path.mkdir(exist_ok=True)

class ProblemStore:

    def __init__(self):
        self.path = Path.cwd()
        self.conf_path = self.path / '.prob'

        globs = GLOBALS.get()
        config = globs['config']
        config.read([MAIN_CONFIG, self.conf_path / 'config'])
        GLOBALS.set(globs)

        # Store variables
        for k, v in config['problemstore'].items():
            setattr(self, k, v)
        
        # Path variables
        for k, v in config['paths'].items():
            setattr(self, k, self.path / v)
        
    def must_exist(self):
        if not self.path.exists() or not self.conf_path.exists():
            raise RuntimeError(f'No problem store found in {self.path}')

    @classmethod
    def create_directory(cls, path):
        path = Path(path)
        if not path.exists():
            path.mkdir()
        else:
            if (path / '.prob').exists():
                # problemdir already exists in this directory
                raise RuntimeError('Problem store already exists '
                                   f'in {path!s}')
        # create local config
        logger.info(f'Initialising problem store in {path!s}')
        cls.create_local_config(path)

    @classmethod
    def create_local_config(cls, path):
        import pkgutil
        conf_path = path / '.prob'
        conf_path.mkdir()
        logger.debug('Creating local configuration.')
        template = pkgutil.get_data(__package__, 'data/template')
        config = pkgutil.get_data(__package__, 'data/config')
        sheets = pkgutil.get_data(__package__, 'data/sheets')

        for fname in ['sheets', 'template', 'config']:
            logger.debug(f'Writing local {fname} file in {conf_path!s}.')
            data = pkgutil.get_data(__package__, f'data/{fname}')
            (conf_path / fname).write_bytes(data)

    @classmethod
    def from_path(cls, path):
        from .utils import change_cwd
        with change_cwd(path):
            ps = cls()
        return ps

    def sheet_file(self, *, relative=None):
        path = self.conf_path / self.sheets
        if relative:
            path = path.relative_to(relative)
        return path

    def get_config_file(self):
        return self.conf_path / 'config'

    def get_sheet_file(self):
        return self.conf_path / self.sheets

    def get_template_file(self):
        return self.conf_path / self.template

    def get_mixed_dir(self):
        return self.get_sheets_dir() / 'mixed'

    def get_dir_for_mode(self, mode):
        if mode == 'questions':
            path = self.sheets_path
        elif mode == 'solutions':
            path = self.sheet_solution_path
        elif mode == 'mixed':
            path = self.sheet_mixed_path
        else:
            logger.warning(f'Mode {mode} not recognised '
                           'defaulting to questions')
            path = self.sheets_path
        _ensure_exists(path)

    def get_template(self, template):
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(self.conf_path)))
        return env.get_template(template)

    def get_sheets(self, pats):
        from .parser import SheetParser
        logger.debug(f'Reading sheet file, with patterns {pats}')
        with SheetParser(self.path,
                         self.sheet_file(relative=self.path)) as parser:
            sheets = [sheet for sheet in parser.parse()
                      if any(fnmatch(sheet.file_name, pat)
                             for pat in pats)]
        return sheets

    def list_problems(self):
        return [d.name for d in self.problems_path.iterdir() if d.is_dir()]
       
    def get_problem(self, id_, must_exist=True):
        problem_path = self.problems_path / id_
        if must_exist and not problem_path.exists():
            raise RuntimeError(f'Problem {id_} does not exist')
        return Problem(id_, problem_path)

    def rm_problem(self, id_):
        if self.check_problem(id_):
            shutil.rmtree(self.problems_path / id_)

    def new_problem(self, id_):
        problem = self.get_problem(id_, must_exist=False)
        problem.create()
        return problem
        
    def get_problem_text(self, id_):
        return self.get_problem(id_).get_question()

    def get_answer_text(self, id_):
        return self.get_problem(id_).get_solution()

    def attach_to_problem(self, id_, attach, overwrite=False):
        problem = self.get_problem(id_).add_attachment(Path(attach),
                                                       overwrite=overwrite)
   
    def get_all_problems(self):
        return [id_ for id_ in self.list_problems()]

    def update_problem_text(self, id_, text):
        self.get_problem(id_).update_question_text(text)

    def update_answer_text(self, id_, text):
        self.get_problem(id_).update_solution_text(text)

    def rm_attachment(self, id_, attachment):
        self.get_problem(id_).rm_attachment(Path(attachment).name)

    def get_includes(self):
        return (self.conf_path / self.include).glob('*')

    def write_and_compile(self, mode, sheets, output_to, template):
        if not sheets:
            raise ValueError('No sheets to build, aborting')
        
        use_template = self.get_template(template)
        with TemporaryDirectory() as tmp:
            dst = Path(tmp)
            
            includes = list(self.get_includes())
            for incl in includes:
                shutil.copy(incl, dst / incl.name)
        
            for sheet in sheets:
                try:
                    yield sheet.write_and_compile(mode,
                                                  dst,
                                                  output_to,
                                                  use_template)
                except RuntimeError as e:
                    logger.warning(e)
                    yield None
                
        logger.debug(f'Deleting temporary directory {dst}')
                
    def compile(self, mode, pats):
        sheets = self.get_sheets(pats)
        number = len(sheets)

        if mode == 'both':
            rounds = ['questions', 'solutions']
        else:
            rounds = [mode]
            
        yield number*len(rounds)
        for rnd in rounds:
            yield from self.write_and_compile(rnd, sheets,
                                              self.get_dir_for_mode(rnd),
                                              self.template)

    @contextmanager    
    def preview(self, id_):
        sheet = self.get_problem(id_).get_preview_sheet()
        compiler = self.write_and_compile('mixed', [sheet], None,
                                          self.preview_template)
        # advance to yield the number of sheets == 1
        pdf = next(compiler)
        if not pdf:
            raise RuntimeError(f'Problem {id_} preview build failed.')
        yield pdf
        logger.debug(f'Removing preview file {pdf.name}')
        

    ##### Merging stores

    def merge_other(self, other, overwrite=False):
        if isinstance(other, (str, Path)):
            other = ProblemStore.from_path(other)
        else:
            raise ValueError(f'Cannot merge, {other} is not a problem store')
        self_probs = set(self.list_problems())
        other_probs = set(other.list_problems())
        in_both = self_probs.intersect(other_probs)
        in_other = other_probs.difference(self_probs)

        for prb_id in in_other:
            other.get_problem(prb_id).clone(self.get_problem_dir())

        if overwrite:
            for prb_id in in_both:
                other.get_problem(prb_id).clone(self.get_problem_dir())

        

    
            
    
