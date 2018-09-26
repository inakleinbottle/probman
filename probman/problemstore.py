
import shutil
import logging
import re
from pathlib import Path
from string import Template
from tempfile import TemporaryDirectory
from configparser import ConfigParser
from contextlib import contextmanager

logger = logging.getLogger(__name__)

from .utils import extract_figs, encode, decode, tex_compile
from .sheets import Problem

def _ensure_created(path):
    path.mkdir(exist_ok=True)

class ProblemStore:

    def __init__(self):
        self.path = Path.cwd()
        self.config = None
        self.load_local_config()

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

    def load_local_config(self):
        config_path = self.path / '.prob' / 'config'
        if not config_path.exists():
            raise RuntimeError(f'Problem store not found in {self.path!s}')
        parser = ConfigParser()
        parser.read(str(config_path))
        self.config = parser

    def get_sheet_file(self):
        mks = self.path / '.prob' / 'sheets'
        return mks

    def get_config_file(self):
        return str(self.path / '.prob' / 'config')

    def get_template_file(self):
        return self.path / '.prob' / 'template'

    def get_template(self):
        return self.get_template_file().read_text()

    def read_sheets_file(self):
        from .parser import SheetParser
        logger.debug(f'Reading sheet file')
        with SheetParser(self.get_sheet_file()) as parser:
            for sheet in parser.parse():
                logger.debug(f'Found sheet {sheet.file_name}')
                sheet.problems = {Problem(prb,
                                          self.get_problem_text(prb),
                                          self.get_answer_text(prb),
                                          []) : mk
                                  for prb, mk in sheet.problems}
                yield sheet

    def get_attachments(self, id_):
        self.check_problem_exists(id_)
        path = self.get_problem_path(id_) / 'attach'
        if not path.exists():
            return []
        else:
            return [p for p in path.iterdir()]

    def copy_attachments(self, id_, dst):
        attachments = self.get_attachments(id_)
        for attach in attachments:
            logger.debug(f'Copying {attach} to {dst!s}')
            shutil.copy(attach, dst / attach.name)
            yield dst / attach.name

    def check_problem(self, problem_id):
        chk_path = self.get_problem_path(problem_id)
        return chk_path.is_dir()

    def check_problem_exists(self, id_):
        if not self.check_problem(id_):
            raise RuntimeError(f'Problem {id_} not found.')

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
            dst = self.path / (id_ + '.pdf')
            shutil.copy(pdf_file, dst)
        yield str(dst)
        # remove the preview file
        dst.unlink()

    def list_problems(self):
        return [d for d in self.path.iterdir() if d.is_dir()]

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


    def rm_problem(self, id_):
        if self.check_problem(id_):
            shutil.rmtree(self.get_problem_path(id_))

    def get_problem_path(self, id_):
        return self.path / 'problems' / id_

    def new_problem(self, id_, problem_text, answer_text, attachments):
        if self.check_problem(id_):
            raise ValueError(f'Problem {id_} already exists')

        dirpath = self.get_problem_path(id_)
        _ensure_created(dirpath)

        prb_path = dirpath / 'problem.tex'
        sol_path = dirpath / 'solution.tex'
        prb_path.write_text(problem_text)
        sol_path.write_text(answer_text)

        if attachments:
            attach_path  = dirpath / 'attach'
            _ensure_created(attach_path)
            for attach in attachments:
                self.attach_to_problem(id_, attach)

    def get_problem_text(self, id_):
        self.check_problem_exists(id_)
        return (self.get_problem_path(id_) / 'problem.tex').read_text()

    def get_answer_text(self, id_):
        self.check_problem_exists(id_)
        return (self.get_problem_path(id_) / 'solution.tex').read_text()

    def attach_to_problem(self, id_, attach):
        self.check_problem_exists(id_)
        src_path = Path(attach)
        dst_path = self.get_problem_path(id_) / 'attach' / src_path
        shutil.copy(src_path, dst_path)

    def get_problem(self, id_):
        self.check_problem_exists(id_)
        path = self.get_problem_path(id_)
        problem_path = path / 'problem.tex'
        answer_path = path / 'solution.tex'
        attach_path = path / 'attach'

        attachments = [(p.relative_to(attach_path),
                        encode(p.read_bytes()))
                       for p in attach_path.iterdir()]

        problem = Problem(id_,
                          problem_path.read_text(),
                          answer_path.read_text(),
                          attachments)
        return problem

    def get_all_problems(self):
        get_problem = self.get_problem
        return [get_problem(id_) for id_ in self.list_problems()]

    def update_problem_text(self, id_, text):
        self.check_problem_exists(id_)
        path = self.getProblem_path(id_) / 'problem.text'
        path.write_text(text)

    def update_answer_text(self, id_, text):
        self.check_problem_exists(id_)
        path = self.get_problem_path(id_) / 'solution.tex'
        path.write_text(text)

    def rm_attachment(self, id_, attachment):
        self.check_problem_exists(id_)
        path = self.get_problem_path(id_) / 'attach' / attachment
        if path.exists():
            path.unlink()

    def get_includes(self):
        return (self.path / '.prob' / 'include').glob('*')

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
