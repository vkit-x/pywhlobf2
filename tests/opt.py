from typing import Optional
import os
import os.path
import inspect
import shutil

import iolite as io
from Cython.Compiler.Version import version as cython_version


def get_data_folder(code_path: str):
    proj_root = os.getenv('PYWHLOBF_ROOT')
    data_root = os.getenv('PYWHLOBF_DATA')
    assert proj_root and data_root

    if os.path.isabs(code_path):
        code_path = os.path.relpath(code_path, proj_root)

    rel_folder = code_path.split('.')[0]
    data_folder = os.path.join(data_root, rel_folder)

    io.folder(data_folder, touch=True)

    return data_folder


def get_test_output_fd(frames_offset: int = 0):
    if not os.getenv('PYWHLOBF_ROOT') or not os.getenv('PYWHLOBF_DATA'):
        raise NotImplementedError()

    frames = inspect.stack()
    frames_offset += 1
    module_path = frames[frames_offset].filename
    function_name = frames[frames_offset].function
    module_fd = io.folder(get_data_folder(module_path))
    test_fd = io.folder(module_fd / function_name, touch=True)
    return test_fd


def get_test_output_path(rel_path: str, frames_offset: int = 0):
    if not os.getenv('PYWHLOBF_ROOT') or not os.getenv('PYWHLOBF_DATA'):
        raise NotImplementedError()

    frames = inspect.stack()
    frames_offset += 1
    module_path = frames[frames_offset].filename
    function_name = frames[frames_offset].function
    module_fd = io.folder(get_data_folder(module_path))
    test_fd = io.folder(module_fd / function_name, touch=True)
    test_output_path = test_fd / rel_path
    io.folder(test_output_path.parent, touch=True)
    return test_output_path


def get_test_py_file(new_name: Optional[str] = ''):
    if cython_version[0] != '3':
        test_py_file = io.file(
            '$PYWHLOBF_DATA/test-data/wheel-0.37.1/wheel/bdist_wheel.py',
            expandvars=True,
            exists=True,
        )
    else:
        test_py_file = io.file(
            '$PYWHLOBF_DATA/test-data/wheel-0.38.4/wheel/bdist_wheel.py',
            expandvars=True,
            exists=True,
        )

    if new_name:
        new_fd = io.folder('$PYWHLOBF_DATA/test-data', expandvars=True, exists=True)
        new_fd = new_fd / 'wheel-new'
        new_fd.mkdir(exist_ok=True)
        new_test_py_file = io.file(new_fd / new_name)
        shutil.copyfile(test_py_file, new_test_py_file)
        test_py_file = new_test_py_file

    return test_py_file
