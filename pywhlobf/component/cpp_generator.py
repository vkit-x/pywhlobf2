from typing import Mapping, Union
from pathlib import Path
import shutil

import attrs
from setuptools import Extension
from Cython.Build.Dependencies import cythonize
from Cython.Compiler import Options


@attrs.define
class CppGeneratorConfig:
    # See:
    # https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#Cython.Build.cythonize
    # https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#compiler-directives
    # https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#compiler-options
    compiler_directives: Mapping[str, Union[bool, str]] = attrs.field(factory=dict)
    cythonize_options: Mapping[str, Union[bool, int, str]] = attrs.field(factory=dict)
    compiler_options: Mapping[str, Union[bool, int, str]] = attrs.field(factory=dict)


class CppGenerator:

    def __init__(self, config: CppGeneratorConfig):
        self.config = config

    def run(self, py_file: Path, working_fd: Path):
        # Copy python file to the working folder.
        assert working_fd.is_dir()
        working_py_file = working_fd / py_file.name
        shutil.copyfile(py_file, working_py_file)
        py_file = working_py_file

        cpp_file = py_file.with_suffix('.cpp')
        # The `cythonize` function behave abnormally if the cpp file exists.
        cpp_file.unlink(missing_ok=True)

        # The `cythonize` function generate a c++ file alongside.
        compiler_directives = dict(self.config.compiler_directives)
        # NOTE: Make sure you know what you are doing if you pass the `language_level`.
        if 'language_level' not in compiler_directives:
            compiler_directives['language_level'] = '3'

        # Set compiler options.
        for key, value in self.config.compiler_options.items():
            assert hasattr(Options, key)
            setattr(Options, key, value)

        ext_modules = cythonize(
            module_list=[str(py_file)],
            # NOTE: Passing language will trigger a warning message, that is ok.
            language='c++',
            compiler_directives=compiler_directives,
            **self.config.cythonize_options,
        )
        assert ext_modules is not None
        assert len(ext_modules) == 1
        ext_module: Extension = ext_modules[0]

        # Make sure the cpp file is generated.
        assert cpp_file.is_file()

        return cpp_file, ext_module
