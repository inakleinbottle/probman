import logging
import re
from collections import namedtuple, defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

ProblemError = namedtuple('ProblemError', ('type', 'description', 'cat'))






class Checker:

    patterns = [
                r'\\includegraphics(?P<opt>\[.+\])?\{(?P<figure>.+?)\}',
                r'\\input\{(?P<input>.+?)\}',
               ]

    def __init__(self, problem_store):
        self.problem_store = problem_store
        self.errors = defaultdict(list)
        self.current_problem = None
        self.regex = re.compile('|'.join(self.patterns))

    def replace_in_text(self, str1, str2):
        text = self.current_problem.get_question()
        self.current_problem.update_question_text(text.replace(str1, str2))
        text = self.current_problem.get_solution()
        self.current_problem.update_solution_text(text.replace(str1, str2))

    def _attachment_check(self, type_, value):
        if not self.current_problem.has_attachment(value):
            current = self.current_problem
            # figure is missing, check why
            parts = value.split('/')
            if self.current_problem.has_attachment(parts[-1]):
                err = ProblemError(f'Missing {type_}',
                                   f'Problem {current.problem_id} '
                                   f'has attachment "{parts[-1]}", but the text'
                                   f' requires "{value}"',
                                   f'missing {type_}: needs rename {parts[-1]}')
                self.errors[self.current_problem].append(err)
                yield err
                self.replace_in_text(value, parts[-1])
            elif parts[0].startswith('\\'):
                err = ProblemError(f'Missing {type_}',
                                   f'Problem {current.problem_id} '
                                   f'requests figure "{value}", which contains '
                                   'an unexpanded TeX macro',
                                   f'missing {type_}: unexpanded macro '
                                   f'{parts[0]}')
                self.errors[self.current_problem].append(err)
                yield err
            else:
                err = ProblemError(f'Missing {type_}',
                                   f'Problem {current.problem_id} '
                                   f'requests figure "{value}", which is not '
                                   'found in the attachments for this problem',
                                   f'missing {type_}: file not found {value}')
                self.errors[self.current_problem].append(err)
                yield err

    def check_figure(self, value):
        yield from self._attachment_check('figure', value)

    def check_input(self, value):
        yield from self._attachment_check('input', value)

    def process_match(self, match):
        type_ = match.lastgroup
        value = match.group(type_)
        logger.debug(f'Found {type_} with value {value}')
        try:
            processor = getattr(self, f'check_{type_}')
            yield from processor(value)
        except AttributeError:
            raise # reraise for now

    def check_text(self, text):
        for match in self.regex.finditer(text):
            yield from self.process_match(match)

    def _file_not_found(self, type_):
        yield ProblemError(f'Missing {type_}',
                           f'Problem {self.current_problem.problem_id} '
                           f'is missing the {type_} file',
                           f'missing {type_}')
        getattr(self.current_problem, f'update_{type_}_text')('')
            
    def check_problem(self, problem):
        try:
            yield from self.check_text(problem.get_question())
        except FileNotFoundError:
            yield from self._file_not_found('question')
        try:
            yield from self.check_text(problem.get_solution())
        except FileNotFoundError:
            yield from self._file_not_found('solution')
        
    def process_problem(self, id_):
        problem = self.problem_store.get_problem(id_)
        self.current_problem = problem
        yield from self.check_problem(problem)
          
    def generator(self):
        process = self.process_problem
        problems = self.problem_store.list_problems()
        for id_ in problems:
            yield from process(id_)

    def __iter__(self):
        return self.generator()
        
            
                                
