from setuptools import setup



setup(name='probman',
      author='InAKleinBottle',
      email='admin@inakleinbottle.com',
      version='1.0.1',
      packages=['probman'],
      entry_points={
	     'console_scripts' : ['probman=probman.cli:main']
      },
      install_requires=['click', 'jinja2'],
      package_data = {'probman' : ['data/template',
                                   'data/sheets',
                                   'data/config'
                                  ]}
      )
