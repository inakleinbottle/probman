
import shutil
from pathlib import Path


from .utils import extract_figs


def _ensure_created(path):
        path.mkdir(exists_ok=True)

class ProblemDirectory:

    def __init__(self, parent, topic_dirs=None):
        self.path = Path(parent) / 'sheets'
        _ensure_created(self.path)


    def check_problem(self, problem_id):
        chk_path = self.path / problem_id
        return chk_path.is_dir()

    def list_problems(self):
        return [d for d in self.path.iterdir() if d.is_dir()]


    def add_problem(self, problem):
        self.new_problem(problem.problem_id, problem.problem_text,
                         problem.answer_text, problem.attachments)

    def rm_problem(self, problem):
        if self.check_problem(problem.problem_id):
            shutil.rmtree(self.path / problem.problem_id)


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

            extract_figs(attach_path, attachments)
                
    

        
        
