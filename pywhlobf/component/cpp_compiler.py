from typing import Sequence
from pathlib import Path
import os
import subprocess

import attrs
from distutils.extension import Extension
from distutils.core import setup
from distutils import sysconfig


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
            ext_module.extra_compile_args.append('-std=c++17')

            cmd = sysconfig.get_config_var('LDCXXSHARED')
            assert isinstance(cmd, str)

            if cmd.startswith('g++'):
                # https://askubuntu.com/questions/1256440/how-to-get-libstdc-with-c17-filesystem-headers-on-ubuntu-18-bionic
                # NOTE: It's ok to pass `-lstdc++fs` to GCC > 9.1.
                ext_module.extra_link_args.append('-lstdc++fs')

            elif cmd.startswith('clang++'):
                # Get libc++ version.
                result = subprocess.run(
                    'printf "#include <ciso646>\nint main () {}" '
                    '| clang -E -stdlib=libc++ -x c++ -dM - '
                    '| grep _LIBCPP_VERSION',
                    shell=True,
                    capture_output=True,
                    check=True,
                    text=True,
                )
                stdout = result.stdout
                assert '_LIBCPP_VERSION' in stdout
                # VRRR format.
                libcpp_version = stdout.split()[-1]
                libcpp_major_version = int(libcpp_version[:-3])
                # https://releases.llvm.org/10.0.0/projects/libcxx/docs/UsingLibcxx.html#using-filesystem
                if libcpp_major_version < 7:
                    ext_module.extra_link_args.append('-lc++experimental')
                elif libcpp_major_version < 9:
                    ext_module.extra_link_args.append('-lc++fs')

            elif cmd.startswith('msvc?'):
                raise NotImplementedError()

            else:
                raise NotImplementedError()

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
