from typing import Sequence
from pathlib import Path
import os

import attrs
from distutils.extension import Extension
from distutils.core import setup


@attrs.define
class CppCompilerConfig:
    pass


class CppCompiler:

    def __init__(self, config: CppCompilerConfig):
        self.config = config

    def run(
        self,
        cpp_file: Path,
        ext_module: Extension,
        include_fds: Sequence[Path],
        temp_fd: Path,
        string_literal_obfuscator_activated: bool,
        source_code_injector_activated: bool,
    ):
        # Set -std.
        if source_code_injector_activated:
            ext_module.extra_compile_args.extend(['-std=c++17', '-lstdc++fs'])
            # TODO: https://releases.llvm.org/10.0.0/projects/libcxx/docs/UsingLibcxx.html#using-filesystem  # noqa
        elif string_literal_obfuscator_activated:
            ext_module.extra_compile_args.append('-std=c++14')
        else:
            ext_module.extra_compile_args.append('-std=c++11')

        # Add include_dirs.
        for include_fd in include_fds:
            ext_module.include_dirs.append(str(include_fd))

        # Build the shared library.
        cwd = os.getcwd()
        working_fd = cpp_file.parent
        os.chdir(working_fd)
        setup(
            script_name='setup.py',
            script_args=[
                'build_ext',
                '-i',
                '--build-temp',
                str(temp_fd),
            ],
            ext_modules=[ext_module],
        )
        os.chdir(cwd)

        # Get the path of shared library.
        if os.name != 'nt':
            # Non-Windows.
            ext = '.so'
        else:
            # Windows.
            ext = '.pyd'

        compiled_lib_files = tuple(working_fd.glob(f'{cpp_file.stem}*{ext}'))
        assert len(compiled_lib_files) == 1
        return compiled_lib_files[0]
