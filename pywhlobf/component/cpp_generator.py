from typing import Mapping, Union
from pathlib import Path
import shutil
import re

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

    @classmethod
    def patch_cpp_file_generated_by_cython2(cls, py_file: Path, cpp_file: Path):
        if py_file.stem != '__init__':
            return

        code = cpp_file.read_text()
        if 'PyInit___init__' in code:
            # Cython3, no need to patch.
            return

        shutil.copyfile(cpp_file, cpp_file.with_suffix('.cpp.bak_before_patching_init'))

        # Inject PyInit___init__ for Windows.
        pattern_py_init_prefix = rf'^__Pyx_PyMODINIT_FUNC\s+PyInit_{py_file.parent.name}\(void\)'
        pattern_py_init_suffix = r'\s+CYTHON_SMALL_CODE;\s+/\*proto\*/'
        pattern_py_init = (
            rf'^({pattern_py_init_prefix}{pattern_py_init_suffix})\n'
            rf'^({pattern_py_init_prefix})'
        )

        code_snippet = f'''
#if !defined(CYTHON_NO_PYINIT_EXPORT) && (defined(_WIN32) || defined(WIN32) || defined(MS_WINDOWS))
__Pyx_PyMODINIT_FUNC PyInit___init__(void) {{ return PyInit_{py_file.parent.name}(); }}
#endif
'''
        code = re.sub(
            pattern_py_init,
            '\n'.join([
                r'\1',
                code_snippet.strip(),
                r'\2',
            ]),
            code,
            flags=re.MULTILINE,
        )
        cpp_file.write_text(code)

    def run(self, py_file: Path, working_fd: Path):
        '''
        Copy the `py_file` into `working_fd` and generate C++ file inplace.
        '''
        assert working_fd.is_dir()

        if py_file.stem == '__init__':
            # Make sure the module name is matched.
            assert working_fd.name == py_file.parent.name

        # Copy python file to the working folder.
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
            **self.config.cythonize_options,  # type: ignore
        )
        assert ext_modules is not None
        assert len(ext_modules) == 1
        ext_module: Extension = ext_modules[0]

        # Make sure the cpp file is generated.
        assert cpp_file.is_file()

        # Patch.
        self.patch_cpp_file_generated_by_cython2(py_file=py_file, cpp_file=cpp_file)

        return cpp_file, ext_module
