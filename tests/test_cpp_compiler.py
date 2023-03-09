import sys
import subprocess
import os

import iolite as io

from pywhlobf.component.cpp_generator import CppGeneratorConfig, CppGenerator
from pywhlobf.component.string_literal_obfuscator import (
    StringLiteralObfuscatorConfig,
    StringLiteralObfuscator,
)
from pywhlobf.component.source_code_injector import (
    SourceCodeInjectorConfig,
    SourceCodeInjector,
)
from pywhlobf.component.cpp_compiler import (
    CppCompilerConfig,
    CppCompiler,
)
from tests.opt import get_test_output_fd, get_test_py_file


def test_cpp_compiler():
    output_fd = get_test_output_fd()
    test_py_file = get_test_py_file()

    cpp_generator = CppGenerator(CppGeneratorConfig())
    cpp_file, ext_module = cpp_generator.run(test_py_file, output_fd)

    string_literal_obfuscator = StringLiteralObfuscator(StringLiteralObfuscatorConfig())
    string_literal_obfuscator_activated, include_fd = string_literal_obfuscator.run(cpp_file)
    assert string_literal_obfuscator_activated and include_fd

    source_code_injector = SourceCodeInjector(
        SourceCodeInjectorConfig(fernet_key='WwAPKBMXKl-I43L4u8B5WD9xoperM9qhXDlLVWRFkiY=')
    )
    source_code_injector_activated = source_code_injector.run(
        py_file=test_py_file,
        cpp_file=cpp_file,
    )
    assert source_code_injector_activated

    cpp_compiler = CppCompiler(CppCompilerConfig(build_ext_timeout=600))
    compiled_lib_file = cpp_compiler.run(
        ext_module=ext_module,
        working_fd=output_fd,
        include_fds=[include_fd],
        string_literal_obfuscator_activated=string_literal_obfuscator_activated,
        source_code_injector_activated=source_code_injector_activated,
    )
    assert compiled_lib_file.is_file()

    env = os.environ.copy()
    env['PYTHONPATH'] = str(output_fd)
    process = subprocess.run(
        [
            sys.executable,
            '-c',
            f'import {test_py_file.stem}',
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    print('-' * 40)
    print(process.stdout)
    print('-' * 40)
    print(process.stderr)
    print('-' * 40)
    encrypted_traceback = process.stderr
    assert 'wheel' not in encrypted_traceback
    assert encrypted_traceback.count('(pywhlobf') == 3


def test_cpp_compiler_exe():
    test_output_fd = get_test_output_fd()
    test_py_file = test_output_fd / 'some_file.py'
    test_py_file.write_text('''
if __name__ == '__main__':
    print("this is exe")
''')

    output_fd = io.folder(test_output_fd / 'working', touch=True)
    cpp_generator = CppGenerator(CppGeneratorConfig(compiler_options={'embed': 'main'}))
    _, ext_module = cpp_generator.run(test_py_file, output_fd)

    cpp_compiler = CppCompiler(
        CppCompilerConfig(
            build_ext_timeout=600,
            enable_build_exe=True,
            build_exe_timeout=600,
            delete_temp_fd=False,
        )
    )
    compiled_exe_file = cpp_compiler.run(
        ext_module=ext_module,
        working_fd=output_fd,
        include_fds=[],
        string_literal_obfuscator_activated=False,
        source_code_injector_activated=False,
    )
    process = subprocess.run(
        str(compiled_exe_file),
        check=True,
        capture_output=True,
        text=True,
    )
    assert process.stdout.strip() == 'this is exe'
