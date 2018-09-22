
import logging
from pathlib import Path
import click

logger = logging.getLogger()
logging.basicConfig(level=logging.DEBUG)



@click.group()
def main():
    '''Problem manager main executable.'''
    pass

@main.command()
def init():
    '''Make a new problemstore in the current directory.'''
    from .problemstore import ProblemDirectory
    problem_dir = ProblemDirectory('.')

@main.command()
@click.option('-i', '--include', type=click.Path(), multiple=True,
              help=('Include a file in for compilation'))
#@click.option('-t', '--template', type=click.File())
@click.argument('problemdb', type=click.File('r'))
@click.argument('sheetfile', type=click.Path('r'))
@click.argument('template', type=click.File('r'))
def compile(problemdb, sheetfile, template, include):
    '''Compile the sheets specified in a sheet specification file.

    Args
    -----
        :problemdb: A database of problems to use to construct sheets.
        :sheetfile: The sheet specification file.
        :template: Template to use to build the sheets.
    '''
    from .builder import Builder
    from string import Template
    builder = Builder(problemdb, sheetfile, include,
                      Template(template.read()))
    builder.compile_all()

@main.command()
@click.option('-p', '--problem', type=str, default=None)
@click.option('-s', '--solution', type=str, default=None)
@click.argument('problemid')
def new(problemid, problem, solution):
    '''Create a new problem in the directory.'''
    from .problemstore import ProblemDirectory
    from .utils import parse_for_figures
    if not problem:
        problem_text = click.edit()
    else:
        problem_text = problem
    if not solution:
        answer_text = ''
        click.echo(f'Now solution text given for problem {problemid}.')
    else:
        answer_text = solution

    fig_list = parse_for_figures(problem_text)
    fig_list.extend(parse_for_figures(answer_text))

    attachments = []
    if fig_list:
        header = 'probman expects the following figure files\n'
        header += '\n'.join(f + '=' for f in fig_list)
        filelocs = click.edit(header)

        if not filelocs:
            for fig in fig_list:
                click.echo(f'Figure file "{fig}" not specified, '
                           'this will need to be added later')
        else:
            for line in filelocs.splitlines():
                if not '=' in line:
                    continue
                fig, loc = line.split('=', 1)
                if not loc:
                    click.echo(f'Figure file "{fig}" not specified, '
                               'this will need to be added later')
                attachments.append(loc)

    ProblemDirectory(Path.cwd()).new_problem(problemid,
                                             problem_text,
                                             answer_text,
                                             attachments)

@main.command()
@click.argument('problemid')
@click.argument('path', type=click.Path(exists=True, is_dir=False))
def attach(problemid, path):
    '''Attach a figure to a problem.'''
    from .problemstore import ProblemDirectory
    ProblemDirectory('.').attach_to_problem(problemid, path)


@main.command()
@click.argument('problemdb', type=click.File('w'))
@click.argument('path', type=click.Path(), nargs=-1)
def packdb(problemdb, path):
    '''Build a problem database from the problem directories.'''
    import json
    from .problemstore import ProblemDirectory
    problem_dir = ProblemDirectory(path)
    json.dump(problem_dir.get_all_problems(), f, indent=4)
