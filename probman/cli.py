
import logging

from functools import wraps

import click

from .problemstore import ProblemStore

logger = logging.getLogger()
logging.basicConfig(level=logging.WARNING)


pass_prbd = click.make_pass_decorator(ProblemStore,
                                      ensure=True)


def error_handling(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            raise
            logger.error(e)
            raise click.Abort()
    return wrapper


@click.group()
@click.option('-v', '--verbose', is_flag=True)
def main(verbose):
    '''Problem manager main executable.'''
    if verbose:
        logger.setLevel(logging.DEBUG)

@main.command()
@click.argument('path', default='.', required=False,
                type=click.Path())
@error_handling
def init(path):
    '''Make a new problemstore in the current directory.'''
    ProblemStore.create_directory(path)

# @main.command()
# @click.option('-i', '--include')
# @pass_prbd
# def compile(prbd, include):
#     """Compile all sheets into the directory."""
#     pass

@main.command()
@click.option('-i', '--include', type=click.Path(), multiple=True,
              help=('Include a file in for compilation'))
#@click.option('-t', '--template', type=click.File())
#@click.argument('problemdb', type=click.File('r'))
#@click.argument('sheetfile', type=click.Path(exists=True))
#@click.argument('template', type=click.File('r'))
@pass_prbd
@error_handling
def compile(prbd, include):
    '''Compile the sheets specified in a sheet specification file.

    Args
    -----
        :problemdb: A database of problems to use to construct sheets.
        :sheetfile: The sheet specification file.
        :template: Template to use to build the sheets.
    '''
    #from .builder import Builder
    #from string import Template
    #builder = Builder(problemdb, sheetfile, include,
    #                  Template(template.read()))
    #builder.compile_all()
    prbd.compile_all_sheets(include)

@main.command()
@click.option('-p', '--problem', type=str, default=None)
@click.option('-s', '--solution', type=str, default=None)
@click.argument('problemid')
@pass_prbd
@error_handling
def new(prbd, problemid, problem, solution):
    '''Create a new problem in the directory.'''
    from .utils import parse_for_figures
    if not problem:
        problem_text = click.edit()
    else:
        problem_text = problem
    if not solution:
        answer_text = ''
        logger.warning(f'No solution text given for problem {problemid}.')
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

    prbd.new_problem(problemid,
                     problem_text,
                     answer_text,
                     attachments)

@main.command()
@click.argument('problemid')
@click.argument('path', type=click.Path(exists=True))
@pass_prbd
@error_handling
def attach(prbd, problemid, path):
    '''Attach a figure to a problem.'''
    prbd.attach_to_problem(problemid, path)


def edit_file(ctx, param, value):
    prbd = ProblemStore()
    if ctx.command.name == 'sheets':
        click.edit(filename=prbd.get_sheet_file())
    elif ctx.command.name == 'config':
        click.edit(filename=prbd.get_config_file())
    elif ctx.command.name == 'template':
        click.edit(filename=prbd.get_template_file())


@main.command()
@click.option('-e', '--edit', is_flag=True, is_eager=True,
              callback=edit_file)
@click.argument('sheet', required=False, default=None, nargs=-1)
@error_handling
def sheets(edit, sheet):
    """View or edit sheets."""
    if not sheet:
        # view or edit global sheets
        pass

@main.command()
@click.option('-e', '--edit', is_flag=True, is_eager=True,
              callback=edit_file)
@error_handling
def config(edit):
    """Edit directory config."""
    pass

@main.command()
@click.option('-e', '--edit', is_flag=True, is_eager=True,
              callback=edit_file)
@error_handling
def template(edit):
    """Edit the template file."""
    pass

@main.command()
@click.argument('problem')
@pass_prbd
@error_handling
def preview(prbd, problem):
    """Build and preview a problem."""
    with prbd.preview_problem(problem) as pdf:
        click.launch(pdf, wait=True)

@main.command()
@click.argument('out', type=click.File('w'))
@pass_prbd
@error_handling
def packdb(prbd, out):
    '''Build a problem database from the problem store.'''
    import json

    json.dump(prbd.get_all_problems(), out, indent=4)


@main.command()
@click.argument('file', type=click.File('r'))
@pass_prbd
@error_handling
def unpackdb(prbd, file):
    """Unpack a problem database to problem store."""
    prbd.unpack_db(file)
