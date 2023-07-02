from typing import List
import os
import shutil
import re
from pathlib import Path
import importlib.util
import sys
import random
import hashlib

import iolite as io
from Cython.Build.Dependencies import cythonize
from Cython.Compiler.Version import version
from setuptools import setup, Extension
from cryptography.fernet import Fernet


def is_cython3():
    return version.startswith('3')


def poc_cythonize(py_file: Path, working_fd: Path):
    working_py_file = working_fd / py_file.name
    shutil.copyfile(py_file, working_py_file)

    cythonize_options = {'language_level': 3, 'language': 'c++'}
    ext_modules = cythonize(module_list=[str(working_py_file)], **cythonize_options)  # type: ignore
    print(ext_modules)
    assert ext_modules is not None
    assert len(ext_modules) == 1

    cpp_file = working_py_file.with_suffix('.cpp')
    assert cpp_file.is_file()
    return cpp_file, ext_modules[0]


def poc_obfuscate_inplace(cpp_file: Path, ext_module: Extension, temp_fd: Path, asset_fd: Path):
    include_fd = temp_fd / 'include'
    include_fd.mkdir(exist_ok=True)

    shutil.copyfile(
        asset_fd / 'Obfuscate' / 'obfuscate.h',
        include_fd / 'obfuscate.h',
    )
    shutil.copyfile(
        asset_fd / 'obfuscate_utility.h',
        include_fd / 'obfuscate_utility.h',
    )

    ext_module.include_dirs.append(str(include_fd))

    # shutil.copyfile(cpp_file, cpp_file.with_suffix('.cpp.bak'))

    code = cpp_file.read_text()

    # Pattern 1.
    pattern = r'^static const char (\w+)\[\] = \"(.*?)\";$'

    var_names = []
    for var_name, _ in re.findall(pattern, code, flags=re.MULTILINE):
        var_names.append(var_name)

    code = re.sub(
        pattern,
        '\n'.join([
            r'static const char *\1 = AY_OBFUSCATE("\2");',
            r'static const long __length\1 = HACK_LENGTH("\2");',
        ]),
        code,
        flags=re.MULTILINE,
    )
    for var_name in var_names:
        sizeof_pattern = r'sizeof\(' + var_name + r'\)'
        code = re.sub(sizeof_pattern, f'__length{var_name}', code)

    # Pattern 2.
    pattern = r'^static char (\w+)\[\] = \"(.*?)\";$'

    var_names = []
    for var_name, _ in re.findall(pattern, code, flags=re.MULTILINE):
        var_names.append(var_name)

    code = re.sub(
        pattern,
        '\n'.join([
            r'static char *\1 = AY_OBFUSCATE("\2");',
            r'static const long __length\1 = HACK_LENGTH("\2");',
        ]),
        code,
        flags=re.MULTILINE,
    )
    for var_name in var_names:
        sizeof_pattern = r'sizeof\(' + var_name + r'\)'
        code = re.sub(sizeof_pattern, f'__length{var_name}', code)

    cpp_file.write_text(
        '\n'.join([
            '#include "obfuscate.h"',
            '#include "obfuscate_utility.h"',
            code,
        ])
    )


def poc_encrypt(fernet: Fernet, text: str):
    text += f'pywhlobf-salt:{random.randint(int(1E5), int(1E6))}'
    return f'<pywhlobf {fernet.encrypt(text.encode()).decode()}>'


