from typing import Sequence
from enum import unique, Enum
from pathlib import Path
import os
import subprocess
from multiprocessing import Process, ProcessError
import re
import sysconfig
import tempfile
import shutil

import attrs
import iolite as io
from setuptools import setup, Extension


@attrs.define
class CppCompilerConfig:
    # TODO: support extra arguments listed in
    # https://setuptools.pypa.io/en/latest/userguide/ext_modules.html#setuptools.Extension
    setup_build_ext_timeout: int = 120
    delete_temp_fd: bool = True


@unique
class CppCompilerKind(Enum):
    MSVC = 'msvc'
    CLANG = 'clang'
    GCC = 'gcc'


def get_cpp_file_from_ext_module(ext_module: Extension):
    assert len(ext_module.sources) == 1
    cpp_file = io.file(ext_module.sources[0], exists=True)
    return cpp_file


def setup_build_ext(
    ext_module: Extension,
    working_fd: Path,
    temp_fd: Path,
):
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


class CppCompiler:

    def __init__(self, config: CppCompilerConfig):
        self.config = config

        # Detect C++ compiler.
        cxx = sysconfig.get_config_var('CXX')
        if not cxx:
            assert os.name == 'nt'
            self.cpp_compiler_kind = CppCompilerKind.MSVC
            self.clang_version_major = None
            self.gcc_version_major = None
            self.gcc_version_minor = None

        else:
            process = subprocess.run(
                # https://en.cppreference.com/w/cpp/header/ciso646
                # NOTE: It's fine since we don't use c++20.
                'printf "#include <ciso646>\nint main () {}" '
                f'| {cxx} -E -x c++ -dM -',
                shell=True,
                capture_output=True,
                check=True,
                text=True,
            )
            stdout = process.stdout

            libcpp_version_match = re.search(r'_LIBCPP_VERSION (\d+)', stdout)
            glibcpp_version_match = re.search(r'__GLIBCXX__', stdout)

            # https://stuff.mit.edu/afs/athena/project/rhel-doc/3/rhel-cpp-en-3/predefined-macros.html
            gunc_match = re.search(r'__GNUC__ (\d+)', stdout)
            gunc_minor_match = re.search(r'__GNUC_MINOR__ (\d+)', stdout)

            if libcpp_version_match:
                # VRRR format.
                self.cpp_compiler_kind = CppCompilerKind.CLANG
                libcpp_version = libcpp_version_match.group(1)
                self.clang_version_major = int(libcpp_version[:-3])

            elif glibcpp_version_match:
                self.cpp_compiler_kind = CppCompilerKind.GCC
                assert gunc_match and gunc_minor_match
                self.gcc_version_major = int(gunc_match.group(1))
                self.gcc_version_minor = int(gunc_minor_match.group(1))

            else:
                raise NotImplementedError()

    def run(
        self,
        ext_module: Extension,
        working_fd: Path,
        include_fds: Sequence[Path],
        string_literal_obfuscator_activated: bool,
        source_code_injector_activated: bool,
    ):
        '''
        `working_fd` could be the python package root folder.
        '''

        # Configure compiler.
        if source_code_injector_activated:
            if self.cpp_compiler_kind == CppCompilerKind.CLANG:
                ext_module.extra_compile_args.append('-std=c++17')

                assert self.clang_version_major
                # https://releases.llvm.org/10.0.0/projects/libcxx/docs/UsingLibcxx.html#using-filesystem
                if self.clang_version_major < 7:
                    ext_module.extra_link_args.append('-lc++experimental')
                elif self.clang_version_major < 9:
                    ext_module.extra_link_args.append('-lc++fs')

            elif self.cpp_compiler_kind == CppCompilerKind.GCC:
                ext_module.extra_compile_args.append('-std=c++17')

                assert self.gcc_version_major and self.gcc_version_minor
                if self.gcc_version_major < 9 \
                        or self.gcc_version_major == 9 and self.gcc_version_minor < 1:
                    ext_module.extra_link_args.append('-lstdc++fs')

            elif self.cpp_compiler_kind == CppCompilerKind.MSVC:
                # This works for Visual Studio >= 2019.
                # https://learn.microsoft.com/en-us/cpp/standard-library/filesystem?view=msvc-170
                ext_module.extra_compile_args.append('/std:c++17')

            else:
                raise NotImplementedError()

        elif string_literal_obfuscator_activated:
            if self.cpp_compiler_kind in (CppCompilerKind.CLANG, CppCompilerKind.GCC):
                ext_module.extra_compile_args.append('-std=c++14')
            elif self.cpp_compiler_kind == CppCompilerKind.MSVC:
                ext_module.extra_compile_args.append('/std:c++14')
            else:
                raise NotImplementedError()

        else:
            if self.cpp_compiler_kind in (CppCompilerKind.CLANG, CppCompilerKind.GCC):
                ext_module.extra_compile_args.append('-std=c++11')
            elif self.cpp_compiler_kind == CppCompilerKind.MSVC:
                ext_module.extra_compile_args.append('/std:c++11')
            else:
                raise NotImplementedError()

        # Add include_dirs.
        for include_fd in include_fds:
            ext_module.include_dirs.append(str(include_fd))

        # Build the shared library.
        cpp_file = get_cpp_file_from_ext_module(ext_module)
        temp_fd = io.folder(tempfile.mkdtemp(), exists=True)

        process = Process(
            target=setup_build_ext,
            kwargs={
                'ext_module': ext_module,
                'working_fd': working_fd,
                'temp_fd': temp_fd,
            },
        )
        process.start()
        process.join(timeout=self.config.setup_build_ext_timeout)

        if process.exitcode != 0:
            process.kill()
            if process.exitcode is None:
                raise ProcessError('Compilation timeout.')
            else:
                raise ProcessError('Compilation failed.')

        # Get the path of shared library.
        if os.name == 'posix':
            # POSIX.
            ext = '.so'
        elif os.name == 'nt':
            # Windows.
            ext = '.pyd'
        else:
            raise NotImplementedError()

        if self.config.delete_temp_fd:
            shutil.rmtree(temp_fd)

        compiled_lib_files = tuple(cpp_file.parent.glob(f'{cpp_file.stem}.*{ext}'))
        assert len(compiled_lib_files) == 1
        return compiled_lib_files[0]
