import logging
import shutil
from pathlib import Path
from functools import partialmethod
from collections import namedtuple
from subprocess import run, PIPE

from .utils import tex_compile


logger = logging.getLogger(__name__)

##Requirement = namedtuple('Requirement', ('type', 'data'))


class Problem:

    def __init__(self, problem_id, path):
        self.problem_id = problem_id
        self.path = path
        self.question_path = self.path / 'problem.tex'
        self.solution_path = self.path / 'solution.tex'
        self.attach_path = self.path / 'attach'
    
    def exists(self):
        return self.path.exists()

    def create(self):
        if self.exists():
            raise RuntimeError(f'Problem {self.problem_id} aleady exists')
        self.path.mkdir()
        self.question_path.touch()
        self.solution_path.touch()
        
    def get_question(self):
        return self.question_path.read_text()

    def get_solution(self):
        return self.solution_path.read_text()

    def copy_attachments_to(self, dst):
        for attach in self.attach_path.glob('*'):
            logger.debug(f'Copying {attach.name} to {dst}')
            shutil.copy(attach, dst / attach.name)

    def update_question_text(self, text):
        self.question_path.write_text(text)

    def update_solution_text(self, text):
        self.solution_path.write_text(text)
        
    def add_attachment(self, attachment, overwrite=False):
        self.attach_path.mkdir(exist_ok=True)
        new_path = self.attach_path / attachment.name
        if new_path.exists() and not overwrite:
            raise RuntimeError(f'Cannot add {attachment!s} to '
                               f'{self.problem_id}, '
                               'file already exists')
        shutil.copy(attachment, new_path)
    
    def add_attachments(self, attachments, overwrite=False):
        for attach in attachments:
            self.add_attachment(self, attach, overwrite=overwrite)

    def rm_attachment(self, name):
        for attach in self.attach_path.glob(name + '*'):
            logger.info(f'Removing {attach!s}')
            attach.unlink()
    
    def has_attachment(self, name):
        return any(self.attach_path.glob(name + '*'))

    def list_attachments(self):
        return list(self.attach_path.iterdir())

    def get_preview_sheet(self):
        return Sheet('preview', None, {}, [(self, None)])
    
    def clone(self, path):
        shutil.copytree(self.path, path)









class Sheet:

    def __init__(self, file_name, sheet_type, metadata, problems):
        self.file_name = file_name
        self.sheet_type = sheet_type
        self.metadata = metadata
        self.problems = problems
        
    def _write_file(self, dst, template, include_problems, include_solutions):
        logger.debug(f'Writing {dst!s}')
        text = template.render(problems=self.problems,
                               include_problems=include_problems,
                               include_solutions=include_solutions,
                               **self.metadata)
        dst.write_text(text)    
 
    def create_question_file(self, dst, template):
        self._write_file(dst, template, True, False)

    def create_answer_file(self, dst, template):
        self._write_file(dst, template, False, True)

    def create_mixed_file(self, dst, template):
        self._write_file(dst, template, True, True)

    def compile_only(self, target, **kwargs):
        logger.debug(f'Building {target}')
        if not target.exists():
            raise RuntimeError('File must be created in build location first')
        return tex_compile(target, **kwargs)


    def write_and_compile(self, mode, build_dir, out_dir, template):
        target = build_dir / (self.file_name + '.tex')
        built = build_dir / (self.file_name + '.pdf')
        if out_dir is None:
            out_dir = build_dir
        final = out_dir / (self.file_name + '.pdf')

        if mode == 'questions':
            self.create_question_file(target, template)
        elif mode == 'solutions':
            self.create_answer_file(target, template)
        elif mode == 'mixed':
            self.create_mixed_file(target, template)
        else:
            raise NotImplementedError()
        
        for prob, _ in self.problems:
            prob.copy_attachments_to(build_dir)

        if not self.compile_only(target):
            raise RuntimeError(f'Build failed for {target}')

        if not build_dir == out_dir:
            logger.debug(f'Moving {built} to {out_dir}')
            shutil.copy(built, final)
        return final



        
