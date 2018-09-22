
import shutil
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

logger = logging.getLogger(__name__)

from .utils import extract_figs, encode, decode
from .sheets import Problem

def _ensure_created(path):
    path.mkdir(exist_ok=True)

class ProblemDirectory:

    def __init__(self, parent, topic_dirs=None):
        self.path = Path(parent) / 'problems'
        _ensure_created(self.path)

    def check_problem(self, problem_id):
        chk_path = self.path / problem_id
        return chk_path.is_dir()

    def check_problem_exists(self, id_):
        if not self.check_problem(id_):
            raise RuntimeError(f'Problem {id_} not found.')

    def list_problems(self):
        return [d for d in self.path.iterdir() if d.is_dir()]

    def add_problem(self, problem):
        self.new_problem(problem.problem_id, problem.problem_text,
                         problem.answer_text, problem.attachments)

    def add_problems(self, problems):
        for problem in problems:
            self.add_problem(problem)

    def rm_problem(self, id_):
        if self.check_problem(id_):
            shutil.rmtree(self.path / id_)

    def new_problem(self, id_, problem_text, answer_text, attachments):
        if self.check_problem(id_):
            raise ValueError(f'Problem {id_} already exists')

        dirpath = self.path / id_
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
        return (self.path / id_ / 'problem.tex').read_text()

    def get_answer_text(self, id_):
        self.check_problem_exists(id_)
        return (self.path / id_ / 'solution.tex').read_text()

    def attach_to_problem(self, id_, attach):
        self.check_problem_exists(id_)
        src_path = Path(attach)
        dst_path = self.path / 'attach' / src_path
        shutil.copy(src_path, dst_path)

    def get_problem(self, id_):
        self.check_problem_exists(id_)
        path = self.path / id_
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
        path = self.path / id_ / 'problem.text'
        path.write_text(text)

    def update_answer_text(self, id_, text):
        self.check_problem_exists(id_)
        path = self.path / id_ / 'solution.tex'
        path.write_text(text)

    def rm_attachment(self, id_, attachment):
        self.check_problem_exists(id_)
        path = self.path / id_ / 'attach' / attachment
        if path.exists():
            path.unlink()
