from typing import Sequence
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
            if os.name == 'posix':
                ext_module.extra_compile_args.append('-std=c++17')
                # POSIX.
                cxx = sysconfig.get_config_var('CXX')
                assert cxx

                result = subprocess.run(
                    # https://en.cppreference.com/w/cpp/header/ciso646
                    # NOTE: It's fine since we don't use c++20.
                    'printf "#include <ciso646>\nint main () {}" '
                    f'| {cxx} -E -x c++ -dM -',
                    shell=True,
                    capture_output=True,
                    check=True,
                    text=True,
                )
                stdout = result.stdout

                libcpp_version_match = re.search(r'_LIBCPP_VERSION (\d+)', stdout)
                glibcpp_version_match = re.search(r'__GLIBCXX__', stdout)

                # https://stuff.mit.edu/afs/athena/project/rhel-doc/3/rhel-cpp-en-3/predefined-macros.html
                gunc_match = re.search(r'__GNUC__ (\d+)', stdout)
                gunc_minor_match = re.search(r'__GNUC_MINOR__ (\d+)', stdout)

                if libcpp_version_match:
                    # VRRR format.
                    libcpp_version = libcpp_version_match.group(1)
                    libcpp_major_version = int(libcpp_version[:-3])
                    # https://releases.llvm.org/10.0.0/projects/libcxx/docs/UsingLibcxx.html#using-filesystem
                    if libcpp_major_version < 7:
                        ext_module.extra_link_args.append('-lc++experimental')
                    elif libcpp_major_version < 9:
                        ext_module.extra_link_args.append('-lc++fs')

                elif glibcpp_version_match:
                    assert gunc_match and gunc_minor_match
                    major = int(gunc_match.group(1))
                    minor = int(gunc_minor_match.group(1))
                    if major < 9 or major == 9 and minor < 1:
                        ext_module.extra_link_args.append('-lstdc++fs')

                else:
                    raise NotImplementedError()

            elif os.name == 'nt':
                # Windows.
                # This works for Visual Studio >= 2019.
                # https://learn.microsoft.com/en-us/cpp/standard-library/filesystem?view=msvc-170
                ext_module.extra_compile_args.append('/std:c++17')

            else:
                raise NotImplementedError()

        elif string_literal_obfuscator_activated:
            if os.name == 'posix':
                # POSIX.
                ext_module.extra_compile_args.append('-std=c++14')
            elif os.name == 'nt':
                # Windows.
                ext_module.extra_compile_args.append('/std:c++14')
            else:
                raise NotImplementedError()

        else:
            if os.name == 'posix':
                # POSIX.
                ext_module.extra_compile_args.append('-std=c++11')
            elif os.name == 'nt':
                # Windows.
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
