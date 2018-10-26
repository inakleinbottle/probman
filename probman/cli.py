
import logging
import os
import pkgutil
from functools import wraps
from pathlib import Path
from configparser import ConfigParser

import click

from .problemstore import ProblemStore
from .utils import make_launcher
from probman import MAIN_CONFIG, GLOBALS

logger = logging.getLogger()
logging.basicConfig(level=logging.WARNING)

CONTEXT_SETTINGS = dict(auto_envvar_prefix='PROBMAN')

pass_prbd = click.make_pass_decorator(ProblemStore)

def error_handling(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error(e)
            raise click.Abort()
    return wrapper

@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('-v', '--verbose', is_flag=True, envvar='VERBOSE')
@click.pass_context
def main(ctx, verbose):
    '''Problem manager main executable.'''
    ctx.obj = ProblemStore()
    if verbose:
        logger.setLevel(logging.DEBUG)
    

@main.command()
@click.argument('path', default='.', required=False,
                type=click.Path())
@error_handling
def init(path):
    '''Make a new problemstore in the current directory.'''
    ProblemStore.create_directory(path)

@main.command()
@click.option('-m', '--mode',
              type=click.Choice(('questions', 'solutions', 'mixed', 'both')),
              default='questions')
@click.argument('sheets', required=False, nargs=-1)
@pass_prbd
@error_handling
def compile(prbd, mode, sheets):
    '''Compile the sheets specified in a sheet specification file.

    Args
    -----
        
    '''
    if not sheets:
        sheets = ('*',)
    prbd.must_exist()
    compiler = prbd.compile(mode, sheets)
    length = next(compiler)
    click.echo('Building sheets')
    
    with click.progressbar(compiler, length=length) as bar:
        for _ in bar:
            pass

@main.command()
@click.option('-p', '--problem', type=str, default=None)
@click.option('-s', '--solution', type=str, default=None)
@click.argument('problemid')
@pass_prbd
@error_handling
def new(prbd, problemid, problem, solution):
    '''Create a new problem in the directory.'''
    prbd.must_exist()

    blank_problem = prbd.new_problem(problemid)
    
    from .utils import parse_for_figures
    if not problem:
        click.edit(blank_problem.question_path)
    else:
        blank_problem.update_question_text(problem)
    if solution:
        blank_problem.update_solution_text(solution)
    
@main.command()
@click.argument('problemid')
@click.argument('path', type=click.Path(exists=True))
@pass_prbd
@error_handling
def attach(prbd, problemid, path):
    '''Attach a figure to a problem.'''
    prbd.must_exist()
    prbd.attach_to_problem(problemid, path)

@main.command()
@click.option('-e', '--edit', is_flag=True
              )
@click.argument('sheet', required=False, default=None, nargs=-1)
@pass_prbd
@error_handling
def sheets(prbd, edit, sheet):
    """View or edit sheets."""
    prbd.must_exist()
    if edit:
        click.edit(filename=prbd.get_sheet_file())
    else:
        if not sheet:
            # view or edit global sheets
            sheets = prbd.get_sheets('*')
            w, h = click.get_terminal_size()
            click.echo('{:<15}{:<11}{:<14}{}'.format('Sheet name', 
                                                     'Sheet type', 
                                                     'No. questions', 
                                                     'Questions'))
            for sheet in sheets:
                click.echo(f'{sheet.file_name:15}'
                           + f'{sheet.sheet_type if sheet.sheet_type else "":11}'
                           + f'{len(sheet.problems):13} '
                           + f'''{", ".join(p.problem_id
                                  for p, _ in sheet.problems)}''')

@main.command()
@click.option('-e', '--edit', is_flag=True,
              help='Open the specified problem/solution for editing')
@click.option('-s', '--solution', is_flag=True,
              help='Switch to solution mode')
@click.argument('problem', required=False, default=None)
@pass_prbd
@error_handling
def problem(prbd, edit, solution, problem):
    """Get or edit information about a problem."""
    prbd.must_exist()
    if not problem:
        click.echo("\n".join(prbd.list_problems()))
    else:
        problem = prbd.get_problem(problem)
        if edit and not solution:
            click.edit(filename=problem.question_path)
        elif edit and solution:
            click.edit(filename=problem.solution_path)
        elif not edit and solution:
            click.echo_via_pager(problem.get_solution())
        else:
            click.echo_via_pager(problem.get_question())

@main.command()
@click.option('-e', '--edit', is_flag=True
              )
@click.option('--write-main-config', is_flag=True)
@pass_prbd
@error_handling
def config(prbd, edit, write_main_config):
    """Edit directory config."""
    prbd.must_exist()
    if edit:
        click.edit(filename=prbd.get_config_file())
    if write_main_config:
        import pkgutil
        conf = MAIN_CONFIG
        conf.write_bytes(pkgutil.get_data(__package__,'data/config'))
        click.echo(f'Writing main config file to {conf!s}')

@main.command()
@click.option('-e', '--edit', is_flag=True)
@pass_prbd
@error_handling
def template(prbd, edit):
    """Edit the template file."""
    prbd.must_exist()
    if edit:
        click.edit(filename=prbd.get_template_file())

@main.command()
@click.argument('problem')
@pass_prbd
@error_handling
def preview(prbd, problem):
    """Build and preview a problem."""
    prbd.must_exist()
    try:
        viewer = prbd.get_from_config('system', 'pdfviewer')
        logger.debug(f'Using viewer {viewer} specified in config')
        launcher = make_launcher(viewer)
    except KeyError:
        viewer=None
    with prbd.preview(problem) as pdf:
        if viewer:
            launcher(str(pdf))
        else:
            click.launch(str(pdf), wait=True)
            click.pause()

@main.command()
@pass_prbd
def check(prbd):
    """Check all problems for errors.
    """
    prbd.must_exist()
    from .checker import Checker
    for err in Checker(prbd):
        click.echo(err.description)

@main.command()
@pass_prbd
def open(prbd):
    """Open the problem store directory."""
    prbd.must_exist()
    click.launch(str(prbd.path))

@main.command()
@click.option('-o', '--overwrite', is_flag=True)
@click.argument('path', type=click.Path())
@pass_prbd
@error_handling
def merge(prbd, overwrite, path):
    """Merge problems from another store or archive."""
    from .utils import check_is_archive
    if check_is_archive(path):
        from .utils import decompress
        with decompress(path) as store:
            prbd.merge_other(store, overwrite=overwrite)
    else:
        prbd.merge_other(path, overwrite=overwrite)
        
@main.command()
@click.option('-m', '--mode', type=click.Choice(('targz', 'tarxz', 'zip')))
@click.option('-o', '--output', type=click.Path(), default=None)
@pass_prbd
@error_handling
def archive(prbd, mode, output):
    """Compress the store into an archive."""
    from .utils import compress
    if not output:
        output = prbd.path / 'archive'
    arch = compress(prbd.get_problem_dir(), output, mode)
    click.echo(f'Archive created in {arch}')

