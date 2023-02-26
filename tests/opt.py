import os
import inspect
import subprocess

import iolite as io
from Cython.Compiler.Version import version as cython_version


def get_data_folder(file: str):
    proc = subprocess.run(
        f'$PYWHLOBF_ROOT/.direnv/bin/pyproject-data-folder "$PYWHLOBF_ROOT" "$PYWHLOBF_DATA" "{file}"',  # noqa
        shell=True,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0

    data_folder = proc.stdout.strip()
    assert data_folder

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


def get_test_py_file():
    if cython_version[0] != '3':
        return io.file(
            '$PYWHLOBF_DATA/test-data/wheel-0.37.1/wheel/bdist_wheel.py',
            expandvars=True,
            exists=True,
        )
    else:
        return io.file(
            '$PYWHLOBF_DATA/test-data/wheel-0.38.4/wheel/bdist_wheel.py',
            expandvars=True,
            exists=True,
        )
