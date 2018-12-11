
import logging
import re
from .sheets import Sheet, Problem

LINERE = re.compile(r'((?P<sheet>\w+)(\s+(?P<sheet_type>\w+))?\s*|'
                    r'(?P<indent>\s+)?((?P<key>\w+)\s*=\s*)?(?P<value>.*))$')
PROBLEMRE = re.compile(r'(?P<problem_id>\w+)(\s+(?P<marks>\d+))?\s*$')

logger = logging.getLogger(__name__)

def default_mark_formatter(mark):
    return f'''\\par\\null\\hfill\\textbf{{[{str(mark) + " mark"
                                             if mark else " marks"}]}}'''

class SheetParser:

    def __init__(self, path, ext):
        self.path = path / ext
        self.problem_dir = path / 'problems'
        self.file = open(self.path, 'r')
        self.current = None
        self.global_metadata = dict()
        self.formatters = dict()
        self.last_key = None
        self.lineno = 0
        #self.include = []
        self.template = None

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.file.close()

    #def get_includes(self):
    #    return self.include

    def get_processor(self, key):
        self.last_key = key
        return getattr(self, f'do_{key}', lambda v: v)

    def process_kv(self, dest, key, value):
        processed = self.get_processor(key)(value)
        if processed:
            dest[key] = processed

    def update_kv(self, dest, key, value):
        processed = self.get_processor(key)(value)
        if processed and key in dest:
            dest[key] += processed

    def parse_global(self, key, value):
        if not key:
            # Error?
            pass
        else:
            self.process_kv(self.global_metadata, key, value)

    def parse_in_context(self, key, value):
        if not key and self.last_key:
            logger.debug(f'Passing {value} to be added to {key}')
            self.update_kv(self.current.metadata, self.last_key, value)
        elif not key:
            raise RuntimeError('Dangling data')
        else:
            logger.debug(f'Adding {value} to current metadata {key}')
            self.process_kv(self.current.metadata, key, value)

    def parse_problem(self, problem_text):
        match = PROBLEMRE.match(problem_text)
        mark_group = match.group('marks')
        mark = int(mark_group) if mark_group is not None else None
        id_ = match.group('problem_id')
        if id_ is None:
            raise SyntaxError(f'Invalid syntax in {problem_text}')
        self.current.problems.append((Problem(id_, self.problem_dir / id_), mark))

    def new_sheet(self, sheet_name, sheet_type):
        logger.debug(f'Creating new sheet with name {sheet_name}')
        metadata = dict()
        metadata.update(self.global_metadata)
        current = self.current
        self.current = Sheet(sheet_name, sheet_type, metadata, [])
        return current

    def parse_line(self, line):
        line = line.rstrip('\n')
        if line.startswith('#') or not line:
            return False
        match = LINERE.match(line)
        if match.group('indent'):
            return self.parse_in_context(match.group('key'),
                                         match.group('value'))
        elif match.group('sheet'):
            return self.new_sheet(match.group('sheet'),
                                  match.group('sheet_type'))
        else:
            return self.parse_global(match.group('key'),
                                     match.group('value'))


    def parse(self):
        for line in self.file:
            self.lineno += 1
            sheet = self.parse_line(line)
            if sheet:
                yield sheet
                sheet = None
        if self.current:
            yield self.current


    # Special keys
    def do_problems(self, value):
        '''Parse a problem list and generate the problem objects.'''
        if not self.current:
            raise RuntimeError('No current sheet')
        for problem in value.split(';'):
            problem = problem.strip()
            if problem:
                self.parse_problem(problem)

    def do_mark(self, marker):
        def mark_formatter(mark):
            return f'\n{marker}{{{mark}}}' if mark else ''
        self.formatters['mark'] = mark_formatter

    def do_template(self, value):
        with open(self.path.with_name(value), 'r') as f:
            self.template = f.read()

    #def do_include(self, value):
    #    self.include.append(str(self.path.with_name(value)))
