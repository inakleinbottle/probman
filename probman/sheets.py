import logging
import shutil
from pathlib import Path
from collections import namedtuple
from subprocess import run, PIPE


logger = logging.getLogger(__name__)

##Requirement = namedtuple('Requirement', ('type', 'data'))


class Problem:

    def __init__(self, problem_id, problem_text, answer_text, attachments):
        self.problem_id = problem_id
        self.problem_text = problem_text
        self.answer_text = answer_text
        self.attachments = attachments


    def write_problem_file(self, path):
        logger.write(f'Writing problem {self.problem_id} '
                     f'to {path!s}')
        p = path / self.problem_id
        p.mkdir(parents=True, exist_ok=True)
        p /= 'problem.tex'
        p.write_text(self.problem_text)

    def write_answer_file(self, path):
        logger.write(f'Writing solution {self.problem_id} '
                     f'to {path!s}')
        p = path / self.problem_id
        p.mkdir(parents=True, exist_ok=True)
        p/= 'solution.tex'
        p.write_text(self.answer_text)

    def write_files(self, path):
        self.write_problem_file(path)
        self.write_answer_file(path)




class Sheet:

    def __init__(self, file_name, sheet_type, metadata, problems, formatters):
        self.file_name = file_name
        self.sheet_type = sheet_type
        self.metadata = metadata
        self.problems = problems
        self.formatters = formatters
        if not 'mark' in self.formatters:
            self.formatters['mark'] = lambda x: ''
           
    def _format_problem(self, problem, mark):
        text = problem.problem_text
        if self.sheet_type and 'mark' in self.formatters:
            text += self.formatters['mark'](mark)
        return text

    def create_question_file(self, dst, template):
        logger.debug(f'Writing {self.file_name} into {dst!s}')
        with open(Path(dst) / (self.file_name + '.tex'), 'w') as f:
            prob_text = '\n\n\n\\item '.join(self._format_problem(prob, mk)
                                             for prob, mk in self.problems.items())
            f.write(template.substitute(problems=prob_text, **self.metadata))

    def create_answer_file(self, dst, template):
        with open(Path(dst) / (self.file_name + '.tex'), 'w') as f:
            ans_text = '\\item '.join(prob.answer_text
                                      for prob in self.problems)
            f.write(template.substitute(problems=ans_text, **self.metadata))

    def create_mixed_file(self, dst, template, sep='\n\n\textbf{solution}\n'):
        with open(Path(dst) / (self.file_name + '.tex'), 'w') as f:
            text = '\\item '.join(prob.problen_text
                                  + sep
                                  + prob.answer_text
                                  for prob in self.problems)
            f.write(template.substitute(problems=text, **self.metadata))

    def compile_only(self, build_dir, output_dir,
                     engine='pdflatex'):
        logger.debug(f'Building {self.file_name} in {build_dir} '
                     f'and outputting to {output_dir}')
        build_dir = Path(build_dir)
        output_dir = Path(output_dir)
        build_path = build_dir / (self.file_name + '.tex')

        if not build_path.exists():
            raise RuntimeError('File must be created in build location first')

        cmd = [engine, self.file_name + '.tex']
        ck = run(cmd, stdout=PIPE, stderr=PIPE, cwd=str(build_dir))
        if not ck.returncode:
            ck = run(cmd, stdout=PIPE, stderr=PIPE, cwd=str(build_dir))

        if not build_dir == output_dir:
            shutil.copy(build_dir / (self.file_name + '.pdf'),
                        output_dir / (self.file_name + '.pdf'))
        
                    
