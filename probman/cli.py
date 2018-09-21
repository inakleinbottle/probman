
import logging

import click

logger = logging.getLogger()
logging.basicConfig(level=logging.DEBUG)



@click.group()
def main():
    '''Problem manager main executable.'''
    pass



    
@main.command()
@click.option('-i', '--include', type=click.Path(), multiple=True,
              help=('Include a file in for compilation'))
#@click.option('-t', '--template', type=click.File())
@click.argument('problemdb', type=click.File('r'))
@click.argument('sheetfile', type=click.Path('r'))
@click.argument('template', type=click.File('r'))
def compile(problemdb, sheetfile, template, include):
    '''Compile the sheets specified in a sheet specification file.

    Args:
        problemdb: A database of problems to use to construct sheets.
        sheetfile: The sheet specification file.
        template: Template to use to build the sheets.
    '''
    from .builder import Builder
    from string import Template
    builder = Builder(problemdb, sheetfile, include, 
                      Template(template.read()))
    builder.compile_all()
    



@main.command()
@click.argument('problemdb', type=click.File('r'))
@click.argument('path', type=click.Path(), nargs=-1)
def builddb(problemdb, path):
    '''Build a problem database from the problem directories.'''
    pass
