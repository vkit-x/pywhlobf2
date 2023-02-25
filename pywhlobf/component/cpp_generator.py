from typing import Mapping, Union
from pathlib import Path
import shutil

import attrs
from Cython.Build.Dependencies import cythonize


@attrs.define
class CppGeneratorConfig:
    # See:
    # https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#Cython.Build.cythonize
    # https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#compiler-directives
    language: str = 'c++'
    compiler_directives: Mapping[str, Union[bool, str]] = {'language_level': '3'}
    options: Mapping[str, Union[bool, int, str]] = attrs.field(factory=dict)


class CppGenerator:

    def __init__(self, config: CppGeneratorConfig):
        self.config = config

    def run(self, py_file: Path, working_fd: Path):
        # Copy python file to the working folder.
        assert working_fd.is_dir()
        working_py_file = working_fd / py_file.name
        shutil.copyfile(py_file, working_py_file)
        py_file = working_py_file

        # The `cythonize` function generate a c++ file alongside.
        ext_modules = cythonize(
            module_list=[str(py_file)],
            language=self.config.language,
            compiler_directives=self.config.compiler_directives,
            **self.config.options,
        )
        print(ext_modules)
        assert ext_modules is not None
        assert len(ext_modules) == 1
        ext_module = ext_modules[0]

        cpp_file = py_file.with_suffix('.cpp')
        assert cpp_file.is_file()

        return cpp_file, ext_module
