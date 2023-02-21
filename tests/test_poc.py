import os
import shutil
import re
from pathlib import Path

import iolite as io
from Cython.Build.Dependencies import cythonize
from Cython.Compiler.Version import version
from distutils.extension import Extension
from distutils.core import setup


def is_cython3():
    return version.startswith('3')


def poc_cythonize(py_file: Path, working_fd: Path):
    working_py_file = working_fd / py_file.name
    shutil.copyfile(py_file, working_py_file)

    cythonize_options = {'language_level': 3, 'language': 'c++'}
    ext_modules = cythonize(module_list=[str(working_py_file)], **cythonize_options)
    print(ext_modules)
    assert ext_modules is not None
    assert len(ext_modules) == 1

    cpp_file = working_py_file.with_suffix('.cpp')
    assert cpp_file.is_file()
    return cpp_file, ext_modules[0]


def poc_obfuscate_inplace(cpp_file: Path, ext_module: Extension, temp_fd: Path, asset_fd: Path):
    include_fd = temp_fd / 'include'
    include_fd.mkdir()

    shutil.copyfile(
        asset_fd / 'Obfuscate' / 'obfuscate.h',
        include_fd / 'obfuscate.h',
    )
    shutil.copyfile(
        asset_fd / 'obfuscate_sizeof.h',
        include_fd / 'obfuscate_sizeof.h',
    )

    ext_module.include_dirs = [str(include_fd)]
    ext_module.extra_compile_args = ['-std=c++14']

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
            '#include "obfuscate_sizeof.h"',
            code,
        ])
    )


def poc_compile(cpp_file: Path, ext_module: Extension, temp_fd: Path):
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


def debug_poc_cythonize():
    assert not is_cython3()
    py_file = io.file(
        '$PYWHLOBF_DATA/poc/wheel-src/wheel-0.37.1/wheel/bdist_wheel.py',
        expandvars=True,
        exists=True,
    )

    working_fd = io.folder('$PYWHLOBF_DATA/poc/working', expandvars=True, touch=True)
    temp_fd = io.folder(working_fd / 'temp', reset=True)
    asset_fd = io.folder('$PYWHLOBF_DATA/poc/asset', expandvars=True, exists=True)

    cpp_file, ext_module = poc_cythonize(py_file, working_fd)
    poc_obfuscate_inplace(
        cpp_file=cpp_file,
        ext_module=ext_module,
        temp_fd=temp_fd,
        asset_fd=asset_fd,
    )
    poc_compile(cpp_file=cpp_file, ext_module=ext_module, temp_fd=temp_fd)


def debug_poc_cythonize_pyx():
    assert not is_cython3()
    py_file = io.file(
        '$PYWHLOBF_DATA/poc/customized-src/example.pyx',
        expandvars=True,
        exists=True,
    )

    working_fd = io.folder('$PYWHLOBF_DATA/poc/working', expandvars=True, touch=True)
    temp_fd = io.folder(working_fd / 'temp', reset=True)
    asset_fd = io.folder('$PYWHLOBF_DATA/poc/asset', expandvars=True, exists=True)

    cpp_file, ext_module = poc_cythonize(py_file, working_fd)
    poc_obfuscate_inplace(
        cpp_file=cpp_file,
        ext_module=ext_module,
        temp_fd=temp_fd,
        asset_fd=asset_fd,
    )
    poc_compile(cpp_file=cpp_file, ext_module=ext_module, temp_fd=temp_fd)


def debug_poc_cythonize_cython3():
    assert is_cython3()
    # https://github.com/cython/cython/issues/2863
    py_file = io.file(
        '$PYWHLOBF_DATA/poc/wheel-src/wheel-0.38.4/wheel/bdist_wheel.py',
        expandvars=True,
        exists=True,
    )

    working_fd = io.folder('$PYWHLOBF_DATA/poc/working', expandvars=True, touch=True)
    temp_fd = io.folder(working_fd / 'temp', reset=True)
    asset_fd = io.folder('$PYWHLOBF_DATA/poc/asset', expandvars=True, exists=True)

    cpp_file, ext_module = poc_cythonize(py_file, working_fd)
    poc_obfuscate_inplace(
        cpp_file=cpp_file,
        ext_module=ext_module,
        temp_fd=temp_fd,
        asset_fd=asset_fd,
    )
    poc_compile(cpp_file=cpp_file, ext_module=ext_module, temp_fd=temp_fd)
