from setuptools import setup



setup(name='probman',
      author='InAKleinBottle',
      email='admin@inakleinbottle.com',
      version='0.1.0',
      packages=['probman'],
      entry_points={
	'console_scripts' : ['probman=probman.cli:main']
      },
      install_requires=['click']
      )