def poc_inject_encrypted_source_code(cpp_file: Path, py_file: Path):
    # Encrypt source code.
    fernet = Fernet(b'WwAPKBMXKl-I43L4u8B5WD9xoperM9qhXDlLVWRFkiY=')
    encrypted_src_lines: List[str] = []
    for src_line in py_file.read_text().splitlines():
        encrypted_src_line = poc_encrypt(fernet, src_line)
        encrypted_src_lines.append(encrypted_src_line)

    encrypted_src_code_lines: List[str] = []
    encrypted_src_code_lines.append('const std::string encrypted_source_code =')
    for encrypted_src_line in encrypted_src_lines:
        encrypted_src_code_lines.append(f'        "{encrypted_src_line}\\\\n"')
    encrypted_src_code = '\n'.join(encrypted_src_code_lines) + ';'

    # Get file hash.
    # TODO: encrypt file name + hash.
    py_file_hash = hashlib.sha256(py_file.read_bytes()).hexdigest()

    # Code snippet for saving encrypted source code.
    write_encrypted_src_code_to_tempfile_code = f'''
static std::filesystem::path write_encrypted_src_code_to_temp_file() {{
    auto temp_fd = std::filesystem::temp_directory_path();
    auto temp_pywhlobf_fd = temp_fd / "pywhlobf";
    auto temp_file = temp_pywhlobf_fd / "{py_file_hash}.py";

    if (std::filesystem::exists(temp_file)) {{
        // No need to update.
        return temp_file;
    }}

    // Make sure temp_fd exists.
    if (!std::filesystem::exists(temp_fd)) {{
        return temp_file;
    }}

    // Make sure temp_pywhlobf_fd exists.
    if (!std::filesystem::exists(temp_pywhlobf_fd)) {{
        if (!std::filesystem::create_directory(temp_pywhlobf_fd)) {{
            return temp_file;
        }}
    }}

    // Write the encrypted code to file.
    {encrypted_src_code}
    std::ofstream fout(temp_file);
    fout << encrypted_source_code;

    return temp_file;
}}
'''
    write_encrypted_src_code_to_tempfile_code = write_encrypted_src_code_to_tempfile_code.lstrip()

    # NOTE: This snippet will be injected into __PYX_ERR macro.
    # __PYX_ERR changes the variables in the scope, such as `__pyx_filename` variable.
    # In order to trace the temporary file, we will inject a `std::string __pyx_temp_file;`
    # statement after all appearances of `const char *__pyx_filename = NULL;`
    # and `static const char *__pyx_filename;`.
    pyx_mark_err_pos_code = '''
auto temp_file = write_encrypted_src_code_to_temp_file();
if (std::filesystem::exists(temp_file)) {
    __pyx_temp_file = temp_file.string();
    __pyx_filename = __pyx_temp_file.c_str();
}
'''
    # Flatten to one line.
    pyx_mark_err_pos_code = ' '.join(pyx_mark_err_pos_code.split())

    # Code injection.
    code = cpp_file.read_text()

    code = re.sub(
        r'(#define __PYX_MARK_ERR_POS.+?\\\s+\{.+?)\}',
        '\n'.join([
            write_encrypted_src_code_to_tempfile_code,
            r'\1' + pyx_mark_err_pos_code + '}',
        ]),
        code,
        flags=re.MULTILINE,
    )

    code = re.sub(
        r'^(static const char \*__pyx_filename;)',
        '\n'.join([
            r'\1',
            r'static std::string __pyx_temp_file;',
        ]),
        code,
        flags=re.MULTILINE,
    )

    code = re.sub(
        r'^(\s+)(const char \*__pyx_filename = NULL;)',
        '\n'.join([
            r'\1\2',
            r'\1std::string __pyx_temp_file;',
        ]),
        code,
        flags=re.MULTILINE,
    )

    code = re.sub(
        r'__Pyx_AddTraceback\(\"(.+?)\"',
        lambda match: f'__Pyx_AddTraceback("{poc_encrypt(fernet, match.group(1))}"',
        code,
        flags=re.MULTILINE,
    )
    code = re.sub(
        r'__Pyx_RaiseArgtupleInvalid\(\"(.+?)\"',
        lambda match: f'__Pyx_RaiseArgtupleInvalid("{poc_encrypt(fernet, match.group(1))}"',
        code,
        flags=re.MULTILINE,
    )

    cpp_file.write_text(
        '\n'.join([
            '#include <string>',
            '#include <filesystem>',
            '#include <fstream>',
            code,
        ])
    )


def poc_compile(cpp_file: Path, ext_module: Extension, temp_fd: Path):
    ext_module.extra_compile_args = ['-std=c++17']

    os.chdir(cpp_file.parent)
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


def poc_build(
    path: str,
    obfuscate: bool = True,
    inject_encrypted_source_code: bool = True,
):
    py_file = io.file(path, exists=True)

    working_fd = io.folder('$PYWHLOBF_DATA/poc/working', expandvars=True, touch=True)
    temp_fd = io.folder(working_fd / 'temp', reset=True)
    asset_fd = io.folder('$PYWHLOBF_DATA/poc/asset', expandvars=True, exists=True)

    cpp_file, ext_module = poc_cythonize(py_file, working_fd)

    if obfuscate:
        poc_obfuscate_inplace(
            cpp_file=cpp_file,
            ext_module=ext_module,
            temp_fd=temp_fd,
            asset_fd=asset_fd,
        )
    if inject_encrypted_source_code:
        poc_inject_encrypted_source_code(cpp_file, py_file)
    poc_compile(cpp_file=cpp_file, ext_module=ext_module, temp_fd=temp_fd)


def poc_run(path: str):
    file = io.file(path, exists=True)
    module_name = file.stem.split('.')[0]
    spec = importlib.util.spec_from_file_location(module_name, str(file))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    module.main()


def debug_poc_build_bdist_wheel():
    assert not is_cython3()
    py_file = io.file(
        '$PYWHLOBF_DATA/poc/wheel-src/wheel-0.37.1/wheel/bdist_wheel.py',
        expandvars=True,
        exists=True,
    )
    poc_build(str(py_file))


def debug_poc_build_bdist_wheel_cython3():
    assert is_cython3()
    # https://github.com/cython/cython/issues/2863
    py_file = io.file(
        '$PYWHLOBF_DATA/poc/wheel-src/wheel-0.38.4/wheel/bdist_wheel.py',
        expandvars=True,
        exists=True,
    )
    poc_build(str(py_file))


def debug_poc_build_example_pyx():
    assert not is_cython3()
    py_file = io.file(
        '$PYWHLOBF_DATA/poc/customized-src/example.pyx',
        expandvars=True,
        exists=True,
    )
    poc_build(str(py_file))


def debug_poc_build_main():
    py_file = io.file(
        '$PYWHLOBF_DATA/poc/customized-src/main.py',
        expandvars=True,
        exists=True,
    )
    poc_build(str(py_file))


def debug_poc_run_main():
    working_fd = io.folder('$PYWHLOBF_DATA/poc/working', expandvars=True, touch=True)
    poc_run(str(working_fd / 'main.cpython-38-darwin.so'))
