from typing import Any
import sys
from pathlib import Path
from importlib.machinery import ExtensionFileLoader, ModuleSpec
from importlib.util import module_from_spec

import iolite as io
import fire


def run_extension_file(extension_file: Path):
    name = extension_file.name.split('.')[0]
    extension_file = extension_file.absolute()
    loader = ExtensionFileLoader(name=name, path=str(extension_file))
    spec = ModuleSpec(name=name, loader=loader, origin=str(extension_file))
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

    def run_ext(self, extension_file_path: str, *args: Any, **kwargs: Any):
        '''
        desc

        :param todo:
            todo.
        '''
        extension_file = io.file(extension_file_path, exists=True).absolute()
        assert io.file(sys.argv[2]).absolute() == extension_file
        sys.argv = sys.argv[2:]
        run_extension_file(extension_file)

    def decrypt_msg(self):
        '''
        desc

        :param todo:
            todo.
        '''


def main():
    fire.Fire(CommandLineInterface)


if __name__ == '__main__':
    print(sys.argv)
