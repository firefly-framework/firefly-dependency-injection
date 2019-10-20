import os
from configparser import ConfigParser

import setuptools
from setuptools.command.develop import develop
from setuptools.command.install import install

with open("README.md", "r") as fh:
    long_description = fh.read()


def setup_project_structure():
    current_dir = os.getcwd()
    while not os.path.exists('firefly.ini'):
        if os.path.realpath(os.getcwd()) == os.path.realpath('..'):
            break
        os.chdir('..')

    if not os.path.exists('firefly.ini'):
        os.chdir(current_dir)
        return

    config = ConfigParser()
    config.read('firefly.ini')
    for provider in config.sections():
        if config.has_option(provider, 'is_extension'):
            continue

        di_dir = os.path.join(provider, 'application')
        if not os.path.exists(di_dir):
            os.makedirs(di_dir)
        if not os.path.exists(os.path.join(di_dir, 'container.py')):
            code = """from firefly.di.application import DIC
    
    
    class Container(DIC):
        pass
    """
            with open(os.path.join(di_dir, 'container.py'), 'w') as fp:
                fp.write(code)

    os.chdir(current_dir)


class PostDevelopCommand(develop):
    def run(self):
        setup_project_structure()
        develop.run(self)


class PostInstallCommand(install):
    def run(self):
        setup_project_structure()
        install.run(self)


setuptools.setup(
    name='firefly-dependency-injection',
    version='0.1',
    author="JD Williams",
    author_email="me@jdwilliams.xyz",
    description="A dependency injection framework for python",
    long_description=long_description,
    # long_description_content_type="text/markdown",
    url="https://github.com/firefly19/python-dependency-injection",
    # packages=setuptools.find_packages('src'),
    packages=setuptools.PEP420PackageFinder.find('src'),
    package_dir={'': 'src'},
    # py_modules=[splitext(basename(path))[0] for path in glob('src/*.py')],
    classifiers=[
        "Programming Language :: Python :: 3.7",
        "Operating System :: OS Independent",
    ],
    cmdclass={
        'develop': PostDevelopCommand,
        'install': PostInstallCommand,
    }
)
