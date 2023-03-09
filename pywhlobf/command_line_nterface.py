import sys
from pathlib import Path
from importlib.machinery import ExtensionFileLoader, ModuleSpec
from importlib.util import module_from_spec

import fire


def run_c_extension(c_extension_file: Path):
    name = c_extension_file.name.split('.')[0]
    loader = ExtensionFileLoader(name=name, path=str(c_extension_file))
    spec = ModuleSpec(name=name, loader=loader, origin=str(c_extension_file))
    module = module_from_spec(spec)
    module.__name__ = '__main__'
    sys.modules[name] = module
    loader.exec_module(module)


class CommandLineInterface:

    def file_config(self):
        '''
        desc

        :param todo:
            todo.
        '''

    def file(self):
        '''
        desc

        :param todo:
            todo.
        '''

    def package_config(self):
        '''
        desc

        :param todo:
            todo.
        '''

    def package(self):
        '''
        desc

        :param todo:
            todo.
        '''

    def wheel_config(self):
        '''
        desc

        :param todo:
            todo.
        '''

    def wheel(self):
        '''
        desc

        :param todo:
            todo.
        '''

    def run(self):
        '''
        desc

        :param todo:
            todo.
        '''

    def decrypt(self):
        '''
        desc

        :param todo:
            todo.
        '''


def main():
    fire.Fire(CommandLineInterface)
