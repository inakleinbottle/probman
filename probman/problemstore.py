
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

from .utils import extract_figs, encode, decode, tex_compile
from .sheets import Problem
from probman import MAIN_CONFIG

logger = logging.getLogger(__name__)

def _ensure_exists(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        path = func(*args, **kwargs)
        path.mkdir(exist_ok=True)
        return path
    return wrapper

class ProblemStore:

    def __init__(self):
        self.path = Path.cwd()
        self.conf_path = self.path / '.prob'
        self.config = None
        self.runtime = {}
        #self.load_local_config()
        
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

    def update_config(self, **kwargs):
        self.runtime.update(kwargs)

    def get_from_runtime(self, key):
        logger.debug(f'Getting {key} from config')
        return self.runtime.get(key, None)

    def get_sheet_file(self):
        return self.conf_path / 'sheets'

    def get_config_file(self):
        return self.conf_path / 'config'

    def get_template_file(self):
        return self.conf_path / 'template'
    
    @_ensure_exists
    def get_problems_dir(self):
        return self.path / 'problems'

    @_ensure_exists
    def get_sheets_dir(self):
        return self.path / 'sheets'

    @_ensure_exists
    def get_solutions_dir(self):
        return self.get_sheets_dir() / 'solutions'

    @_ensure_exists
    def get_mixed_dir(self):
        return self.get_sheets_dir() / 'mixed'

    def get_dir_for_mode(self, mode):
        if mode == 'questions':
            return self.get_sheets_dir()
        elif mode == 'solutions':
            return self.get_solutions_dir()
        elif mode == 'mixed':
            return self.get_mixed_dir()
        else:
            logger.warning(f'Mode {mode} not recognised '
                           'defaulting to questions')
            return self.get_sheets_dir()

    def load_local_config(self):
        parser = ConfigParser()
        parser.read([MAIN_CONFIG, self.get_config_file()])
        self.config = parser

    def get_from_config(self, *keys):
        if not self.config:
            self.load_local_config()
        level=self.config
        for key in keys:
            level = level[key]
        return level

    def get_template(self):
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(self.path / '.prob')))
        return env.get_template('template')

    def get_sheets(self, pat):
        from .parser import SheetParser
        logger.debug(f'Reading sheet file, with patter {pat}')
        with SheetParser(self.path,
                         self.get_sheet_file().relative_to(self.path)) as parser:
            sheets = [sheet for sheet in parser.parse()
                      if fnmatch(sheet.file_name, pat)]
        return sheets

    def list_problems(self):
        return [d.name for d in self.get_problems_dir().iterdir() if d.is_dir()]
       
    def get_problem(self, id_, must_exist=True):
        problem_path = self.get_problems_dir() / id_
        if must_exist and not problem_path.exists():
            raise RuntimeError(f'Problem {id_} does not exist')
        return Problem(id_, problem_path)

    def rm_problem(self, id_):
        if self.check_problem(id_):
            shutil.rmtree(self.get_problem_path(id_))

    def new_problem(self, id_, problem_text, answer_text, attachments,
                    must_be_new=True):
        problem = self.get_problem(id_, must_exist=False)
        if must_be_new and problem.exists():
            raise RuntimeError(f'Cannot create problem {id_}, '
                               'problem already exists')
        problem.update_question_text(problem_text)
        problem.update_answer_text(answer_text)
        problem.add_attachments(Path(att) for att in attachments)
        
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
        return (self.path / '.prob' / 'include').glob('*')

    def write_and_compile(self, mode, sheets, output_to):
        if not sheets:
            raise ValueError('No sheets to build, aborting')
        
        template = self.get_template()
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
                                                  template)
                except RuntimeError as e:
                    logger.warning(e)
                
        logger.debug(f'Deleting temporary directory {dst}')
                
    def compile(self, mode, pat='*'):
        sheets = self.get_sheets(pat)
        number = len(sheets)
        round_one = mode
        round_two = None
        if mode == 'both':
            round_one = 'questions'
            round_two = 'solutions'
            number *=2
            mode = 'questions'
            
        yield number
        yield from self.write_and_compile(mode, sheets,
                                          self.get_dir_for_mode(round_one))
        if round_two:
            yield from self.write_and_compile(round_two,
                                              sheets,
                                              self.get_dir_for_mode(round_two))
            
    
    @contextmanager    
    def preview(self, id_):
        sheet = self.get_problem(id_).get_preview_sheet()
        compiler = self.write_and_compile('mixed', [sheet], None)
        # advance to yield the number of sheets == 1
        pdf = next(compiler)
        yield pdf
        logger.debug(f'Removing preview file {pdf.name}')
        pdf.unlink()
        

    
            
    #### DEPRECATED ####
    
    
    
    def check_problem(self, problem_id):
        chk_path = self.get_problem_path(problem_id)
        return chk_path.is_dir()

    def check_problem_exists(self, id_):
        if not self.check_problem(id_):
            raise RuntimeError(f'Problem {id_} not found.')
    
    def compile_all_sheets(self, include_extra):

        sheets = list(self.read_sheets_file())
        if not sheets:
            raise RuntimeError('No sheet specifications found')

        include = list(self.get_includes())
        logger.debug(f'Including {", ".join(map(str, include))}')

        with TemporaryDirectory() as tmp:
            logger.debug(f'Building all sheets in {tmp}.')
            tmp = Path(tmp)
            output_dir = self.path / 'sheets'
            _ensure_created(output_dir)

            for inc in include:
                shutil.copy(inc, tmp / inc.name)

            template = Template(self.get_template())

            for sheet in sheets:
                logger.debug(f'Preparing to build {sheet.file_name}')

                to_remove = []
                for prb in sheet.problems:
                    to_remove.extend(self.copy_attachments(prb.problem_id, tmp))

                sheet.create_question_file(tmp, template)

                tex_compile(tmp / (sheet.file_name + '.tex'))

                pdf_path = tmp / (sheet.file_name + '.pdf')

                if not pdf_path.exists():
                    logger.error(f'Compilation of sheet {sheet.file_name} '
                                 'failed.')
                else:
                    logger.debug(f'Copying output to {output_dir!s}.')

                    shutil.copy(pdf_path, output_dir / pdf_path.name)

                # cleanup
                logger.debug('Cleaning up.')
                for rem in to_remove:
                    rem.unlink()
                    
    @contextmanager
    def preview_problem(self, id_):
        self.check_problem_exists(id_)
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            tex_file = tmp / 'build.tex'
            text = (self.get_problem_text(id_)
                    + '\n\n\hrule\n\\textbf{Solution}\n'
                    + self.get_answer_text(id_))
            template = self.get_template()
            fields = re.findall(r'\$(\w+)', template)
            repl = {field : field for field in fields
                    if not field == 'problems'}
            repl['problems'] = text
            tex_file.write_text(Template(template).substitute(repl))
            self.copy_attachments(id_, tmp)

            tex_compile(tex_file)
            pdf_file = tmp / 'build.pdf'
            if not pdf_file.exists():
                raise RuntimeError('Compile failed')
            #dst = self.path / (id_ + '.pdf')
            #shutil.copy(pdf_file, dst)
            yield str(pdf_file)
            # remove the preview file
            #pdf_file.unlink()   
            
    def add_problem(self, problem):
        logger.debug(f'Writing problem {problem.problem_id} to store')
        self.new_problem(problem.problem_id, problem.problem_text,
                         problem.answer_text, [])
        path = self.get_problem_path(problem.problem_id) / 'attach'
        path.mkdir()
        for fname, data in problem.attachments:
            logger.debug(f'Unpacking {fname}')
            (path / Path(fname).name).write_bytes(decode(data))

    def add_problems(self, problems):
        for problem in problems:
            if self.check_problem(problem.problem_id):
                continue
            self.add_problem(problem)

    def unpack_db(self, fd):
        import json
        self.add_problems(map(lambda j: Problem(*j), json.load(fd)))
