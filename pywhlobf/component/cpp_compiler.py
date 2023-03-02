from typing import Sequence
from enum import unique, Enum
from pathlib import Path
import os
import subprocess
import re
from distutils.extension import Extension
from distutils.core import setup
import sysconfig

import attrs


@attrs.define
class CppCompilerConfig:
    # TODO: support extra arguments listed in
    # https://docs.python.org/3/distutils/apiref.html#distutils.core.Extension
    pass


@unique
class CppCompilerKind(Enum):
    MSVC = 'msvc'
    CLANG = 'clang'
    GCC = 'gcc'


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
        cpp_file: Path,
        ext_module: Extension,
        include_fds: Sequence[Path],
        temp_fd: Path,
        string_literal_obfuscator_activated: bool,
        source_code_injector_activated: bool,
    ):
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
        if os.name == 'posix':
            # POSIX.
            ext = '.so'
        elif os.name == 'nt':
            # Windows.
            ext = '.pyd'
        else:
            raise NotImplementedError()

        compiled_lib_files = tuple(working_fd.glob(f'{cpp_file.stem}*{ext}'))
        assert len(compiled_lib_files) == 1
        return compiled_lib_files[0]
