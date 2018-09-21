

import re
from sheets import Sheet

LINERE = re.compile(r'((?P<sheet>\w+)(\s+(?P<sheet_type>\w+))?|'
                    r'(?P<indent>\s+)?((?P<key>\w+)\s*=\s*)?(?P<value>.+))$')
PROBLEMRE = re.compile(r'(?P<problem_id>\w+)(\s+(?P<marks>\d+))?\s*$')

def default_mark_formatter(mark):
    return f'''\\par\\null\\hfill\\textbf{{[{str(mark) + "mark"
                                             if mark else "marks"}]}}'''

class SheetParser:
    
    def __init__(self, path, include):
        self.path = path
        self.file = open(path, 'r')
        self.current = None
        self.global_metadata = dict()
        self.formatters = dict()
        self.last_key = None
        self.lineno = 0
        self.include = include
        self.template = None
        
    def __enter__(self):
        return self
        
    def __exit__(self, *args, **kwargs):
        self.file.close()
        
    def get_processor(self, key):
        self.last_key = key
        return getattr(self, f'do_{key}', lambda v: v)
    
    def process_kv(self, dest, key, value):
        processed = self.get_processor(key)(value)
        if processed and not key in dest:
            dest[key] = processed
        elif processed and key in dest:
            dest[key] += processed
                
    def parse_global(self, key, value):
        if not key:
            # Error?
            pass
        else:
            self.process_kv(self.global_metadata, key, value)

    def parse_in_context(self, key, value):
        if not key and self.last_key:
            self.process_kv(self.current.metadata, self.last_key, value)
        elif not key:
            raise RuntimeError('Dangling data')
        else:
            self.process_kv(self.current.metadata, key, value)
      
    def parse_problem(self, problem_text):
        match = PROBLEMRE.match(problem_text)
        mark = int(match.group('marks')) if match.group('marks') else 0
        self.current.problems.append((match.group('problem_id'),
                                      mark))
    
    def new_sheet(self, sheet_name, sheet_type):
        metadata = dict()
        metadata.update(self.global_metadata)
        formatters = dict()
        formatters.update(self.formatters)
        if sheet_type and not 'mark' in formatters:
            formatters['mark'] = default_mark_formatter
        current = self.current
        self.current = Sheet(sheet_name, sheet_type, metadata, [], formatters)
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
            
    def do_marks(self, marker):
        def mark_formatter(mark):
            return f'\n{marker}{{{mark}}}' if mark else ''
        self.formatters['mark'] = mark_formatter

    def do_template(self, value):
        with open(self.path / value, 'r') as f:
            self.template = f.read()

    def do_include(self, value):
        self.include.append(self.path / value)

    
            
        
