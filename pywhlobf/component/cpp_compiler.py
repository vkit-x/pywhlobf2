from typing import Sequence
from enum import unique, Enum
from pathlib import Path
import os
import os.path
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
    build_ext_timeout: int = 60
    delete_temp_fd: bool = True
    enable_build_exe: bool = False
    build_exe_timeout: int = 60


@unique
class CppCompilerKind(Enum):
    MSVC = 'msvc'
    CLANG = 'clang'
    GCC = 'gcc'


def get_config_var(name: str, default: str = '') -> str:
    return sysconfig.get_config_var(name) or default


class BuildVariable:
    LIBDIR1 = get_config_var('LIBDIR')
    LIBDIR2 = get_config_var('LIBPL')
    PYLIB = get_config_var('LIBRARY')
    PYLIB_DYN = get_config_var('LDLIBRARY')
    CC = get_config_var('CC', os.environ.get('CC', ''))
    CXX = get_config_var('CXX')
    CFLAGS = get_config_var('CFLAGS') + ' ' + os.environ.get('CFLAGS', '')
    LINKCC = get_config_var('LINKCC', os.environ.get('LINKCC', CC))
    LINKFORSHARED = get_config_var('LINKFORSHARED')
    LIBS = get_config_var('LIBS')
    SYSLIBS = get_config_var('SYSLIBS')
    EXE_EXT = get_config_var('EXE')


if BuildVariable.PYLIB_DYN == BuildVariable.PYLIB:
    # Not a shared library.
    BuildVariable.PYLIB_DYN = ''

    pylib_file = io.folder(BuildVariable.LIBDIR1) / BuildVariable.PYLIB
    if not pylib_file.exists():
        # 'lib(XYZ).a' -> 'XYZ'.
        patch_name = os.path.splitext(BuildVariable.PYLIB[3:])[0]
        pylib_file = pylib_file.with_name(patch_name)
        if pylib_file.exists():
            BuildVariable.PYLIB = patch_name
        else:
            raise NotImplementedError()

else:
    # 'lib(XYZ).so' -> 'XYZ'.
    BuildVariable.PYLIB_DYN = os.path.splitext(BuildVariable.PYLIB_DYN[3:])[0]


def get_cpp_file_from_ext_module(ext_module: Extension):
    assert len(ext_module.sources) == 1
    cpp_file = io.file(ext_module.sources[0], exists=True)
    return cpp_file


def build_ext(
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
        if not BuildVariable.CXX:
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
                f'| {BuildVariable.CXX} -E -x c++ -dM -',
                shell=True,
                capture_output=True,
                check=True,
                text=True,
                timeout=self.config.build_ext_timeout,
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

        process_build_ext = Process(
            target=build_ext,
            kwargs={
                'ext_module': ext_module,
                'working_fd': working_fd,
                'temp_fd': temp_fd,
            },
        )
        process_build_ext.start()
        process_build_ext.join(timeout=self.config.build_ext_timeout)

        if process_build_ext.exitcode != 0:
            process_build_ext.kill()
            if process_build_ext.exitcode is None:
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

        compiled_lib_files = tuple(cpp_file.parent.glob(f'{cpp_file.stem}.*{ext}'))
        assert len(compiled_lib_files) == 1
        compiled_lib_file = compiled_lib_files[0]
        assert compiled_lib_file.is_file()

        if not self.config.enable_build_exe:
            compiled_file = compiled_lib_file

        else:
            # https://github.com/cython/cython/blob/master/Cython/Build/BuildExecutable.py
            object_file_ext = '.o' if os.name != 'nt' else '.obj'
            complied_object_files = list(temp_fd.glob(f'**/*{object_file_ext}'))
            assert len(complied_object_files) == 1
            complied_object_file = complied_object_files[0]

            compiled_exe_file = compiled_lib_file.parent / complied_object_file.name
            compiled_exe_file = compiled_exe_file.with_suffix(BuildVariable.EXE_EXT)

            args = [
                BuildVariable.LINKCC,
                '-o',
                str(compiled_exe_file),
                str(complied_object_file),
                '-L' + BuildVariable.LIBDIR1,
                '-L' + BuildVariable.LIBDIR2,
                (
                    BuildVariable.PYLIB_DYN and ('-l' + BuildVariable.PYLIB_DYN)
                    or os.path.join(BuildVariable.LIBDIR1, BuildVariable.PYLIB)
                ),
            ]
            args.extend(BuildVariable.LIBS.split())
            args.extend(BuildVariable.SYSLIBS.split())
            args.extend(BuildVariable.LINKFORSHARED.split())
            process_build_exe = subprocess.run(
                ' '.join(args),
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.config.build_exe_timeout,
            )
            if process_build_exe.returncode != 0:
                raise ProcessError(
                    'Failed to build exe.\n'
                    f'stdout={process_build_exe.stdout}\n'
                    f'stderr={process_build_exe.stderr}'
                )

            assert compiled_exe_file.is_file()
            compiled_file = compiled_exe_file

        if self.config.delete_temp_fd:
            shutil.rmtree(temp_fd)

        return compiled_file
